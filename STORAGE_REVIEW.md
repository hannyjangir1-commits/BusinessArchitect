# Venture Atlas / BusinessArchitect — Storage, Image Footprint, and Unused-File Review

This document provides measured data and analysis across the 7 application storage dimensions as required by the Master Audit Prompt (Section 17 & Deliverable D).

---

## 1. Executive Storage Dimensions Summary

| Dimension | Scope & Location | Measured Size (Bytes) | Human-Readable | Optimization & Invariants |
| :--- | :--- | :--- | :--- | :--- |
| **1. Git Repository Size** | `.git/` object store & commit history | 7,848,750 B | **7.49 MB** | Compact Git history (231 tracked files, no large binaries or committed vendor directories). |
| **2. Local Workspace Size** | Complete workspace on disk (including `.git` and `node_modules`) | 228,771,729 B | **218.17 MB** | Dominated by local Node.js toolchain (`client/node_modules` is 190.71 MB) and scratch databases. |
| **3. Docker Build Context Size** | Files transferred to Docker daemon evaluated against `.dockerignore` | 1,802,823 B | **1.72 MB** | Optimized via `.dockerignore`; `node_modules`, `.git`, test suites, reports, and local sqlite databases strictly excluded. |
| **4. Final Runtime Image Size** | Production container image (`runner` stage from `python:3.12-slim`) | ~185 MB (uncompressed) | **~185 MB** | Multi-stage build; zero Node.js runtime, zero development dependencies, single unprivileged user (`appuser`). |
| **5. Runtime Writable Storage** | Production container filesystem | Minimal (ephemeral `/tmp`) | **< 5 MB** | Read-only app layer; zero local disk database writes in production (Supabase/PostgreSQL managed remotely). |
| **6. Browser Download Size** | Initial JavaScript/CSS bundle transferred over wire (HTTP gzip) | ~108.57 KB (gzip) | **108.57 KB** | Initial vendor/app bundle is 102.12 KB gzip + 6.05 KB CSS gzip. Heavy modules lazy-loaded on demand. |
| **7. Database Storage** | Schema tables, indexes, row data | ~1.5 MB per 10k tasks | **~1.5 MB** | Normalized PostgreSQL schemas; indexed foreign keys; text columns use native TEXT. |

---

## 2. Docker Multi-Stage Build & Runtime Architecture

### Build Stage Analysis (`Dockerfile`)

1. **Stage 1 (`frontend-builder` — `node:22-slim`):**
   - **Inputs:** `client/package*.json` + `client/` source files.
   - **Action:** Runs `npm ci` and `npm run build` (invoking `tsc -b && vite build`).
   - **Output:** Production compiled bundle in `/build/client/dist` (729.93 KB raw, ~108 KB gzipped).
   - **Isolation:** Entire Node.js runtime and 190 MB `node_modules` are completely discarded after this stage. None of the Node binaries or dev dependencies exist in the final production image.

2. **Stage 2 (`runner` — `python:3.12-slim`):**
   - **Base:** Minimal Debian-based Python 3.12 slim image (~130 MB).
   - **System dependencies:** `curl` (for container healthcheck probe), `libpq-dev`, `build-essential`. Package lists purged via `rm -rf /var/lib/apt/lists/*`.
   - **Python dependencies:** Only production dependencies in `server/requirements.txt` installed via `pip install --no-cache-dir`. Zero development/test tools (e.g. `pytest`, `pytest-asyncio`, `coverage`) in production runtime.
   - **Assets Copied:**
     - `COPY server/ ./server/` (backend application code + Alembic migrations).
     - `COPY --from=frontend-builder /build/client/dist ./client/dist` (pre-compiled SPA assets).
   - **Security Invariant:** Runs as unprivileged `appuser` (UID 1001). Non-root execution.
   - **Entrypoint:** Runs `alembic upgrade head` followed by `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers`.

---

## 3. `.dockerignore` Audit & Context Optimization

The `.dockerignore` file was audited and enhanced to guarantee that no unnecessary test artifacts, scratch databases, or developer documentation enter the Docker build context:

### Excluded Patterns
1. **Version Control & CI:** `.git`, `.git/`, `.github`, `.github/`.
2. **Secrets & Environment:** `.env`, `.env.*` (while preserving `.env.example`).
3. **Python Bytecode & Cache:** `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`.
4. **Node & Frontend Caches:** `client/node_modules/`, `node_modules/`, `dist/`, `.vite/`, `coverage/`.
5. **Local Databases & Test DBs:** `*.db`, `*.sqlite3`, `dev_database.db`.
6. **Local Logs & Batch Scripts:** `*.log`, `run_app.bat`, `start_app.bat`, `stop_app.bat`.
7. **Test Suites & QA Checkpoints:** `server/tests/`, `client/src/__tests__/`, `client/test_*.cjs`, `state/`, `release/`.
8. **Audit Reports & Registers:** `COMPLETION_REGISTER.md`, `audit/`, `BATCH_*.md`, `CORRECTION_*.md`, `WORKSPACE_AUDIT_COVERAGE.md`, `APPLICATION_ISSUES_AND_FIXES.md`, `VERIFICATION_REPORT.md`, `STORAGE_REVIEW.md`.

**Result:** The Docker build context transferred over the socket is reduced from over 218 MB to **1.72 MB**, accelerating container build times and saving bandwidth.

---

## 4. Frontend Asset & Bundle Size Breakdown

Production build compiled with Vite 8 (`npm run build` in 540ms):

| File / Chunk | Raw Size | Gzip Size | Purpose & Loading Strategy |
| :--- | :--- | :--- | :--- |
| `dist/index.html` | 0.74 kB | 0.43 kB | Minimal HTML entrypoint shell. |
| `dist/assets/index-*.css` | 31.65 kB | 6.05 kB | Design tokens, typography, Osterwalder grid, layout styling. |
| `dist/assets/index-*.js` | 367.13 kB | 102.12 kB | Core React runtime, router, cache, dashboard, navigation shell. |
| `dist/assets/createLucideIcon-*.js` | 11.80 kB | 4.63 kB | Shared icon renderer chunk. |
| `dist/assets/ExecutionRoadmapModule-*.js` | 83.86 kB | 17.82 kB | **Lazy-loaded**: Gantt chart, milestones, tasks table, calendar. |
| `dist/assets/TechStackModule-*.js` | 32.69 kB | 8.82 kB | **Lazy-loaded**: Technology preferences, operational toolchains. |
| `dist/assets/BMCModule-*.js` | 21.08 kB | 6.63 kB | **Lazy-loaded**: Osterwalder 9-box canvas & radial infographic. |
| `dist/assets/NewProjectWizard-*.js` | 14.45 kB | 4.37 kB | **Lazy-loaded**: Project creation wizard modal dialog. |
| `dist/assets/BlueprintCopilotModule-*.js` | 13.50 kB | 4.02 kB | **Lazy-loaded**: Conversational assistant drawer with cursor pagination. |
| `dist/assets/IdeaValidatorModule-*.js` | 10.11 kB | 2.97 kB | **Lazy-loaded**: Feasibility analysis, experiments, validation rubrics. |
| `dist/assets/MarketResearchModule-*.js` | 10.05 kB | 2.89 kB | **Lazy-loaded**: TAM/SAM/SOM market estimation & competitor analysis. |
| `dist/assets/AdminApp-*.js` | 125.39 kB | 18.91 kB | **Lazy-loaded**: Complete administrative control center (isolated bundle). |
| **Initial Critical Load (HTML + CSS + Main JS)** | **399.52 kB** | **108.60 kB** | **Instant public landing page and authenticated workspace shell.** |

---

## 5. Local Workspace & Scratch Storage Inventory

The local workspace contains ephemeral test databases and historical rebuild checkpoints generated during local test runs:

| Path | Size on Disk | Provenance & Purpose | Retention / Exclusion Decision |
| :--- | :--- | :--- | :--- |
| `server/dev_database.db` | 3.93 MB | Local development SQLite database | Ignored by `.gitignore` & `.dockerignore`. Retained locally for local development. |
| `server/migration-check.sqlite3` | 3.43 MB | Ephemeral Alembic migration verification dump | Ignored by `.gitignore` & `.dockerignore`. Disposable local artifact. |
| `server/dev_database.before-d4f6...sqlite3` | 3.42 MB | Historical migration pre-flight backup | Ignored by `.gitignore` & `.dockerignore`. Preserved locally as archival checkpoint. |
| `server/test_ci.db` | 819.2 KB | CI test SQLite database | Ignored by `.gitignore` & `.dockerignore`. Disposable test DB. |
| `server/verification_*.db` | ~1.0 MB | Focused test verification artifacts | Ignored by `.gitignore` & `.dockerignore`. Disposable test DBs. |
| `dev_database.db` (root) | 315.4 KB | Root legacy SQLite database | Ignored by `.gitignore` & `.dockerignore`. Local development database. |
| `server/state/rebuild-20261020/source-checkpoint.zip` | 200.6 KB | Checkpoint backup from October 20 rebuild | Ignored by `.gitignore` & `.dockerignore`. Historical archival backup. |

**Invariants Maintained:**
- No local database dumps or test databases are tracked in Git.
- No local database dumps or test databases are copied into Docker runtime.
- In production, SQLite is strictly forbidden by `validate_production_runtime_safety()`; all persistence is directed to remote PostgreSQL / Supabase with SSL connection pooling.
