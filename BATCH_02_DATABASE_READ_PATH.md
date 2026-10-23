# BATCH 02 — AUTHENTICATED READ-PATH AND DATABASE ROUND-TRIP OPTIMIZATION

**Repository:** `https://github.com/hannyjangir1-commits/BusinessArchitect`
**Execution Timestamp:** 2026-10-23T15:10:00Z
**Branch:** `main`
**Deployment Status:** Batch 02 was pushed to main but has not been deployed because Render auto-deploy is disabled.
**Production Safety:** No production data was modified.
**Scope:** Batch 02 Only (Authenticated Activity Write Throttling, Maintenance Mode In-Process TTL Cache, Project Listing N+1 Query Elimination, Module Version Payload Deferral).

---

## 1. Starting Commit
- **Commit SHA:** `a172572b46dc3d55feb9134f9a5e1b15cc62fee0`
- **Summary:** `perf: add safe request and database timing diagnostics` (Batch 01 verified deployment baseline)

---

## 2. Ending Commit
- **Batch 02 Initial Commit:** `1ffe1cdfa098382f027cdeb67e6c840624822911` (`perf: reduce authenticated database round trips`)
- **Review Gate Hardening Commit:** To be recorded upon push (`fix: harden database read-path optimizations`)
- **Target Branch:** `main`

---

## 3. Files Changed
1. `BATCH_01_PERFORMANCE_BASELINE.md`:
   - Updated latency interpretation to qualify network overhead without asserting fixed per-query latency.
   - Added Section I Addendum recording the verified manual deployment of `a172572` and production baseline summary.
2. `server/app/core/config.py`:
   - Added bounded configuration setting `USER_ACTIVITY_THROTTLE_SECONDS: int` (default: 600, range: 60–86400).
3. `.env.example`:
   - Documented `USER_ACTIVITY_THROTTLE_SECONDS=600`.
4. `server/app/api/deps.py`:
   - Implemented write-throttling for `user.last_active_at`: updates and commits now execute only when `now - last_active_at >= USER_ACTIVITY_THROTTLE_SECONDS`.
   - Read requests inside the throttle window execute 0 writes and 0 commits.
5. `server/app/services/system_setting_service.py`:
   - Implemented thread-safe, bounded in-process TTL cache (`get_maintenance_mode_cached`, `invalidate_maintenance_mode_cache`, `reset_maintenance_mode_cache`).
   - Wired immediate cache invalidation inside `set_setting` when `key == "maintenance_mode"`.
6. `server/app/api/admin/maintenance.py`:
   - Wired immediate cache invalidation on administrative `toggle_maintenance_mode`.
7. `server/app/api/admin/config.py`:
   - Wired immediate cache invalidation in `update_system_config` when `maintenance_mode` is modified.
8. `server/app/main.py`:
   - Updated `maintenance_mode_middleware` to use `get_maintenance_mode_cached()`, eliminating 1 synchronous database query per request.
9. `server/app/api/projects.py`:
   - Replaced per-project loops with batched $O(1)$ query aggregation in `_format_projects_batch`.
   - Uses a single grouped query for roadmap task counts and a single projection query for module types across all project IDs.
   - Handled empty project lists cleanly without emitting `IN ()`.
10. `server/app/services/version_service.py`:
    - Added `get_version_metadata` using SQLAlchemy `load_only` to exclude heavy `data` JSON payloads during version list generation.
    - Updated `get_versions` to support `include_data: bool = True`.
11. `server/app/api/modules.py`:
    - Updated `get_module` to load version list history with `get_version_metadata`, ensuring inactive version payloads are never queried or transferred.
12. `server/scripts/run_baseline_measurements.py`:
    - Extended local repeatable benchmark harness to cover single-version vs multi-version modules and warm throttled auth reads.
13. `server/tests/test_batch_02_read_path_optimizations.py`:
    - Added 13 exhaustive unit, boundary, concurrency, and regression tests.

---

## 4. Activity-Throttling Design
- **Mechanism:** When `get_current_user` validates a session token against `sessions` and resolves `users`, it inspects `user.last_active_at`.
- **Condition:** If `now - user.last_active_at < USER_ACTIVITY_THROTTLE_SECONDS`, the timestamp is left unchanged, and `db.commit()` is completely bypassed.
- **Security & Authorization Invariants:**
  - Session existence and cryptographic token matching remain validated on 100% of requests.
  - Session expiration (`sess.expires_at < now`) is strictly enforced on every request.
  - Account suspension (`user.is_suspended`) is strictly enforced on every request.
  - No authorization or permission data is cached in memory.
  - Race conditions between concurrent requests arriving near the boundary are harmless (both write `now` idempotently).

---

## 5. Maintenance-Cache Design
- **Structure:** Process-local, bounded state storing `_cached_maintenance_value: Optional[bool]` and `_cached_maintenance_expiry: float` (monotonic timestamp).
- **Concurrency & Non-Blocking Event Loop:**
  - Maintenance-cache refresh does not block the event loop: verified through deterministic async concurrency testing with a synthetic 200 ms slow refresh, where `/health/live` completed in < 10 ms without waiting for the maintenance database lookup.
  - The in-memory cache fast-path inspects state without locking or DB queries.
  - On a cache miss, database I/O is offloaded to a worker thread via `asyncio.to_thread` so the ASGI event loop remains completely unblocked.
  - Crucially, no `threading.Lock` is held while performing remote database I/O. The lock's critical section is limited strictly to sub-microsecond in-memory assignments.
  - Synchronous database sessions are created, used, and closed entirely within the worker-thread operation.
- **TTL:** 30.0 seconds.
- **Fail-Open Policy:** If the database query raises an exception during refresh, the cache returns the last known value or `False` without poisoning the cache or blocking user traffic.
- **Invalidation Triggers:**
  - `POST /api/admin/maintenance/toggle`
  - `PUT /api/admin/config` (when updating `maintenance_mode`)
  - Direct `set_setting(db, "maintenance_mode", ...)` invocations
- **Multi-Worker Note:** In multi-process deployments, this cache is per-process; manual admin changes take effect immediately on the worker handling the request and within $\le 30$ seconds across sibling workers.

---

## 6. Project Batching Design
- **Problem Solved:** Previously, `_format_project_response` executed 2 queries per project ($6 + 2N$ SQL statements).
- **New Architecture:**
  1. Single query for user projects: `SELECT ... FROM projects WHERE user_id = ? ORDER BY updated_at DESC`.
  2. If projects is empty, returns `[]` immediately without issuing secondary queries.
  3. Batched task count query: Single query grouping `RoadmapTask.project_id`, `count(id)`, and `sum(case(status in ('Finished', 'Completed')))` filtered by `project_id.in_(project_ids)`.
  4. Batched module query: Single projection query selecting `project_id, module_type` from `module_contents` where `project_id.in_(project_ids)` and `active_version_id IS NOT NULL`.
  5. Combination: Merged in Python memory into `ProjectResponse` models preserving project order.
- **Complexity:** $O(1)$ constant SQL statements regardless of project portfolio size.

---

## 7. Version Metadata-Loading Design
- **Problem Solved:** When viewing a module, `VersionService.get_versions` previously fetched the entire `data` JSON column (often 20–100 kB per version) for all 5 versions in history, even though the API response only requires version metadata (`id`, `version_number`, `version_name`, `change_summary`, `is_active`, `created_at`).
- **New Architecture:**
  - `VersionService.get_version_metadata` employs SQLAlchemy `load_only(...)` to explicitly project only metadata columns.
  - The heavy `data` column is loaded solely for the active version required by `current_module_data`.
  - Inactive version data payloads are never transferred across the database connection or deserialized into memory.
  - A SQLAlchemy `load_only()` projection was verified through fully serialized endpoint testing. Capturing all executed SQL statements during the request demonstrated that inactive version `data` JSON payloads are absent from the query projection, and no follow-up lazy-load queries are issued during response serialization.

---

## 8. Before-and-After SQL Statement Counts

Measured using `server/scripts/run_baseline_measurements.py` on disposable SQLite instance with `PERF_DIAGNOSTICS=true`:

| Endpoint | State / Scenario | Batch 01 (Before) | Batch 02 (After) | Statement Delta |
|---|---|:---:|:---:|:---:|
| `GET /health/live` | Process Liveness | 0 | **0** | No change (Decoupled) |
| `GET /api/auth/me` | Session Check (Initial / Cold) | 5 | **3** | **-2 statements (-40%)** |
| `GET /api/auth/me` | Session Check (Warm / Recent) | 5 | **2** | **-3 statements (-60%)** |
| `GET /api/projects` | Project Listing (0 Projects) | 6 | **3** | **-3 statements (-50%)** |
| `GET /api/projects` | Project Listing (1 Project) | 8 | **5** | **-3 statements (-37%)** |
| `GET /api/projects` | Project Listing (10 Projects) | 26 | **5** | **-21 statements (-81%)** |
| `GET /api/projects/{id}/modules/tech_stack` | Module Read (1 Version) | 10 | **8** | **-2 statements (-20%)** |
| `GET /api/projects/{id}/modules/bmc` | Module Read (5 Versions) | 10 | **8** | **-2 statements (-20%)** |
| `GET /api/projects/{id}/tasks/summary` | Task Summary (Regression Control) | 7 | **4** | **-3 statements (-43%)** |
| `GET /api/projects/{id}/copilot` | Copilot History (Regression Control) | 7 | **4** | **-3 statements (-43%)** |

---

## 9. Before-and-After Commit Counts

| Endpoint | State / Scenario | Batch 01 Commits | Batch 02 Commits | Commit Delta |
|---|---|:---:|:---:|:---:|
| `GET /api/auth/me` | Warm Authenticated Read | 1 | **0** | **-1 commit (100% write eliminated)** |
| `GET /api/projects` | Warm Project Listing | 1 | **0** | **-1 commit (100% write eliminated)** |
| `GET /api/projects/{id}/modules/*` | Warm Module Read | 1 | **0** | **-1 commit (100% write eliminated)** |
| `GET /api/projects/{id}/tasks/summary` | Warm Task Summary Read | 1 | **0** | **-1 commit (100% write eliminated)** |
| `GET /api/projects/{id}/copilot` | Warm Copilot History Read | 1 | **0** | **-1 commit (100% write eliminated)** |

---

## 10. Test Results
- **Batch 01 Diagnostics & Baseline Suite:** 13 passed, 0 failed (`pytest server/tests/test_batch_01_diagnostics_and_baseline.py`).
- **Batch 02 Read-Path Optimizations Suite:** 15 passed, 0 failed (`pytest server/tests/test_batch_02_read_path_optimizations.py`).
- **Complete Backend Test Suite:** 232 passed, 4 skipped, 0 failed in 29.61s (`pytest server/tests`).
- **Frontend Vitest Suite:** 39 passed in 7 test files (`npm test` in `client/`).
- **Frontend Production Build:** Built cleanly in 455ms (`npm run build` in `client/`).
- **Database Migrations:** Schema remains at `e6b30f8a2c19 (head)` with 0 schema migrations required.
- **Git Whitespace:** `git diff --check` clean with 0 whitespace issues.

---

## 11. Limitations
- `get_maintenance_mode_cached` operates in-process; across separate Uvicorn worker processes or scaling instances, updates synchronize within the 30-second TTL window rather than via distributed pub-sub.
- `USER_ACTIVITY_THROTTLE_SECONDS` relies on process system clocks (`datetime.now(timezone.utc)` and DB timestamps).
- If a project contains hundreds of tasks, grouping by project ID in SQL aggregates counts efficiently, but does not alter the write path of task generation.

---

## 12. Deferred Work (Out of Scope for Batch 02)
- Database connection pool changes (`NullPool` vs `QueuePool` on port 6543 / 5432) — deferred to connection batch.
- Decoupling database sessions from external Gemini provider calls in `module_orchestration_service.py` and `copilot.py` — deferred to Batch 03.
- Unsafe repair logic in `version_service.py` (`repair_missing_active_versions`) — deferred to dedicated version-safety batch.
- Static asset compression and CDN caching — deferred to static asset batch.

---

## 13. Expected Production Impact
- Query reduction predicts improvement but production latency has not been measured yet.
- On remote Supabase connections where every database round-trip over Singapore $\leftrightarrow$ Mumbai carries network latency, reducing statement counts from 26 to 5 on project listing eliminates 21 sequential round-trips.
- Eliminating the write transaction (`last_active_at` commit) on every read eliminates ACID commit wait time on warm read operations.
- The maintenance cache eliminates 1 round trip on every user-facing API request. Production impact will be measured after authorized manual deployment.

---

## 14. Manual Deployment Checklist
1. Render auto-deploy must remain disabled.
2. Verify local tests and git status before push.
3. Commit message: `perf: reduce authenticated database round trips`.
4. Push `main` to `origin/main`.
5. Verify deployed commit SHA on Render matches the exact commit before approving manual deploy.
6. Trigger manual deployment in Render Dashboard only upon explicit master reviewer authorization.
