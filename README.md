# AI Business Architect — Enterprise Blueprint

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6.svg)](https://www.typescriptlang.org/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-API-4285F4.svg)](https://ai.google.dev/)
[![Supabase](https://img.shields.io/badge/Database-Supabase_PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Render](https://img.shields.io/badge/Deploy-Render_Docker-46E3B7.svg)](https://render.com/)

An enterprise-grade business planning platform that transforms venture concepts into structured, editable, visually organized business blueprints. Built with **FastAPI**, **React 19**, **SQLAlchemy**, **Google Gemini AI**, **Supabase PostgreSQL**, and deterministic SVG visualization engines.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │              Client Browser                  │
                      │  (React 19, TypeScript, Vanilla CSS, SVG)    │
                      └──────────────────────┬───────────────────────┘
                                             │ HTTP-Only Cookie + CSRF
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │             FastAPI Backend                  │
                      │   - Session Auth (Argon2id)                  │
                      │   - 5-Version Limit Engine                   │
                      │   - SPA Static Fallback Server               │
                      └──────────────┬──────────────────┬────────────┘
                                     │                  │
               SQLAlchemy / Alembic  │                  │ Google GenAI SDK
                                     ▼                  ▼
              ┌───────────────────────────┐    ┌─────────────────────┐
              │    Supabase PostgreSQL     │    │  Google Gemini API  │
              │  (Session Pooler / SSL)   │    │  (Structured JSON)  │
              └───────────────────────────┘    └─────────────────────┘
```

### Core Technologies
- **Frontend**: React 19, TypeScript, Vite, Vanilla CSS design system (dark sidebar, clean enterprise workspace), Lucide icons.
- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic database migrations.
- **AI Intelligence**: Google Gemini API via official `google-genai` SDK (`gemini-3.5-flash` with candidate fallback chain).
- **Database**: Supabase PostgreSQL (pooler / direct connection with SSL mode) & SQLite fallback for zero-config test suites.
- **Security**: Argon2id password hashing, HTTP-only SameSite session cookies (`aba_session`), cryptographic CSRF validation (`aba_csrf`), and strict user ownership enforcement on all project endpoints.
- **Visualizations**: Code-based deterministic SVG Radial Business Model Canvas (9 blocks around center node), SVG Technology Stack tiered cards, interactive SVG Gantt chart with month/week grid, dependencies, and today marker.
- **Export Pipeline**: ReportLab PDF engine supporting module-specific PDF downloads and full consolidated multi-page project blueprints (strictly excluding copilot messages, version history, and audit logs).
- **Deployment**: Multi-stage Docker build serving both React frontend assets and FastAPI API routes from a single unified origin on Render.

---

## Application Features

1. **Secure Authentication & Ownership**:
   - Registration with password complexity requirements (8–128 characters, letters & digits).
   - Argon2id password hashing.
   - HTTP-only session cookies with CSRF token verification.
   - Strict project isolation: users cannot access or mutate another user's projects, tasks, or versions.
2. **Stage-Aware 3-Step Project Creation**:
   - Step 1: Venture identity, industry, description, and stage (`Idea / MVP`, `Post-launch`, `Growth`).
   - Step 2: Stage-aware discovery:
     - For `Idea / MVP`: initial build budget & strategic goals.
     - For `Post-launch` and `Growth`: dedicated multi-select **Existing Technology Stack Selector** (Frontend, Backend, Database, Cloud/Hosting, Storage, Auth, DevOps, Services, and custom technologies).
   - Step 3: Review summary and AI blueprint generation.
3. **Alexander Osterwalder 9-Block Business Model Canvas**:
   - Deterministic SVG Radial Infographic inspired by the TempShare reference (center company node + 9 surrounding blocks + 9 dynamic connectors).
   - Structured 9-block grid view.
   - Section-specific AI modification chat.
4. **Technology Stack Architecture**:
   - Evaluates existing stack components, scalability bottlenecks, trade-offs, and migration risks.
   - Categorized tier cards (Frontend, Backend, Database, Cloud, Security, DevOps, Services).
   - Section-specific AI modification chat.
5. **Idea Validator & Feasibility Report**:
   - Overall viability score meter (0–100).
   - Problem urgency, ICP fit, value proposition, and market assumptions.
   - Risk matrix with severity ratings and mitigation strategies.
   - Actionable validation experiments with target metrics.
   - *Section-specific AI modification chat is deliberately absent per system rules.*
6. **Market Research & Competitor Intelligence**:
   - Explicit AI-grounded analytical provenance disclaimer.
   - TAM / SAM / SOM market estimations.
   - Competitor profiles (strengths, weaknesses, pricing models, market share estimates).
   - Competitive positioning wedge, opportunities, and threats.
   - *Section-specific AI modification chat is deliberately absent per system rules.*
7. **Execution Roadmap & Interactive Gantt Chart**:
   - 5 structured phases: *Planning & Research*, *System Design*, *Development*, *Testing & Deployment*, *Launch & Monitor*.
   - Interactive SVG Gantt chart with Month View (Oct 2026 – Mar 2027), weekly columns (W1–W4), today line, and milestone diamonds.
   - 30-Day, 60-Day, and 90-Day milestone cards with progress bars and fractions.
   - Full task management table with filters (All, 30-Day, 60-Day, 90-Day), search, status dropdowns, priority badges, and dependency safety checks.
   - Section-specific AI modification assistant on the right panel.
8. **Detailed Operational Roadmap**:
   - Tasks grouped dynamically by chronological monthly execution intervals.
   - Synchronized with the centralized database tasks table.
9. **Blueprint Copilot**:
   - Full-screen conversational AI venture partner with persistent project context injection.
   - Excluded from the consolidated project PDF export.
10. **Five-Version Control Engine**:
    - Each module independently stores up to 5 versions (`V1` to `V5`).
    - Enforced on the backend: attempting to save a 6th version returns HTTP 409 Conflict.
    - Explicit conflict resolution modal: prompt user to choose a version slot to replace or delete.
    - No silent overwrites or unexpected deletions.
    - Version display renaming, deletion, and restoration.
11. **Per-Project Navigation Memory**:
    - The active module tab is saved to Supabase per project.
    - Reopening a project restores its last viewed module automatically.
12. **Consolidated PDF & Module Exports**:
    - Single-module export button (PDF / SVG) in the workspace toolbar.
    - Consolidated full-project PDF export button directly above *Create New Project* in the sidebar.
    - Excludes chat history, audit logs, and version control metadata.

---

## Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `DATABASE_URL` | Supabase PostgreSQL Connection String | `postgresql://postgres.xxx:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require` |
| `SESSION_SECRET` | 32+ character random secret for signing | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `APP_ENV` | Environment (`development` / `production`) | `production` |
| `COOKIE_SECURE` | Set `true` in production over HTTPS | `true` |
| `PORT` | Listening port (Render supplies automatically) | `8000` |
| `HOST` | Listening interface | `0.0.0.0` |

---

## Local Development Setup

### One-Click Windows Launcher (Recommended for Windows)

Simply double-click `run_app.bat` at the repository root to automatically:
1. Validate Python (3.10+) and Node.js/npm prerequisites.
2. Verify backend and frontend dependencies without silent overwrites.
3. Start the FastAPI backend on `http://127.0.0.1:8000`.
4. Start the Vite frontend dev server on `http://127.0.0.1:5173`.
5. Poll `/api/health` and wait for complete service readiness.
6. Automatically open Google Chrome at `http://localhost:5173`.

To safely shut down the backend and frontend without terminating unrelated processes:
Double-click `stop_app.bat`.

---

### Manual Setup

#### 1. Backend Setup
```bash
cd server
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd client
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Vite automatically proxies `/api` requests to the FastAPI server at `http://localhost:8000`.

### 3. Automated Tests
```bash
cd server
python -m pytest -v
```

---

## Supabase PostgreSQL Setup

1. Log in to [Supabase](https://supabase.com) and navigate to your project.
2. Go to **Project Settings** → **Database**.
3. Under **Connection Pooling**, select **Session mode** (Port `6543`) with URI format.
4. Copy the connection string and replace `[YOUR-PASSWORD]` with your database password:
   ```text
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```
5. Supply this string as the `DATABASE_URL` environment variable.
6. Execute migrations against Supabase:
   ```bash
   alembic upgrade head
   ```

---

## Render Deployment Guide

The repository includes a production-ready multi-stage `Dockerfile` and `render.yaml` Blueprint.

### Option A: Render Blueprint (Recommended)
1. Commit and push your code to GitHub:
   ```bash
   git add .
   git commit -m "feat: complete enterprise blueprint application"
   git push origin main
   ```
2. In the [Render Dashboard](https://dashboard.render.com), click **New +** → **Blueprint**.
3. Select your GitHub repository (`BusinessArchitect`).
4. Render reads `render.yaml` and provisions the Web Service with Docker runtime.
5. In the service settings, configure the following secrets under **Environment Variables**:
   - `DATABASE_URL`: Your Supabase PostgreSQL connection string.
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `SESSION_SECRET`: Generated automatically or enter a random 32-character string.
6. Render builds the multi-stage image, tests the health check at `/health`, and serves the full application on your `.onrender.com` domain.

### Option B: Manual Web Service
1. In Render, select **New +** → **Web Service**.
2. Connect your repository.
3. Choose **Docker** as the runtime.
4. Set **Health Check Path** to `/health`.
5. Add the required environment variables:
   - `DATABASE_URL`
   - `GEMINI_API_KEY`
   - `SESSION_SECRET`
   - `APP_ENV`: `production`
   - `COOKIE_SECURE`: `true`
6. Click **Deploy Web Service**.

---

## Level 3 Enterprise Admin Control Center

The application features a production-ready, data-backed **Enterprise Admin Control Center** accessible at `/admin/login` and `/admin`.

### 1. Initial Bootstrap Administrator Provisioning
The platform supports secure, idempotent server-side administrator initialization via environment variables:
- `ADMIN_BOOTSTRAP_ENABLED=true` (must be explicitly enabled; defaults to `false`)
- `ADMIN_BOOTSTRAP_USERNAME=your_admin_username` (alphanumeric, min 3 characters)
- `ADMIN_BOOTSTRAP_PASSWORD=your_strong_password` (minimum 12 characters including uppercase, lowercase, numbers, and symbols)
- `ADMIN_BOOTSTRAP_EMAIL=admin@yourdomain.com`

**Security Constraints**:
1. Plaintext credentials are **never hardcoded or committed** to git, frontend builds, or database migrations. If bootstrap is enabled without required credentials or with a weak password, provisioning safely aborts with a sanitized log message.
2. The initial administrator is initialized idempotently on application startup: if the administrator record already exists, its password is **never overwritten or reset**.
3. Passwords are encrypted exclusively with **Argon2id** (RFC 9106 parameters).
4. Plaintext credentials or hashes are never returned by any API or exposed to logs.
5. Ordinary users (`role="user"`) and anonymous callers are strictly blocked from all `/api/admin/*` endpoints and `/admin/*` frontend views with HTTP 403/401.

### 2. Mandatory Credential Rotation Procedure
Because bootstrap credentials are used for initial provisioning, administrators must rotate credentials before public exposure:
1. Log into `/admin/login` using the bootstrap credentials.
2. Navigate to **Administration** → **Admin Account** (`/admin/account`).
3. Click **Rotate Administrator Password**.
4. Enter current password and new password meeting the complexity policy (minimum 8 characters with letters and numbers).
5. Upon confirmation, all other active sessions across browsers are automatically terminated, and the event is recorded in the server-side audit trail.

### 3. Enterprise Admin Features & Navigation Groups

| Group | Module | Route | Capabilities |
| :--- | :--- | :--- | :--- |
| **Overview** | **Admin Dashboard** | `/admin` | Real KPI cards (Users, Projects, AI, Infra, Security), dynamic time filters (`24h`, `7d`, `30d`, `90d`), SVG trend series, and operational alerts ordered by severity. |
| **Application** | **User Directory** | `/admin/users` | Server-side pagination, search, status filters (`all`, `active`, `suspended`), account suspension/reactivation with reason, session revocation, and safe deletion. |
| | **Projects Console** | `/admin/projects` | Search, stage filtering, project metadata, module usage summaries, owner transfer workflow, and safe transactional deletion. |
| **AI Operations** | **Gemini Operations** | `/admin/ai-operations` | Filter operations by module/status, p50/p95 latency metrics, sanitized error classification, and idempotent retry. |
| | **AI Quality & Reliability** | `/admin/ai-quality` | Output validation tracking (BMC 9 blocks, Tech Stack, Roadmap dependencies, version limits). |
| **Analytics** | **Product Analytics** | `/admin/analytics` | 6-step conversion funnel (Register → Project → BMC → Stack → Roadmap → Export) and module adoption rates. |
| | **Reports & Exports** | `/admin/reports` | Spreadsheet formula-sanitized CSV exports (`=`, `+`, `-`, `@` sanitization) and ReportLab PDF executive summaries. |
| **Infrastructure** | **System Health** | `/admin/system-health` | Subsystem liveness/readiness, DB latency ms, Alembic revision, and sanitized log explorer. |
| | **Database & Migrations** | `/admin/database` | Engine diagnostics, connection pool stats, core table record counts, and migration status. |
| | **Data Integrity Scan** | `/admin/data-integrity` | Invariant scan (orphans, cyclic tasks, >5 versions) and atomic transactional repair. |
| | **Maintenance Center** | `/admin/maintenance` | Global maintenance toggle with reason and expired session database housekeeping. |
| **Security** | **Security Center** | `/admin/security` | Real-time security incident explorer, severity filters, active session listing, and session revocation. |
| | **Audit Trail** | `/admin/audit-logs` | Server-side immutable audit log of administrative actions, identity updates, and setting mutations. |
| **Administration**| **Configuration Center**| `/admin/configuration` | Validated runtime parameters (AI timeouts, retry count, alert thresholds) and masked deployment secret verification. |
| | **Admin Account** | `/admin/account` | Administrator identity profile, Argon2id security posture, password rotation, and session management. |

### 4. Running Tests and Verification

The test suite is organized into modular verification groups covering core workflows, security, data integrity, concurrency, and audit regressions:

#### Backend Test Suite (Pytest)
```bash
cd server
python -m pytest -v
```
Test groups include:
- **Audit Findings Regression Suite (`test_audit_findings_regression.py`)**: Validates fixes for findings F-01 through F-16 (import blockers, safe bootstrap, RBAC matrix, empty-data handling, runtime settings, project deep copy/forking, roadmap version-task reconciliation, strict payload validation, side-effect-free analytics, health readiness, and user login throttling).
- **Admin Authentication & RBAC (`test_admin_auth_and_security.py`)**: Tests multi-role admin capabilities, session security, password rotation, and unauthenticated/ordinary user access restrictions.
- **Admin Management & Operations (`test_admin_management_and_ops.py`)**: Tests admin telemetry, user directory management, and system maintenance mode toggling.
- **Data Integrity & Concurrency (`test_concurrency_and_sync.py`, `test_audit_repairs_and_csrf_exhaustive.py`)**: Tests concurrent module creation uniqueness, CSRF protection, and version pruning.
- **End-to-End Workflows & Versioning (`test_e2e_full_workflows.py`, `test_version_and_tasks.py`)**: Tests full project lifecycle, roadmap task tracking, and multi-module generation.
- **Deployment & Readiness (`test_deployment_and_supabase_readiness.py`)**: Tests health endpoints, database readiness checks, and migration stability. Live external service tests (e.g. Supabase connection) are opt-in and cleanly skipped when credentials are not configured.

#### Frontend Test Suite (Vitest)
```bash
cd client
npm test
```
Runs component tests and audit regression checks (`audit_findings_frontend.test.tsx`), validating batch project deletion error handling, instant profile state reflection, and dashboard module shortcut navigation.

#### Code Quality & Production Build
```bash
cd client
npm run lint    # Lints frontend code with Oxlint
npm run build   # Type-checks (tsc -b) and compiles optimized bundle with Vite
```
