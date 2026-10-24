# BATCH 04 — ADMIN AUTHORIZATION AND SUPER-ADMIN INTEGRITY REPORT

## 1. Executive Summary
Batch 04 repairs audit finding **S01** and closes privilege-escalation and hierarchy bypass vulnerabilities across administrative user mutation endpoints. It introduces a centralized actor-versus-target policy, seals the generic update bypass, strictly enforces the last-active-super-admin invariant across individual and combined payloads, and implements transaction-level PostgreSQL advisory locking to serialize concurrent operations that threaten the active super admin population.

---

## 2. Original Bypass Reproduction
### Root Cause
In `server/app/api/admin/users.py`, the generic user update route `PUT /api/admin/users/{id}` originally placed administrator target checks exclusively inside the `if req.role is not None:` block:
```python
if req.role is not None:
    ...
    if (target_role in ADMIN_ROLES or user.role in ADMIN_ROLES) and current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can alter administrator roles.")
```
When a lower administrator (e.g. `support_admin`) sent a payload containing only `{"is_suspended": True}`:
1. `req.role` was `None`, so the role check block was completely bypassed.
2. The subsequent block `if req.is_suspended is not None:` checked only whether the target was the last active super admin and whether the caller was suspending themselves.
3. If two active super admins existed, the call succeeded with HTTP 200, allowing a lower-tier `support_admin` to suspend a `super_admin`.

### Local Reproduction Evidence
A focused reproduction test was executed against the unpatched source:
- Dedicated route `POST /api/admin/users/{super_admin.id}/suspend` rejected `support_admin` with HTTP 403 (`Only a Super Admin can suspend another Super Admin`).
- Generic route `PUT /api/admin/users/{super_admin.id}` with `{"is_suspended": True}` bypassed the check, returning HTTP 200 and setting `is_suspended = True` on the super admin.

---

## 3. Shared Policy Implementation
All actor-versus-target policy rules are centralized into [`server/app/services/admin_authorization_service.py`](file:///d:/TE%20-%20SEM%285%29/businessplanner/antigravitybusiness/BusinessArchitect/server/app/services/admin_authorization_service.py) via `validate_admin_mutation_target()` and `validate_session_revocation_target()`:

1. **Pre-mutation Evaluation**: Payloads are fully validated against the target's original role AND proposed final state before any field mutation is applied to the ORM model.
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

| Actor | Action / Route | Target: Ordinary User (`role='user'`) | Target: Administrator (`role in ADMIN_ROLES`, target != actor) | Target: Self (Actor == Target) |
|---|---|---|---|---|
| **Ordinary User** (`user`) | Any admin mutation route | 401 / 403 Forbidden | 401 / 403 Forbidden | 401 / 403 Forbidden |
| **Auditor** (`auditor`) | Any admin mutation route | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Operations Admin** (`operations_admin`) | Any admin mutation route | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Security Admin** (`security_admin`) | User mutations (`/api/admin/users/*`) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) | 403 (No `manage_users` permission) |
| **Security Admin** (`security_admin`) | Session revocation (`/api/admin/security/sessions/{id}/revoke`) | **200 Allowed** (has `revoke_sessions`) | **403 Forbidden** (cannot revoke other admin's session) | **200 Allowed** (self-session revocation) |
| **Security Admin** (`security_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **200 Allowed** (system-wide emergency kill-switch) | **200 Allowed** (system-wide emergency kill-switch) | Own current session preserved |
| **Support Admin** (`support_admin`) | `POST /api/admin/users` (create user) | **201 Allowed** (`role='user'`) | **403 Forbidden** (cannot create admin accounts) | N/A |
| **Support Admin** (`support_admin`) | `PUT /api/admin/users/{id}` (generic update) | **200 Allowed** (if new role is `'user'`; **403** if promoting to admin) | **403 Forbidden** (cannot modify any field of an admin) | **400** on self-suspend |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/suspend` | **200 Allowed** | **403 Forbidden** (cannot suspend an administrator) | **400 Bad Request** (cannot suspend own account) |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/reactivate` | **200 Allowed** | **403 Forbidden** (cannot reactivate an administrator) | N/A |
| **Support Admin** (`support_admin`) | `POST /api/admin/users/{id}/revoke-sessions` | **200 Allowed** | **403 Forbidden** (cannot revoke an administrator's sessions) | N/A (can use self-service `/api/admin/auth/sessions`) |
| **Support Admin** (`support_admin`) | `DELETE /api/admin/users/{id}` | **200 Allowed** | **403 Forbidden** (cannot delete an administrator) | **400 Bad Request** (cannot delete own account) |
| **Super Admin** (`super_admin`) | `POST /api/admin/users` (create user) | **201 Allowed** | **201 Allowed** | N/A |
| **Super Admin** (`super_admin`) | `PUT /api/admin/users/{id}` (generic update) | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **200 Allowed** (subject to invariant, **400** on self-suspend) |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/suspend` | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **400 Bad Request** (cannot suspend own account) |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/reactivate` | **200 Allowed** | **200 Allowed** | N/A |
| **Super Admin** (`super_admin`) | `POST /api/admin/users/{id}/revoke-sessions` | **200 Allowed** | **200 Allowed** | **200 Allowed** |
| **Super Admin** (`super_admin`) | `DELETE /api/admin/users/{id}` | **200 Allowed** | **200 Allowed** (subject to last-active-super-admin invariant) | **400 Bad Request** (cannot delete own account) |
| **Super Admin** (`super_admin`) | Session revocation (`/api/admin/security/sessions/{id}/revoke`) | **200 Allowed** | **200 Allowed** | **200 Allowed** |
| **Super Admin** (`super_admin`) | Global session revocation (`/api/admin/security/sessions/revoke-all`) | **200 Allowed** | **200 Allowed** | Own current session preserved |

---

## 5. Last-Active-Super-Admin Invariant Algorithm
An account is an "active super admin" if:
$$\text{active\_super} = (\text{role} == \text{"super\_admin"} \land \lnot \text{is\_suspended})$$

For any mutation:
1. Target current status: $\text{current\_active\_super} = (\text{target.role} == \text{"super\_admin"} \land \lnot \text{target.is\_suspended})$.
2. Target proposed status:
   - For deletion: $\text{proposed\_active\_super} = \text{False}$.
   - For suspension: $\text{proposed\_active\_super} = \text{False}$.
   - For update: $\text{final\_role} = \text{req.role} \mathbin{??} \text{target.role}$, $\text{final\_suspended} = \text{req.is\_suspended} \mathbin{??} \text{target.is\_suspended}$. $\text{proposed\_active\_super} = (\text{final\_role} == \text{"super\_admin"} \land \lnot \text{final\_suspended})$.
3. Population check trigger:
   If $\text{current\_active\_super} \land \lnot \text{proposed\_active\_super}$ is $\text{True}$, the mutation reduces the active super admin population.
4. Serialized count check:
   - In PostgreSQL, acquires transaction-level advisory lock `pg_advisory_xact_lock(6004834884214473805)`.
   - Expires session cache (`db.expire_all()`) to guarantee fresh state.
   - Queries `active_count = count(User.role == 'super_admin' and User.is_suspended == False)`.
   - If $\text{active\_count} \le 1$, rejects the request with HTTP 400.
5. Deletion fix: Previous deletion logic counted all super admins including suspended accounts. It now correctly evaluates only active accounts. Deleting an already suspended super admin does not reduce the active count and succeeds if at least one active super admin remains.

---

## 6. Concurrency Mechanism and Transaction Boundaries
1. **Advisory Lock Key**: Constant `SUPER_ADMIN_INVARIANT_LOCK_KEY = 6004834884214473805` (ASCII representation of `'SUPERADM'`).
2. **Lock Order**:
   - `pg_advisory_xact_lock` is acquired before the authoritative count query.
   - Stale ORM objects are refreshed via `db.expire_all()`.
   - The lock is held through account mutation commit (`db.commit()`), which automatically releases the transaction-scoped advisory lock in PostgreSQL.
3. **Deadlock Prevention**: All invariant-critical routes acquire the identical advisory lock key in uniform order, completely preventing mutual cross-lock deadlocks between administrators concurrently targeting each other.
4. **Ordinary Operations Unaffected**: Operations on ordinary users or non-reducing administrative mutations do not acquire the lock, keeping normal operations unblocked.
5. **Telemetry Boundary**: Telemetry helpers (`record_audit_log`, `record_security_event`) are invoked only after the mutation transaction commits, ensuring telemetry helpers never prematurely release the invariant lock or commit unverified partial states.

---

## 7. SQLite vs. PostgreSQL Coverage
- **SQLite (Automated Test Suite)**:
  - SQLite executes queries within a single database file with connection-level serialization.
  - Advisory lock calls gracefully detect dialect `sqlite` and avoid invoking PostgreSQL-specific functions.
  - 21 focused unit and integration tests verify the authorization matrix, bypass resistance, and invariant rules under SQLite.
- **PostgreSQL (Production Concurrency Guard)**:
  - Production Supabase runs PostgreSQL 15+, which fully supports `pg_advisory_xact_lock`.
  - A dedicated concurrency test `test_postgresql_concurrent_super_admin_removal` tests two concurrent threads/connections attempting simultaneous removal of two active super admins.
  - When `TEST_POSTGRES_URL` is configured, it executes the multi-threaded race test and asserts that at most one removal succeeds. In local environments lacking a disposable PostgreSQL instance, the test cleanly skips with an explicit notice.

---

## 8. API Compatibility
- No existing public or admin endpoints were removed or changed in URL structure.
- HTTP status codes and error shapes remain standard (`400 Bad Request`, `403 Forbidden`, `404 Not Found`).
- Legitimate support actions for ordinary users remain fully operational.
- CSRF verification, session cookies, and security telemetry remain intact.
