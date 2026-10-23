# BATCH 01 — PERFORMANCE BASELINE, SAFE DIAGNOSTICS & SUPABASE CONNECTION INSPECTION

**Repository:** `https://github.com/hannyjangir1-commits/BusinessArchitect`  
**Execution Timestamp:** 2026-10-23T12:26:00Z  
**Branch:** `perf/01-observability-connection-baseline`  
**Scope:** Batch 01 Only (Performance Baseline, Non-Intrusive Observability, Safe Health Endpoints, Database Connection Inspection).  

---

## A. Repository State

- **Starting Commit:** `8594eff88f62bf3238a509bd382e379208cea5a2` (`Update test_deployment_and_supabase_readiness.py`)
- **Working Branch:** `perf/01-observability-connection-baseline`
- **Initial Working Tree Status:** Clean (verified with `git status --short`).
- **Files Modified / Created in Batch 01:**
  - `server/app/core/diagnostics.py` (New safe request correlation, stage timing, SQL counter context, and connection classification module)
  - `server/scripts/run_baseline_measurements.py` (New repeatable local baseline measurement harness)
  - `server/tests/test_batch_01_diagnostics_and_baseline.py` (New unit & regression tests covering 14 requirements)
  - `server/app/core/config.py` (Added `PERF_DIAGNOSTICS` configuration flag)
  - `.env.example` (Documented `PERF_DIAGNOSTICS=false`)
  - `server/app/main.py` (Added outer `diagnostics_middleware`, protected `/health/live` from DB/maintenance, updated readiness wording to avoid unprobed `"ready"` claims, added `/api/health/live`)
  - `server/app/db/session.py` (Registered SQL diagnostics event listeners on the engine)
  - `server/app/api/deps.py` (Instrumented `auth_lookup` and `auth_activity_write` stages)
  - `server/app/api/projects.py` (Instrumented `project_query` and `project_metadata_query` stages)
  - `server/app/api/modules.py` (Instrumented `module_query` and `version_metadata_query` stages)
  - `server/app/api/copilot.py` (Instrumented `provider_call` stage)
  - `server/app/services/module_orchestration_service.py` (Instrumented `provider_call` stage)

---

## B. Architecture Findings

1. **Current Middleware Order:**
   - Starlette/FastAPI executes middlewares in reverse declaration order.
   - Outer layer: `CORSMiddleware` (ASGI middleware registered via `app.add_middleware`).
   - Outer HTTP layer: `diagnostics_middleware` (handles incoming correlation ID, monotonic request start, and Server-Timing header injection).
   - Inner HTTP layer: `maintenance_mode_middleware` (inspects `/health/live` exemption before querying DB).
   - Route handlers.
2. **Authentication Database Behavior:**
   - Every authenticated API request invoking `get_current_user` in `server/app/api/deps.py` queries `sessions`, queries `users`, and synchronously updates `user.last_active_at = now` followed by `db.commit()`.
   - On remote databases (Render Singapore &rarr; Supabase `ap-south-1`), this forces multiple synchronous network round-trips plus an ACID write transaction commit before the endpoint logic executes.
3. **Maintenance Lookup Behavior:**
   - `maintenance_mode_middleware` executes `SessionLocal()` to read `system_settings.maintenance_mode` synchronously on every non-exempted user-facing request.
   - It possesses no in-memory TTL caching, forcing another database round-trip before routing.
4. **Engine and Pool Selection Logic:**
   - In `server/app/db/session.py`:
     - URLs containing `:6543` select `NullPool` (PgBouncer transaction pooler mode).
     - Standard URLs select `QueuePool` with `pool_size=5`, `max_overflow=10`, `pool_recycle=300`.
     - `pool_pre_ping=True` is enabled globally. On `NullPool`, this forces a fresh TCP/SSL handshake and a `SELECT 1` pre-ping on every single checkout.
5. **Health Endpoint Dependencies:**
   - `/health/live` is a pure process-liveness probe returning immediately with zero database queries, zero auth checks, zero Gemini probes, and zero maintenance checks.
   - `/health` is a container readiness probe verifying local database connectivity via `SELECT 1`.
   - `/api/health` reports status, database connectivity, and configuration state without executing real LLM generation calls.
6. **Startup Migration Behavior:**
   - `Dockerfile` runs `alembic upgrade head && exec uvicorn ...`.
   - Cold starts on Render Free must complete all Alembic checks over remote SSL before Uvicorn binds port 8000.
7. **Places Where Sessions Span External Provider Calls:**
   - In `server/app/services/module_orchestration_service.py` (`execute_module_generation`) and `server/app/api/copilot.py` (`send_chat_message`), the `db: Session` dependency remains open and holds an active database connection while waiting for external Gemini network HTTPS calls (which take 5–30 seconds).

---

## C. Sanitized Database Configuration

Classified using `classify_database_connection()`:

```text
driver: postgresql+psycopg
endpoint_category: supabase_transaction_pooler
port: 6543
pool_class: NullPool
pool_size: not_applicable
max_overflow: not_applicable
pool_recycle: not_applicable
pool_pre_ping: true
ssl_configured: true
connect_timeout_seconds: unset
statement_timeout_seconds: unset
installed_pg_drivers: ['psycopg_v3', 'psycopg2_v2']
both_driver_families_required: true
```

*Note: All credentials, passwords, usernames, full hostnames, project references, and URL parameters have been strictly excluded.*

---

## D. Baseline Table

Captured via `server/scripts/run_baseline_measurements.py` using isolated, disposable SQLite storage with `PERF_DIAGNOSTICS=true`:

| Endpoint | Dataset | Status | SQL statements | Commits | Response bytes | Local duration | Environment |
|---|---:|---:|---:|---:|---:|---:|---|
| `GET /health/live` | Process Liveness | 200 | 0 | 0 | 77 B | 3.0 ms | Disposable SQLite (Local) |
| `GET /api/auth/me` | Session / Auth Check | 200 | 5 | 1 | 245 B | 27.7 ms | Disposable SQLite (Local) |
| `GET /api/projects` | Project Listing (0 Projects) | 200 | 6 | 1 | 2 B | 24.1 ms | Disposable SQLite (Local) |
| `GET /api/projects` | Project Listing (1 Project) | 200 | 8 | 1 | 764 B | 19.2 ms | Disposable SQLite (Local) |
| `GET /api/projects` | Project Listing (10 Projects) | 200 | 26 | 1 | 5383 B | 20.3 ms | Disposable SQLite (Local) |
| `GET /api/projects/{id}/modules/bmc` | Module Detail (3 Versions) | 200 | 10 | 1 | 829 B | 32.2 ms | Disposable SQLite (Local) |
| `GET /api/projects/{id}/tasks/summary` | Task Summary | 200 | 7 | 1 | 287 B | 20.7 ms | Disposable SQLite (Local) |
| `GET /api/projects/{id}/copilot` | Copilot History | 200 | 7 | 1 | 651 B | 16.7 ms | Disposable SQLite (Local) |

### Key Diagnostic Observations from Baseline:
1. **/health/live is completely decoupled:** Exactly 0 SQL statements and 0 commits.
2. **Every authenticated request incurs a write transaction:** `/api/auth/me` executes 5 statements and 1 commit due to `last_active_at` updates.
3. **Severe N+1 query amplification confirmed in project listing:**
   - 0 Projects: 6 statements (Auth + Maintenance + Project query).
   - 1 Project: 8 statements (+2 child queries for RoadmapTask and ModuleContent).
   - 10 Projects: 26 statements ($6 + 2 \times 10$ child queries).
   - In the observed production probe, an endpoint that created a fresh remote database connection and executed SELECT 1 was materially slower than zero-database liveness endpoints. The measurement combines client-to-Render latency, connection establishment, TLS, pooler behavior, query execution and response transfer. It does not isolate a universal per-statement cost. However, executing 26 sequential round-trips under `NullPool` multiplies connection and round-trip overhead directly with project count.

---

## E. Changes Made

1. **`server/app/core/diagnostics.py`**
   - *Before:* No dedicated diagnostics, request correlation, or timing module.
   - *After:* Adds request-local correlation ID generation/sanitization, monotonic stage timing (`record_stage`), non-intrusive SQLAlchemy statement/commit event listeners, RFC-compliant `Server-Timing` headers, and sanitized database inspection.
   - *Safety:* No DB writes, no external logging network calls, thread/task-local via `ContextVar`, zero parameters logged.
   - *Covered by:* `test_batch_01_diagnostics_and_baseline.py`.

2. **`server/app/main.py`**
   - *Before:* No correlation ID or request timing middleware. Health endpoints claimed `"ready"` without probing. Maintenance check ran if trailing slash was present on liveness.
   - *After:* Added `diagnostics_middleware` injecting `X-Request-ID` and `Server-Timing`. Strictly exempted all liveness paths from DB maintenance checks. Labeled unprobed Gemini readiness as `"configured"`, `"cooldown_active"`, or `"unconfigured"`.
   - *Safety:* Preserves existing API response schemas and contracts.
   - *Covered by:* `test_health_live_performs_no_database_queries`, `test_readiness_wording_accurate`, `test_server_timing_configuration`.

3. **`server/app/core/config.py` & `.env.example`**
   - *Before:* No `PERF_DIAGNOSTICS` variable existed.
   - *After:* Added `PERF_DIAGNOSTICS: bool` defaulting to `False`. Documented safe usage in `.env.example`.
   - *Safety:* Safe boolean fallback; no credentials exposed.
   - *Covered by:* `test_diagnostics_disabled_behavior`.

4. **`server/app/db/session.py`**
   - *Before:* Engine created without statement-level diagnostics listeners.
   - *After:* Calls `register_sql_diagnostics_listeners(engine)` once on startup.
   - *Safety:* Listeners execute only when an active request context has `diag.enabled=True`; no-op during migrations or background work.
   - *Covered by:* `test_concurrent_sql_counters_isolation`.

5. **`server/app/api/deps.py`, `projects.py`, `modules.py`, `copilot.py`, `module_orchestration_service.py`**
   - *Before:* No granular stage tracking.
   - *After:* Instrumented with `record_stage(...)` for `auth_lookup`, `auth_activity_write`, `project_query`, `project_metadata_query`, `module_query`, `version_metadata_query`, and `provider_call`.
   - *Safety:* Zero-overhead no-op when diagnostics are disabled.
   - *Covered by:* `test_server_timing_metric_names_allowlist`.

---

## F. Test Results

### 1. Backend Test Suite (Pytest)
```text
Command: pytest server/tests
Result: 217 passed, 4 skipped, 40 warnings in 35.42s (100% PASS)
```
- Includes 13 focused Batch 01 tests in `test_batch_01_diagnostics_and_baseline.py`.
- Includes all regression, admin, CSRF, and end-to-end catalogue tests.

### 2. Frontend Test Suite (Vitest)
```text
Command: npm test (in client/)
Result: 7 test files passed, 39 tests passed in 27.94s (100% PASS)
```

### 3. Frontend Production Build
```text
Command: npm run build (in client/)
Result: tsc -b && vite build completed cleanly in 905ms (0 errors).
```

### 4. Migration Status
```text
Command: alembic heads
Result: e6b30f8a2c19 (head)
```

### 5. Git Diff & Whitespace Verification
```text
Command: git diff --check
Result: Clean (0 whitespace errors, 0 trailing blank lines).
```

---

## G. Unresolved Findings

1. **Confirmed Source Defects (Deferred to Batch 02):**
   - **N+1 Queries in Project Listing:** `_format_project_response` executes 2 queries per project row. Needs bulk prefetching (`in_`) or single aggregate query.
   - **Frequent Activity Writes:** `user.last_active_at` is updated and committed on every single authenticated request. Should be throttled with a 5-minute memory/cache threshold.
   - **Uncached Maintenance Checks:** `maintenance_mode_middleware` queries the database on every non-exempted request. Needs a 30-second in-memory TTL cache.
   - **Full Version Data Overfetch:** `VersionService.get_versions` loads full `data` JSON columns when only version metadata (`id`, `version_number`, `version_name`, `is_active`, `created_at`) is needed for module headers.
   - **Open DB Sessions Across External AI Calls:** `execute_module_generation` and `copilot` hold active database transactions open during multi-second Gemini API calls.
2. **Production-Configuration Unknowns:**
   - Exact ping RTT between Render's container in Singapore and Supabase pooler host `aws-0-ap-south-1.pooler.supabase.com`.
   - Render Free container memory pressure during heavy SPA serving.

---

## H. Batch 02 Recommendations

1. **Resolve N+1 Queries in `list_projects`:**
   - In `server/app/api/projects.py`, prefetch all roadmap tasks and module contents for `user_project_ids` using two `IN (...)` queries, grouping them in memory in Python rather than issuing 2 queries per project.
2. **Throttle `last_active_at` Database Commits:**
   - In `server/app/api/deps.py`, only update and commit `user.last_active_at` if `now - user.last_active_at > timedelta(minutes=5)`.
3. **Add In-Memory TTL Cache for Maintenance Mode:**
   - In `server/app/services/system_setting_service.py`, cache `maintenance_mode` in memory with a 30-second TTL to eliminate 1 query on every request.
4. **Deferred Version Column Loading:**
   - Use SQLAlchemy `load_only("id", "version_number", "version_name", "is_active", "created_at")` in `VersionService.get_versions` to prevent transferring full JSON payloads when reading version history.
5. **Release Database Session Across External Provider Calls:**
   - Read context and close or commit the DB session before calling `ai_service`, reopening a short session only to persist the generated result.

---

## I. Release Gate Addendum & Verified Deployment Status

- **Deployment Statement:**
  Batch 01 commit `a172572b46dc3d55feb9134f9a5e1b15cc62fee0` was pushed to `main` and manually deployed to the Singapore Render service. No production application data was modified by the baseline measurements.

- **Latency Interpretation:**
  In the observed production probe, an endpoint that created a fresh remote database connection and executed SELECT 1 was materially slower than zero-database liveness endpoints. The measurement combines client-to-Render latency, connection establishment, TLS, pooler behavior, query execution and response transfer. It does not isolate a universal per-statement cost.

- **Verified Production Baseline Summary (Live Singapore Service):**
  - `GET /health/live`: Median 480.4 ms (0 SQL, 0 commits).
  - `GET /api/health/live`: Median 431.8 ms (0 SQL, 0 commits).
  - `GET /api/health`: Median 1,177.2 ms (1 SQL `SELECT 1`, 0 commits).
  - `GET /`: Median 381.1 ms (Static SPA entry point).
