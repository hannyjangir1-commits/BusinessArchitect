# BATCH 04 — ADMIN AUTHORIZATION AND SUPER-ADMIN INTEGRITY REPORT

## 1. Executive Summary
Batch 04 repairs audit finding **S01** and closes privilege-escalation, hierarchy-bypass, and stale-identity-map race conditions across administrative user mutation endpoints. It introduces a centralized actor-versus-target policy, seals generic update and stale-cache bypasses, authoritatively synchronizes actor and target states prior to permission or invariant evaluation, strictly enforces the last-active-super-admin invariant across individual and combined payloads, and implements transaction-level PostgreSQL advisory locking to serialize concurrent operations that threaten the active super admin population.

---

## 2. Stale-State Synchronization and Invariant Check Repair
### Root Cause
Previously, `assert_super_admin_invariant()` in `server/app/services/admin_authorization_service.py` calculated `current_is_active_super` on the target ORM instance *before* acquiring the transaction-scoped advisory lock or refreshing the session:
```python
# Vulnerable sequence in commit 6331d61d
current_is_active_super = (target.role == "super_admin" and not target.is_suspended)
if current_is_active_super and not proposed_is_active_super:
    acquire_super_admin_invariant_lock(db)
    db.expire_all()
    ...
```
If an in-memory ORM object in Session 1 retained `is_suspended=True` from a previous read, and Session 2 reactivated that super admin while demoting the sole other active super admin and committed:
1. Target B was now the sole active super admin in the database.
2. Session 1 evaluated `target.is_suspended` on stale cached memory (`True`).
3. `current_is_active_super` evaluated to `False`.
4. The conditional skipped lock acquisition, cache expiration, and population counting entirely.
5. The operation succeeded, erroneously allowing the sole active super admin to be suspended and violating the invariant.

### Authoritative Architecture & Synchronization Protocol
The transaction architecture was refactored so that target and actor states are authoritatively fresh *before* evaluating permissions, determining population reduction, counting active accounts, or applying mutations:

1. **Protocol Implementation**:
   [`synchronize_and_authoritative_load(db, actor, target_id, required_permission)`](file:///d:/TE%20-%20SEM%285%29/businessplanner/antigravitybusiness/BusinessArchitect/server/app/services/admin_authorization_service.py) enforces:
   - **Step 1: Lock Acquisition**: Transaction-level advisory lock (`pg_advisory_xact_lock(6004834884214473805)`) on PostgreSQL or reentrant depth-tracked lock on SQLite is acquired *first*.
   - **Step 2: Session Cache Expire**: `db.expire_all()` clears the identity map.
   - **Step 3: Authoritative Actor Freshness**: Reloads the invoking actor from the database with `populate_existing()`. If the actor was suspended or demoted to an unauthorized role while waiting for the lock, the operation is immediately rejected with HTTP 403.
   - **Step 4: Authoritative Target Freshness**: If a target ID is provided, reloads the target with `populate_existing()`. Stale role or suspension state cannot bypass hierarchy checks.
   - **Step 5: Hierarchy Check**: [`validate_admin_mutation_target()`](file:///d:/TE%20-%20SEM%285%29/businessplanner/antigravitybusiness/BusinessArchitect/server/app/services/admin_authorization_service.py) runs against the authoritative target. An ordinary target promoted concurrently to an administrator role is recognized, and lower-administrator mutations are rejected with HTTP 403.
   - **Step 6: Authoritative Invariant Enforcement**: `assert_super_admin_invariant()` refreshes the target and queries active count under serialization. If `active_count <= 1`, the mutation is rejected with HTTP 400.
   - **Step 7: Atomic Mutation and Commit**: Changes applied to the verified target; transaction commits.

2. **Lock Order & Deadlock Risk Reduction**:
   All administrative mutation routes (`create_user`, `update_user`, `suspend_user`, `reactivate_user`, `revoke_user_sessions`, `delete_user`, `revoke_session`, `revoke_all_sessions`) acquire the identical single 64-bit advisory lock key (`6004834884214473805`) in uniform order. Using a common application-level lock reduces application lock-order risk across administrative transactions; it does not prove universal "deadlock freedom" against unrelated database-level locks or external access patterns. Ordinary user operations (browsing, profile updates, project management) remain entirely unblocked.

---

## 3. Shared Policy Implementation
All actor-versus-target policy rules are centralized into [`server/app/services/admin_authorization_service.py`](file:///d:/TE%20-%20SEM%285%29/businessplanner/antigravitybusiness/BusinessArchitect/server/app/services/admin_authorization_service.py):

1. **Pre-mutation Evaluation**: Payloads are fully validated against the target's original role AND proposed final state before any field mutation is applied.
2. **Administrator Privilege Gate**: Only `super_admin` can create, promote, demote, suspend, reactivate, delete, change the email of, or revoke sessions belonging to an administrator account (`role in ADMIN_ROLES`).
3. **No-Bypass Invariants**:
   - Omitting `role` (`role is None`) does not bypass the target hierarchy.
   - Supplying an unchanged role (`role == target.role`) does not grant permission to mutate other fields.
   - Passing combined demotion + suspension (`role: "user", is_suspended: true`) is rejected because `target.role in ADMIN_ROLES`.
   - Empty/no-op payloads (`{}`) targeting an administrator are rejected if the caller is not a `super_admin`.
4. **Self-Action Protections**:
   - Self-suspension (`req.is_suspended is True` when `target.id == actor.id`) is rejected with HTTP 400.
   - Self-deletion (`target.id == actor.id`) is rejected with HTTP 400.
   - Self-service profile and session routes under `/api/admin/auth/*` remain separate and intact.

---

## 4. Final Actor / Action / Target Authorization Matrix

> [!NOTE]
> In accordance with `server/app/api/deps.py::_get_permissions_for_role()`, `operations_admin` possesses all system permissions except `manage_users` and `manage_configuration`. This specifically includes `revoke_sessions`, granting `operations_admin` emergency global session revocation capability (`POST /api/admin/security/sessions/revoke-all`) and ordinary user session revocation, while barring it from user account mutations.

| Actor | Action / Route | Target: Ordinary User (`role='user'`) | Target: Administrator (`role in ADMIN_ROLES`, target != actor) | Target: Self (Actor == Target) |
|---|---|---|---|---|
| **Ordinary User** (`user`) | Any admin mutation route | 401 / 403 Forbidden | 401 / 403 Forbidden | 401 / 403 Forbidden |
| **Auditor** (`auditor`) | Any admin mutation route | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Operations Admin** (`operations_admin`) | User mutations (`/api/admin/users/*`) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Operations Admin** (`operations_admin`) | Session revocation (`/api/admin/security/sessions/{id}/revoke`) | **200 Allowed** (has `revoke_sessions`) | **403 Forbidden** (cannot revoke other admin's session) | **200 Allowed** (self-session revocation) |
| **Operations Admin** (`operations_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **200 Allowed** (emergency kill-switch; has `revoke_sessions`) | **200 Allowed** (emergency kill-switch) | Own current session preserved |
| **Security Admin** (`security_admin`) | User mutations (`/api/admin/users/*`) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Security Admin** (`security_admin`) | Session revocation (`/api/admin/security/sessions/{id}/revoke`) | **200 Allowed** (has `revoke_sessions`) | **403 Forbidden** (cannot revoke other admin's session) | **200 Allowed** (self-session revocation) |
| **Security Admin** (`security_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **200 Allowed** (emergency kill-switch; has `revoke_sessions`) | **200 Allowed** (emergency kill-switch) | Own current session preserved |
| **Support Admin** (`support_admin`) | `POST /api/admin/users` (create user) | **201 Allowed** (`role='user'`) | **403 Forbidden** (cannot create admin accounts) | N/A |
| **Support Admin** (`support_admin`) | `PUT /api/admin/users/{id}` (generic update) | **200 Allowed** (if new role is `'user'`; **403** if promoting to admin) | **403 Forbidden** (cannot modify any field of an admin) | **400** on self-suspend |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/suspend` | **200 Allowed** | **403 Forbidden** (cannot suspend an administrator) | **400 Bad Request** (cannot suspend own account) |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/reactivate` | **200 Allowed** | **403 Forbidden** (cannot reactivate an administrator) | N/A |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/revoke-sessions` | **200 Allowed** | **403 Forbidden** (cannot revoke an administrator's sessions) | N/A (can use self-service `/api/admin/auth/sessions`) |
| **Support Admin** (`support_admin`) | `DELETE /api/admin/users/{id}` | **200 Allowed** | **403 Forbidden** (cannot delete an administrator) | **400 Bad Request** (cannot delete own account) |
| **Support Admin** (`support_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **403 Forbidden** (lacks `revoke_sessions`) | **403 Forbidden** (lacks `revoke_sessions`) | **403 Forbidden** |
| **Super Admin** (`super_admin`) | `POST /api/admin/users` (create user) | **201 Allowed** | **201 Allowed** | N/A |
| **Super Admin** (`super_admin`) | `PUT /api/admin/users/{id}` (generic update) | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **200 Allowed** (subject to invariant, **400** on self-suspend) |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/suspend` | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **400 Bad Request** (cannot suspend own account) |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/reactivate` | **200 Allowed** | **200 Allowed** | N/A |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/revoke-sessions` | **200 Allowed** | **200 Allowed** | **200 Allowed** |
| **Super Admin** (`super_admin`) | `DELETE /api/admin/users/{id}` | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **400 Bad Request** (cannot delete own account) |
| **Super Admin** (`super_admin`) | Session revocation (`/api/admin/security/sessions/{id}/revoke`) | **200 Allowed** | **200 Allowed** | **200 Allowed** |
| **Super Admin** (`super_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **200 Allowed** | **200 Allowed** | Own current session preserved |

---

## 5. Sanitized Deletion Error Handling
In `delete_user()`, raw database exception exposure (`detail=f"Failed to delete user: {str(e)}"`) and raw traceback logging were eliminated.
- Server diagnostics log a bounded, structured entry containing only:
  - Fixed event name (`admin_user_deletion_failed`)
  - Request correlation ID when available
  - Safe operation identifier (`delete_user`)
  - Allowlisted exception category (e.g., `database_error`, `runtime_error`, `internal_error`)
- Server logs contain no exception messages, exception repr, SQL parameters, connection strings, credentials, or raw exception tracebacks (`exc_info=None`).
- Client responses return a stable generic message:
  ```json
  {
    "detail": "Failed to delete user account. Please try again or contact support."
  }
  ```
- No SQL statements, database URLs, table schemas, or database parameters are exposed to the client or leaked into server logs.
- Injected database failures roll back cleanly, leaving target user accounts and sessions intact.

---

## 6. Verification and Test Results

### Automated Suite Results
- **Focused Batch 04 Tests**: 27 passed, 1 skipped (`test_postgresql_concurrent_super_admin_removal`).
  - Added regression test: Suspended B becomes sole active super admin after another session commits; stale suspension rejected with HTTP 400.
  - Added regression test: Ordinary user concurrently promoted to admin rejects lower administrator mutation with HTTP 403.
  - Added regression test: Actor demoted or suspended concurrently is rejected before mutation proceeds.
  - Added regression test: Sequential stale-identity-map concurrent demotion cannot leave zero active super admins.
  - Added regression test: Injected deletion failure rolls back and sanitizes client error.
  - Added regression test: Full permission matrix for emergency global session revocation verifying `super_admin`, `operations_admin`, and `security_admin` are permitted with caller session exclusion, while `support_admin`, `auditor`, and `user` are rejected.
- **Complete Backend Suite**: 268 passed, 5 skipped (0 failures) in 44.13s.
- **Frontend Test Suite**: 100 passed (10 files) in 5.09s.
- **Frontend Lint**: 0 errors (25 warnings in legacy components).
- **Frontend Production Build**: `tsc -b && vite build` succeeded with exit code 0 in 481ms.
- **`git diff --check`**: Passed with 0 whitespace errors.

### PostgreSQL Concurrency Test & Isolation Architecture
The test `test_postgresql_concurrent_super_admin_removal` was isolated and hardened:
- **URL Parsing & Safety Guard**: Parses configuration using `sqlalchemy.engine.make_url`. Defaults to local disposable PostgreSQL only (`localhost`, `127.0.0.1`, `::1`); rejects remote destinations unless `TEST_POSTGRES_ALLOW_NAMED_ENV='disposable-test'` is explicitly configured. Full connection URLs containing credentials are never logged or exposed.
- **Isolated Schema Namespace**: Dynamically provisions a unique test-owned schema (`test_conc_<uuid>`) and applies `search_path` to all test connections, workers, and verifications. Never touches, modifies, or deletes from a shared or default schema.
- **Dedicated Synthetic Users**: Seeds exactly the 2 intended synthetic test users in the isolated schema.
- **Bounded Timeouts**: Strict 5s connection timeout, 10s statement timeout (`statement_timeout = 10000`), 5s lock timeout (`lock_timeout = 5000`), 5s barrier timeout (`Barrier(2)`), and 10s thread joins.
- **Guaranteed Teardown**: Teardown in `finally` ensures worker threads are stopped before cleanup, disposes test engines even if assertions fail, and drops the unique test schema with `CASCADE`.
- **Concurrency Assertions**: Asserts exactly 1 removal succeeds (HTTP 200) and exactly 1 invariant rejection occurs (HTTP 400: "last active super admin"), with zero unexpected exceptions.
- **SQLite vs. PostgreSQL Clarification**: SQLite tests execute under Python threading with in-process reentrant locking; they do not prove PostgreSQL behavior or engine-level serialization. When `TEST_POSTGRES_URL` is not configured, the PostgreSQL concurrency check is explicitly skipped with runnable instructions and is never reported as "verified."

Execution against disposable PostgreSQL:
```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:15
$env:TEST_POSTGRES_URL="postgresql://postgres:test@localhost:5433/postgres"
pytest server/tests/test_batch_04_admin_authorization.py -k test_postgresql_concurrent_super_admin_removal
```
