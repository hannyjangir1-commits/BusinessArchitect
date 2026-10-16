# BusinessArchitect repository audit

**Repository:** [hannyjangir1-commits/BusinessArchitect](https://github.com/hannyjangir1-commits/BusinessArchitect)  
**Branch:** `main` (default branch)  
**Snapshot audited:** `455719bd1ba04290ff36fbcaf71c3461f6f8424a`  
**Audit date:** 2026-10-16  
**Method:** read-only source and configuration review using the connected GitHub repository tools.

## Executive summary

The snapshot has **one confirmed release-blocking defect**: the backend imports a Pydantic schema that references `Optional` without importing it, so Python raises `NameError` while loading the application. The API process cannot start until that is corrected.

There are also **two high-severity security issues**: the app can bootstrap a super-admin with a known fallback password if deployment credentials are absent, and server-side admin routes generally check only “is any admin” instead of enforcing the role-specific permissions advertised to each account.

The most significant additional defects affect the admin dashboard on a fresh database, settings that appear editable but do not change runtime behavior, roadmap/version consistency, project copying, and dashboard actions. I found no obvious missing third-party packages or frontend import targets from static inspection; the client lockfile matches its manifest.

## Snapshot and verification limits

The GitHub tree at the audited commit contains **180 tracked blobs**. I fetched all **146 text files** (application source, tests, manifests, configuration, docs, and test-result JSON) and checked the source references below against the pinned commit. The other 34 blobs are image assets/screenshots and were excluded from text-source review.

GitHub reports no Actions workflow runs for the commit and no commit status checks. There is no `.github/` workflow path in the tree. I did not run the local Python or Node test/build commands: this workspace did not contain a repository checkout or its installed dependencies, and the repository was not modified or populated locally. Findings below are therefore based on static source evidence; runtime behavior and database-specific behavior were not independently exercised.

**Confidence labels:** High means the source path establishes the behavior directly. Medium means the failure depends on runtime state, concurrency, or an expected product behavior that is not fully specified.

## Findings

### F-01 — Critical — Backend import fails before application startup

**Confidence: High · Confirmed defect**

[`server/app/schemas/auth.py:1-3`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/schemas/auth.py#L1) imports `re`, `datetime`, and Pydantic symbols, but not `typing.Optional`. The same file uses `Optional[str]` in the `UserProfileUpdateRequest` annotations at [lines 49-55](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/schemas/auth.py#L49). There is no postponed-annotation import. When Python defines that class it evaluates `Optional` and raises `NameError`.

[`server/app/main.py:12-13`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/main.py#L12) imports the auth API module before creating the FastAPI app. That module imports the affected schemas at [`server/app/api/auth.py:8-13`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/auth.py#L8). Consequently Uvicorn cannot import `app.main:app`; the API and the combined web service do not start. The backend tests also import `app.main` (for example [`server/tests/test_auth_and_projects.py:3-6`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/tests/test_auth_and_projects.py#L3)), so they are expected to fail during collection for the same reason.

**Action:** import `Optional` (or use supported postponed annotations) and then run the backend import, tests, and deployment build.

### F-02 — High — Bootstrap can create a super-admin with a public, known password

**Confidence: High for code behavior; deployment exposure depends on environment configuration · Security risk**

[`server/app/core/config.py:33-36`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/core/config.py#L33) falls back to username `HannyAdmin`, password `Hanny@BusinessArchitect`, and a fixed internal email when the corresponding environment variables are absent. [`server/app/core/admin_provisioning.py:18-34`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/core/admin_provisioning.py#L18) uses those nonempty values, and [`server/app/main.py:19-28`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/main.py#L19) invokes provisioning on every application startup.

The `ADMIN_BOOTSTRAP_ENABLED` flag appears in [`.env.example:18-21`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/.env.example#L18) and the README, but a repository-wide search found no application-code read of it. Setting it to `false` therefore does not disable provisioning. The Render blueprint marks only `INITIAL_ADMIN_PASSWORD` as an unsynced variable at [`render.yaml:21-28`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/render.yaml#L21); if the deployment is started without supplying it, the fallback remains active. The README also says plaintext bootstrap credentials are never committed, while documenting the default password at [`README.md:237-245`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/README.md#L237).

**Action:** remove the usable password fallback, fail closed when a required bootstrap secret is missing, and make the enable/disable setting effective. Confirm production has a unique secret and rotate any account that may have used the fallback.

### F-03 — High — Most admin API routes do not enforce role-specific permissions

**Confidence: High · Confirmed authorization defect**

[`server/app/api/admin/auth.py:67-84`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/auth.py#L67) returns distinct permission lists for `super_admin`, `operations_admin`, `security_admin`, `support_admin`, and `auditor`. However, [`server/app/api/deps.py:72-117`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/deps.py#L72) defines `require_admin` as a membership check against the broad admin-role set; its `require_roles` helper is not used by the route modules. Most handlers across `server/app/api/admin/` use only `Depends(require_admin)`. For example, user-management actions use that guard in [`users.py:164-168`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/users.py#L164), and integrity repair uses it in [`integrity.py:127-132`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/integrity.py#L127). The AI retry route has a manual role check, but that is the exception ([`ai_ops.py:177-192`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/ai_ops.py#L177)).

This lets a role whose advertised permissions are read-only or narrower call endpoints such as account suspension/deletion, configuration changes, and data repairs directly. The frontend also passes the role into the sidebar as `_adminRole` and does not use it to filter navigation ([`AdminSidebar.tsx:30-36`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/admin/AdminSidebar.tsx#L30)).

**Action:** enforce permissions on each API operation (including object-level restrictions for sensitive actions); treat frontend navigation filtering as usability only, not as access control.

### F-04 — Medium — Admin dashboard raises an exception when the selected period has no AI operations

**Confidence: High · Confirmed defect for zero-operation periods**

[`server/app/api/admin/dashboard.py:102-103`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/dashboard.py#L102) assigns `None` to `failure_rate` when the count is zero. At [line 149](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/dashboard.py#L149), it compares `failure_rate > 20.0` before checking whether there are at least five operations. In Python, `None > 20.0` raises `TypeError`. A new installation, or a selected date range with no AI operations, therefore returns a server error from the dashboard stats route.

**Action:** guard the comparison when the rate is absent, or use a numeric zero for the empty case.

### F-05 — Medium — Several admin configuration controls save values that runtime code ignores

**Confidence: High · Confirmed no-op settings**

[`server/app/api/admin/config.py:14-21`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/config.py#L14) advertises editable AI timeout/retry, session expiry, alert thresholds, maintenance mode, and public registration settings; [lines 74-109](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/config.py#L74) persist updates to `SystemSetting`. Whole-repository reference checks found no runtime readers for `ai_timeout_seconds`, `ai_max_retries`, `session_expiry_days`, `public_registration_enabled`, `alert_ai_failure_pct`, or `alert_db_latency_ms`.

Observed runtime behavior remains hard-coded: Gemini requests use a 60-second timeout and three attempts ([`gemini_service.py:33-45`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/ai/gemini_service.py#L33)); sessions use the fixed seven-day `SESSION_EXPIRE_DAYS` value ([`core/config.py:28-36`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/core/config.py#L28)); alert thresholds are fixed at 20% and 200 ms ([`admin/dashboard.py:149-168`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/dashboard.py#L149)). The maintenance endpoint reads and writes a status value, but no shared request gate enforces maintenance mode ([`admin/maintenance.py:18-56`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/maintenance.py#L18)). Public registration has no check for its setting ([`api/auth.py:43-60`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/auth.py#L43)).

**Impact:** operators can receive a success response and see a saved setting while the advertised runtime behavior is unchanged.

**Action:** wire each setting to its intended runtime path, or remove/label controls that are informational only.

### F-06 — Medium — “Fork New Project” copies metadata but not the project’s work

**Confidence: High for implementation; intended copy semantics are inferred from UI wording · Likely defect**

The Overview UI calls the action “Fork New Project” and describes preserving the project and forking its changes ([`OverviewModule.tsx:142-168`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/components/OverviewModule.tsx#L142)). The `create_copy` branch in [`server/app/api/projects.py:123-144`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/projects.py#L123) creates a new `Project` row with project attributes, then returns it. It does not clone `ModuleContent`, `ModuleVersion`, `RoadmapTask`, or `CopilotMessage` rows. The new project starts at `active_module="overview"`.

**Impact:** the new project has the copied descriptive fields but none of the generated plans, saved versions, roadmap tasks, or assistant history. If a metadata-only copy is intended, the UI should say that explicitly; otherwise the copy operation needs to clone the associated records.

### F-07 — Medium — Dashboard bulk deletion follows the bulk request with duplicate single deletes

**Confidence: High · Confirmed UI/API flow defect**

[`client/src/App.tsx:586-593`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L586) passes `onDeleteProject` to `DashboardPage` but does not pass the optional `onBulkDeleteProjects` callback. The fallback in [`DashboardPage.tsx:109-129`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/pages/DashboardPage.tsx#L109) first calls the bulk endpoint, then calls `onDeleteProject` once for every selected project. The bulk endpoint has already deleted those projects ([`server/app/api/projects.py:183-230`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/projects.py#L183)).

The parent’s single-delete handler catches errors and displays an alert without rethrowing ([`App.tsx:516-527`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L516)). As a result, users can get a not-found alert for each already-deleted project; the project list is not refreshed by those failed single deletes, even though the selection/modal is cleared.

**Action:** call one bulk-delete handler that refreshes the project list once after success.

### F-08 — Medium — Roadmap task rows can diverge from saved roadmap versions

**Confidence: High · Confirmed consistency defect**

The roadmap is stored twice: versioned module JSON and a separate `RoadmapTask` table used by task APIs and the client. [`server/app/api/modules.py:37-87`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L37) only inserts or updates tasks by task code; it never removes rows whose codes are absent from a newly generated or modified roadmap. The generation and modify paths call this reconciler ([lines 166-172](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L166), [305-309](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L305)), so removed/renamed items remain in task listings and summaries.

Restoring a saved roadmap version only changes the active version and returns its JSON ([`modules.py:489-507`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L489)); it does not reconcile the task table. The frontend restore handler only replaces module detail and does not reload tasks ([`client/src/App.tsx:449-460`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L449)). The roadmap page separately reads tasks from `api.tasks.list` ([`App.tsx:233-244`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L233)).

**Impact:** restored roadmap content, roadmap task listings, progress summaries, and exports can describe different plans. User-edited task status is preserved in some reconciliation cases, but that does not keep the two representations synchronized.

**Action:** define one source of truth and reconcile it transactionally on generation, modification, version replacement, and restore, with a deliberate rule for preserving user-edited tasks.

### F-09 — Medium — AI modification paths do not consistently validate module schemas

**Confidence: High for missing validation; downstream breakage depends on AI output · Data-integrity risk**

[`GeminiAIService.modify_section`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/ai/gemini_service.py#L160) validates only `bmc` and `tech_stack` output ([lines 174-182](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/ai/gemini_service.py#L174)). The normal `/modules/{module_type}/modify` handler stores the returned data without calling the available `_validate_module_data` helper ([`server/app/api/modules.py:290-303`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L290)). The helper has validators for the other module schemas too ([lines 25-35](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L25)), but it is only used on the AI branch of conflict resolution at [lines 386-400](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L386). User-supplied replacement data in conflict resolution also reaches the replacement call without schema validation ([lines 383-385, 438-447](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L383)).

**Impact:** malformed Idea Validator, Market Research, or roadmap payloads can be persisted and later fail UI assumptions or exports.

**Action:** validate every generated or user-supplied payload against its module schema before saving, and return a client error rather than persisting invalid data.

### F-10 — Medium — Analytics counts visited-but-empty modules as adopted modules

**Confidence: High · Confirmed metric error**

A GET to `/modules/{module_type}` calls `VersionService.get_or_create_module` ([`server/app/api/modules.py:103-127`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/modules.py#L103)). That function inserts a placeholder row even when no version exists ([`server/app/services/version_service.py:12-24`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/services/version_service.py#L12)). Admin analytics counts every `ModuleContent` row by module type without checking `active_version_id` ([`server/app/api/admin/analytics.py:22-27`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/analytics.py#L22)).

**Impact:** simply opening an ungenerated module inflates adoption and conversion metrics.

**Action:** count only modules with a generated active version, or make reads side-effect free.

### F-11 — Medium — Concurrent module reads can create duplicate module records

**Confidence: Medium · Concurrency risk**

[`VersionService.get_or_create_module`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/services/version_service.py#L12) performs a query followed by an insert with no lock or conflict recovery. The `ModuleContent` model has separate indexes but no composite uniqueness constraint on `(project_id, module_type)` ([`server/app/models/all_models.py:66-77`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/models/all_models.py#L66)); the baseline migration likewise creates only a non-unique project index ([`199a3ff90b48_initial_baseline_schema.py:80-92`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/alembic/versions/199a3ff90b48_initial_baseline_schema.py#L80)).

Two concurrent first-time requests for the same project/module can both observe no row and insert one. Later calls use `.first()`, so versions can become attached to different duplicate records and analytics can also be distorted.

**Action:** add a database unique constraint and handle insert conflicts by fetching the existing row.

### F-12 — Medium — Render and Docker health checks report healthy while the database is down

**Confidence: High · Confirmed monitoring blind spot**

The configured health path is `/health` in [`render.yaml:7-10`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/render.yaml#L7), and the Docker health check also calls that path ([`Dockerfile:50-52`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/Dockerfile#L50)). The root endpoint always returns `{"status":"ok"}` without querying the database ([`server/app/main.py:80-87`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/main.py#L80)). A separate `/api/health` endpoint does check the database ([`main.py:56-76`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/main.py#L56)), but the deployment health checks do not use it.

**Impact:** a service with a broken database connection can stay marked healthy, delaying detection and automated recovery.

**Action:** make the configured health endpoint include a database readiness check, or point the platform at the existing readiness endpoint.

### F-13 — Medium — Public user login has no rate limit

**Confidence: High for missing control · Security risk**

The ordinary `/api/auth/login` handler records failed attempts but has no throttling or lockout check ([`server/app/api/auth.py:80-99`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/auth.py#L80)). In contrast, the separate admin login implements an IP-based limiter in [`server/app/api/admin/auth.py:18-34`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/auth.py#L18).

**Impact:** password guessing against ordinary accounts is not bounded by application logic. The admin limiter is in-memory and per-process, so it also should not be treated as an instance-wide control in a scaled deployment.

**Action:** add a shared rate-limit/abuse control for ordinary login and use a shared store if multiple app instances are possible.

### F-14 — Low — Admin project details miscount tasks in progress

**Confidence: High for current API-created tasks · Confirmed reporting defect**

Task creation and updates normalize `In Progress` to `Ongoing` ([`server/app/api/tasks.py:177-188`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/tasks.py#L177), [lines 257-264](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/tasks.py#L257)). The admin project detail summary counts only status `"In Progress"` for its `in_progress` field ([`server/app/api/admin/projects.py:116-123`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/server/app/api/admin/projects.py#L116)). Tasks created or updated through the current API therefore do not contribute to that count.

**Action:** normalize status values consistently in storage and admin aggregation.

### F-15 — Low — Successful profile updates do not update the app-level user state

**Confidence: High · Confirmed frontend state issue**

[`DashboardPage`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/pages/DashboardPage.tsx#L15) accepts an optional `onUserUpdated` callback and passes it to `ProfileModal` ([lines 727-738](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/pages/DashboardPage.tsx#L727)). `ProfileModal` invokes that callback after a successful profile request ([`ProfileModal.tsx:48-63`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/components/ProfileModal.tsx#L48)). The dashboard render in `App.tsx` does not supply the callback ([`App.tsx:586-593`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L586)), so the root `currentUser` stays stale until the app reloads or the user signs in again.

### F-16 — Low — Dashboard module shortcuts all open the same project module

**Confidence: High · Confirmed dead/incorrect actions**

The shortcut list assigns each item a different `mod` value, but every button calls only `onOpenProject(projects[0].id)` ([`client/src/pages/DashboardPage.tsx:350-360`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/pages/DashboardPage.tsx#L350)). Opening a project restores its one saved `active_module` ([`client/src/App.tsx:184-192`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/client/src/App.tsx#L184)); the shortcut's `q.mod` is never used. Thus BMC, technology, roadmap, and assistant buttons all open the same first project at its prior module.

### F-17 — Low — Test-count documentation is stale

**Confidence: High**

The README claims 42 backend tests at [`README.md:278-282`](https://github.com/hannyjangir1-commits/BusinessArchitect/blob/455719bd1ba04290ff36fbcaf71c3461f6f8424a/README.md#L278). The 11 tracked backend test files currently contain 76 top-level `def test_...` functions by static count. The number may change with parametrization or collection rules, but the visible function count is inconsistent with the documentation.

## System-by-system review

### Frontend and API wiring

- Client manifest and lockfile root dependency sets match. Relative TypeScript imports resolved in static path checks.
- Core login, registration, project, module, task, and export calls map to backend API routes. The major user-flow issues found are the project-copy, bulk-delete, shortcut, and stale profile-state defects above.
- Frontend Vitest coverage is concentrated in one component test file (`client/src/__tests__/components.test.tsx`); it does not cover `DashboardPage`, the application routing state in `App.tsx`, or the bulk-delete/shortcut/profile propagation flows.
- Browser automation scripts and test-result artifacts are present, but no GitHub Actions workflow is tracked to run them automatically.

### Backend, authentication, and authorization

- The backend has session-cookie and CSRF paths, password hashing, account-suspension checks, and an admin login limiter. The missing `Optional` import prevents those routes from loading at all.
- The admin role model is represented in login responses, but the API generally uses a broad admin-only guard rather than those permissions. Existing tests check an ordinary user against admin access; they do not exercise a matrix of non-super-admin roles against protected actions.
- Public registration stays enabled regardless of the advertised `public_registration_enabled` value; ordinary login has no rate limiter.
- Bootstrap behavior is conditional on deployment secret configuration, but the fallback credentials and ignored enable flag make a misconfigured deployment unsafe.

### Projects, modules, AI, and roadmap tasks

- Readiness checks precede generation. Module results are versioned, and BMC/tech stack have stricter schema checks than the other AI modification paths.
- Roadmap JSON versions and editable task rows are separate persistence paths. Regeneration, conflict resolution, and restore do not fully synchronize them.
- Project ownership scoping and standard project deletion paths are present; the copy path clones metadata only. Module placeholders are created as a side effect of reads, which affects analytics and can race under concurrent access.

### Database, migrations, and deployment

- Two Alembic revisions are tracked and the Docker build installs the declared backend/frontend dependencies and serves the built client from FastAPI.
- The client package lock matches the manifest; no obvious missing third-party dependency was found from the declared imports and manifests.
- Render and Docker use a root health endpoint that does not verify database readiness.
- The critical import defect means the deployment cannot reach a healthy running API even though the container image may build successfully.

### Tests and CI

- There are 11 backend pytest files and one Vitest component test file, plus manual/browser test scripts and stored screenshot/result artifacts.
- No workflow definitions or commit checks were present for this snapshot. I did not run pytest, Vitest, TypeScript build, or Docker build in this environment.
- The report’s confirmed findings come from source inspection; dynamic behavior, configured production environment values, and live database state remain unverified.

## File coverage register

All paths below are tracked text files fetched for the audit. They are grouped by repository area; findings above identify the files and line ranges with material issues. “Reviewed” does not mean that a file with no listed finding is guaranteed bug-free.

### Repository root / deployment

- `.app_pids`
- `.dockerignore`
- `.env.example`
- `.gitattributes`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `render.yaml`
- `run_app.bat`
- `stop_app.bat`

### Client configuration and source

- `client/.gitignore`
- `client/.oxlintrc.json`
- `client/README.md`
- `client/index.html`
- `client/package-lock.json`
- `client/package.json`
- `client/public/favicon.svg`
- `client/public/icons.svg`
- `client/src/App.css`
- `client/src/App.tsx`
- `client/src/__tests__/components.test.tsx`
- `client/src/admin/AdminApp.tsx`
- `client/src/admin/AdminChangePasswordModal.tsx`
- `client/src/admin/AdminHeader.tsx`
- `client/src/admin/AdminLayout.tsx`
- `client/src/admin/AdminSidebar.tsx`
- `client/src/admin/pages/AdminAIOperationsPage.tsx`
- `client/src/admin/pages/AdminAIQualityPage.tsx`
- `client/src/admin/pages/AdminAccountPage.tsx`
- `client/src/admin/pages/AdminAnalyticsPage.tsx`
- `client/src/admin/pages/AdminAuditLogsPage.tsx`
- `client/src/admin/pages/AdminConfigPage.tsx`
- `client/src/admin/pages/AdminDashboardPage.tsx`
- `client/src/admin/pages/AdminDataIntegrityPage.tsx`
- `client/src/admin/pages/AdminDatabasePage.tsx`
- `client/src/admin/pages/AdminLoginPage.tsx`
- `client/src/admin/pages/AdminMaintenancePage.tsx`
- `client/src/admin/pages/AdminProjectDetailPage.tsx`
- `client/src/admin/pages/AdminProjectsPage.tsx`
- `client/src/admin/pages/AdminReportsPage.tsx`
- `client/src/admin/pages/AdminSecurityPage.tsx`
- `client/src/admin/pages/AdminSystemHealthPage.tsx`
- `client/src/admin/pages/AdminUserDetailPage.tsx`
- `client/src/admin/pages/AdminUsersPage.tsx`
- `client/src/assets/react.svg`
- `client/src/assets/vite.svg`
- `client/src/components/AllTasksTable.tsx`
- `client/src/components/ArchitectureInfographic.tsx`
- `client/src/components/BMCModule.tsx`
- `client/src/components/BlueprintCopilotModule.tsx`
- `client/src/components/ContextualAssistant.tsx`
- `client/src/components/DependenciesPanel.tsx`
- `client/src/components/DetailedRoadmapModule.tsx`
- `client/src/components/ExecutionRoadmapModule.tsx`
- `client/src/components/GanttChart.tsx`
- `client/src/components/Header.tsx`
- `client/src/components/IdeaValidatorModule.tsx`
- `client/src/components/LogoutConfirmModal.tsx`
- `client/src/components/MarketResearchModule.tsx`
- `client/src/components/MilestoneCards.tsx`
- `client/src/components/NewProjectWizard.tsx`
- `client/src/components/OverviewModule.tsx`
- `client/src/components/ProfileModal.tsx`
- `client/src/components/RadialBMCInfographic.tsx`
- `client/src/components/Sidebar.tsx`
- `client/src/components/TechStackModule.tsx`
- `client/src/components/VersionConflictModal.tsx`
- `client/src/components/VersionToolbar.tsx`
- `client/src/index.css`
- `client/src/main.tsx`
- `client/src/pages/DashboardPage.tsx`
- `client/src/pages/LandingPage.tsx`
- `client/src/services/api.ts`
- `client/src/styles/index.css`
- `client/src/types/index.ts`
- `client/test_chrome.cjs`
- `client/test_full_suite.cjs`
- `client/test_redesign_suite.cjs`
- `client/test_runner_flows.cjs`
- `client/tsconfig.app.json`
- `client/tsconfig.json`
- `client/tsconfig.node.json`
- `client/vite.config.ts`

### Scripts

- `scripts/app_manager.py`
- `scripts/seed_versions_for_test.py`

### Server configuration, migrations, and source

- `server/alembic.ini`
- `server/alembic/README`
- `server/alembic/env.py`
- `server/alembic/script.py.mako`
- `server/alembic/versions/199a3ff90b48_initial_baseline_schema.py`
- `server/alembic/versions/b0be8b6f68be_add_admin_control_center_schema.py`
- `server/app/ai/gemini_service.py`
- `server/app/ai/prompts.py`
- `server/app/api/admin/__init__.py`
- `server/app/api/admin/ai_ops.py`
- `server/app/api/admin/analytics.py`
- `server/app/api/admin/audit.py`
- `server/app/api/admin/auth.py`
- `server/app/api/admin/config.py`
- `server/app/api/admin/dashboard.py`
- `server/app/api/admin/integrity.py`
- `server/app/api/admin/maintenance.py`
- `server/app/api/admin/projects.py`
- `server/app/api/admin/reports.py`
- `server/app/api/admin/security.py`
- `server/app/api/admin/system.py`
- `server/app/api/admin/users.py`
- `server/app/api/auth.py`
- `server/app/api/copilot.py`
- `server/app/api/deps.py`
- `server/app/api/exports.py`
- `server/app/api/modules.py`
- `server/app/api/projects.py`
- `server/app/api/tasks.py`
- `server/app/core/admin_provisioning.py`
- `server/app/core/config.py`
- `server/app/core/security.py`
- `server/app/core/telemetry.py`
- `server/app/db/base.py`
- `server/app/db/session.py`
- `server/app/main.py`
- `server/app/models/__init__.py`
- `server/app/models/all_models.py`
- `server/app/schemas/auth.py`
- `server/app/schemas/copilot.py`
- `server/app/schemas/modules.py`
- `server/app/schemas/project.py`
- `server/app/schemas/task.py`
- `server/app/services/pdf_service.py`
- `server/app/services/readiness_service.py`
- `server/app/services/version_service.py`
- `server/pytest.ini`
- `server/requirements.txt`

### Backend tests

- `server/tests/test_admin_auth_and_security.py`
- `server/tests/test_admin_management_and_ops.py`
- `server/tests/test_ai_failure_modes.py`
- `server/tests/test_audit_repairs_and_csrf_exhaustive.py`
- `server/tests/test_auth_and_projects.py`
- `server/tests/test_concurrency_and_sync.py`
- `server/tests/test_deployment_and_supabase_readiness.py`
- `server/tests/test_e2e_full_workflows.py`
- `server/tests/test_master_implementation_verification.py`
- `server/tests/test_pdf_and_ai.py`
- `server/tests/test_version_and_tasks.py`

### Test result artifacts

- `test-artifacts/browser_test_results.json`
- `test-artifacts/ui-redesign/redesign_verification_report.json`

**Excluded from text review:** 34 binary image assets/screenshots in the repository tree. No repository files were edited, and no PR, commit, push, or deployment was created.



