# Audit Phase Four & Five: Backend API and Contract Test Matrix

**Project:** Venture Atlas / BusinessArchitect  
**Execution Timestamp:** 2026-10-21T01:52:00+05:30  
**Verification Method:** Live HTTP execution against `http://127.0.0.1:8000` + Pytest suite (203 tests)  

---

## 1. Authentication & Session Management APIs

| Method | Endpoint Path | Auth Required | CSRF Required | Request Body / Schema | Response Status | Persistence & Security Effect | Status |
|---|---|---|---|---|---|---|---|
| `POST` | `/api/auth/register` | No | No | `UserCreateRequest` (username, email, password, confirm_password, terms_accepted) | `201 Created` | Creates `User` with Argon2id hash; sets `aba_session` and `aba_csrf` cookies; returns CSRF token. | **PASS** |
| `POST` | `/api/auth/login` | No | No | `UserLoginRequest` (username, password) | `200 OK` | Verifies credentials; issues session token stored in `sessions` table; invalidates prior tokens if configured. | **PASS** |
| `POST` | `/api/auth/logout` | Yes | Yes | None | `200 OK` | Revokes active session from `sessions` table; clears client cookies. | **PASS** |
| `GET` | `/api/auth/me` | Yes | No | None | `200 OK` / `401 Unauthorized` | Returns current user profile with display name and preferences. Returns 401 when unauthenticated. | **PASS** |
| `PUT` | `/api/auth/profile` | Yes | Yes | `UserProfileUpdateRequest` (display_name, preferences) | `200 OK` | Updates presentation preferences and display name in `users` table. | **PASS** |
| `POST` | `/api/auth/change-password` | Yes | Yes | `PasswordChangeRequest` (current_password, new_password) | `200 OK` | Verifies current password before applying new Argon2id hash; logs security event. | **PASS** |

---

## 2. Project Workspace APIs

| Method | Endpoint Path | Auth Required | CSRF Required | Response Status | Persistence & Verification Notes | Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/projects` | Yes | No | `200 OK` | Returns array of projects belonging strictly to active user; includes task count and stage. | **PASS** |
| `POST` | `/api/projects` | Yes | Yes | `201 Created` | Creates new `Project` record initialized with user ID; returns generated project object. | **PASS** |
| `GET` | `/api/projects/{id}` | Yes | No | `200 OK` / `403 Forbidden` | Loads single project. Strictly blocks access from unauthorized users (`403/404`). | **PASS** |
| `PUT` | `/api/projects/{id}` | Yes | Yes | `200 OK` | Updates venture metadata (name, industry, description, goals, budget). | **PASS** |
| `PATCH` | `/api/projects/{id}/active-module` | Yes | Yes | `200 OK` | Saves last-viewed module per project for seamless navigation resumption. | **PASS** |
| `POST` | `/api/projects/bulk-delete` | Yes | Yes | `200 OK` | Atomically deletes multiple selected projects belonging to user with cascading cleanup. | **PASS** |
| `DELETE` | `/api/projects/{id}` | Yes | Yes | `200 OK` | Cascades deletion to `module_contents`, `module_versions`, `roadmap_tasks`, and `copilot_messages`. | **PASS** |

---

## 3. Module Content & Version Control APIs

| Method | Endpoint Path | Auth Required | CSRF Required | Response Status | Behavior & Verification Notes | Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/projects/{id}/modules/{type}` | Yes | No | `200 OK` | Returns module detail, active version data, version count, and available version list. | **PASS** |
| `POST` | `/api/projects/{id}/modules/{type}/generate` | Yes | Yes | `200 OK` / `500 Error` | Triggers multi-key AI generation pipeline; validates schema; saves new snapshot if successful. | **PASS** |
| `POST` | `/api/projects/{id}/modules/{type}/accept-update` | Yes | Yes | `200 OK` | Saves user-edited JSON data as a new version snapshot; enforces 5-version retention limit. | **PASS** |
| `POST` | `/api/projects/{id}/modules/{type}/modify` | Yes | Yes | `200 OK` | AI section modification with instruction prompt; preserves previous version if AI fails. | **PASS** |
| `POST` | `/api/projects/{id}/modules/{type}/resolve-conflict`| Yes | Yes | `200 OK` | Allows user to replace an older version when 5-version maximum has been reached. | **PASS** |
| `PATCH`| `/api/projects/{id}/modules/{type}/versions/{vid}/rename` | Yes | Yes | `200 OK` | Updates `version_name` display title (e.g., "Subscription Pivot"). | **PASS** |
| `POST` | `/api/projects/{id}/modules/{type}/versions/{vid}/restore` | Yes | Yes | `200 OK` | Atomically sets selected version as `is_active=True` and updates module pointer. | **PASS** |
| `DELETE`| `/api/projects/{id}/modules/{type}/versions/{vid}` | Yes | Yes | `200 OK` | Deletes version; atomically falls back to newest remaining version. Blocks deleting sole version. | **PASS** |

---

## 4. Execution Roadmap Task APIs

| Method | Endpoint Path | Auth Required | CSRF Required | Response Status | Behavior & Verification Notes | Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/projects/{id}/tasks` | Yes | No | `200 OK` | Returns ordered task list with dependencies, timelines, assignees, and effort metrics. | **PASS** |
| `GET` | `/api/projects/{id}/tasks/summary` | Yes | No | `200 OK` | Calculates milestone progress percentages (30/60/90-day) and overall completion. | **PASS** |
| `POST` | `/api/projects/{id}/tasks` | Yes | Yes | `201 Created` | Creates new roadmap task with order index and validated date formatting. | **PASS** |
| `PUT` | `/api/projects/{id}/tasks/{tid}` | Yes | Yes | `200 OK` / `400 Bad Request` | Updates task details. Blocks circular dependencies with HTTP 400. | **PASS** |
| `DELETE`| `/api/projects/{id}/tasks/{tid}` | Yes | Yes | `200 OK` | Removes task; reconciles dependent task dependency arrays safely. | **PASS** |

---

## 5. Planning Copilot APIs

| Method | Endpoint Path | Auth Required | CSRF Required | Response Status | Behavior & Verification Notes | Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/projects/{id}/copilot` | Yes | No | `200 OK` | Retrieves chronologically ordered chat messages for the project. | **PASS** |
| `POST` | `/api/projects/{id}/copilot` | Yes | Yes | `200 OK` | Injects project facts, validates token boundaries, and streams/returns assistant guidance. | **PASS** |

---

## 6. Document & Export APIs

| Method | Endpoint Path | Auth Required | Content-Type | Response Status | Verification Notes | Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/projects/{id}/export/pdf` | Yes | `application/pdf` | `200 OK` | Generates consolidated executive blueprint PDF (ReportLab). Validated `%PDF-1.4` binary in 83ms. | **PASS** |
| `GET` | `/api/projects/{id}/modules/{type}/export/pdf` | Yes | `application/pdf` | `200 OK` | Generates single-module formatted PDF dossier. Validated `%PDF-1.4` binary in 67ms. | **PASS** |

---

## 7. Admin Operations & Governance APIs

| Method | Endpoint Path | Role Required | Response Status | Verification Notes | Status |
|---|---|---|---|---|---|
| `POST` | `/api/admin/auth/login` | Admin Tiers | `200 OK` | Verifies admin credentials; issues admin session cookie and CSRF token. | **PASS** |
| `GET` | `/api/admin/dashboard/stats` | Any Admin | `200 OK` | Returns platform aggregates (users, projects, active sessions). Rejects non-admin (403). | **PASS** |
| `GET` | `/api/admin/users` | Admin Tiers | `200 OK` | Lists users with pagination and suspension status. | **PASS** |
| `POST` | `/api/admin/users/{id}/suspend` | Super / Ops | `200 OK` | Suspends target user; terminates all active sessions; logs audit event. | **PASS** |
| `GET` | `/api/admin/ai-operations` | Admin Tiers | `200 OK` | Queries AI operation telemetry, latency, token usage, and provider error categories. | **PASS** |
| `GET` | `/api/admin/audit-logs` | All Admins | `200 OK` | Queries immutable platform audit logs with actor tracing and outcome filtering. | **PASS** |
| `GET` | `/api/admin/integrity/scan` | Super / Ops | `200 OK` | Scans relational tables for orphaned records or constraint inconsistencies. | **PASS** |
| `GET` | `/api/admin/configuration` | Super Admin | `200 OK` | Retrieves runtime settings without exposing private secret keys. | **PASS** |
| `POST` | `/api/admin/maintenance/toggle` | Super Admin | `200 OK` | Activates maintenance mode; middleware immediately returns HTTP 503 to non-admin traffic. | **PASS** |
