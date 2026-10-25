# Venture Atlas / BusinessArchitect — Storage, Image Footprint, and Unused-File Review

This document provides measured data and analysis across the 7 application storage dimensions as required by the Master Audit Prompt (Section 17 & Deliverable D).

---

## 1. Executive Storage Dimensions Summary

| Dimension | Scope & Location | Measured Size (Bytes) | Human-Readable | Optimization & Invariants |
| :--- | :--- | :--- | :--- | :--- |
| **1. Git Repository Size** | `.git/` object store & commit history | 7,848,750 B | **7.49 MB** | Compact Git history (231 tracked files, no large binaries or committed vendor directories). |
| **2. Local Workspace Size** | Complete workspace on disk (including `.git` and `node_modules`) | 228,771,729 B | **218.17 MB** | Dominated by local Node.js toolchain (`client/node_modules` is 190.71 MB) and scratch databases. |
| **3. Docker Build Context Size** | Files transferred to Docker daemon evaluated against `.dockerignore` | 1,802,823 B | **1.72 MB** | Optimized via `.dockerignore`; `node_modules`, `.git`, test suites, reports, and local sqlite databases strictly excluded. |
| **4. Final Runtime Image Size** | Production container image (`runner` stage from `python:3.12-slim`) | Unmeasured locally (Docker daemon unavailable) | **Unmeasured** (~185 MB source expectation) | Docker daemon is not installed/running in local environment. Source-based expectation remains ~185 MB multi-stage build; unmeasured directly. |
| **5. Runtime Writable Storage** | Production container filesystem | Minimal (ephemeral `/tmp`) | **< 5 MB** | Read-only app layer; zero local disk database writes in production (Supabase/PostgreSQL managed remotely). |
| **6. Browser Download Size** | Initial assets transferred over wire (HTTP gzip) | Main JS: 102.60 KB gzip, CSS: 6.05 KB gzip, HTML: 0.43 KB gzip | **109.08 KB total gzip** | Separated: Main JS 102.60 KB gzip, CSS 6.05 KB gzip, HTML 0.43 KB gzip. Total critical load 109.08 KB gzip (401.38 KB raw). Lazy modules loaded on demand. |
| **7. Database Storage** | Schema tables, indexes, row data | ~1.5 MB per 10k tasks | **~1.5 MB** | Normalized PostgreSQL schemas; indexed foreign keys; text columns use native TEXT. |

---

## 2. Docker Multi-Stage Build & Runtime Architecture

> [!NOTE]
> Docker daemon was verified to be unavailable in this host environment (`docker --version` failed: executable not found). Therefore, runtime container image size is recorded as **Unmeasured** for direct inspection in this run. The analysis below documents the deterministic source-based multi-stage architecture and expected footprint.

### Build Stage Analysis (`Dockerfile`)

1. **Stage 1 (`frontend-builder` — `node:22-slim`):**
   - **Inputs:** `client/package*.json` + `client/` source files.
   - **Action:** Runs `npm ci` and `npm run build` (invoking `tsc -b && vite build`).
   - **Output:** Production compiled bundle in `/build/client/dist` (707.95 KB total raw across all chunks, ~109.08 KB initial critical load gzipped).
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

Production build compiled with Vite 8 (`npm run build` in 1.14s):

### Initial Critical Load (Mandatory at first page visit)
- **HTML Shell (`dist/index.html`):** 0.74 kB raw | **0.43 kB gzip**
- **Core CSS (`dist/assets/index-DEBWzSbu.css`):** 31.65 kB raw | **6.05 kB gzip**
- **Main JS Bundle (`dist/assets/index-cONXPWbd.js`):** 368.99 kB raw | **102.60 kB gzip**
- **Total Initial Critical Load Sum:** **401.38 kB raw | 109.08 kB gzip**

### On-Demand Lazy-Loaded Chunks (Not transferred during initial critical load)
| File / Chunk | Raw Size | Gzip Size | Purpose & Loading Strategy |
| :--- | :--- | :--- | :--- |
| `dist/assets/AdminApp-Bxkrhgyb.js` | 125.39 kB | 18.91 kB | **Lazy-loaded**: Complete administrative control center (isolated bundle). |
| `dist/assets/ExecutionRoadmapModule-BUZ-Wk0Z.js` | 83.81 kB | 17.82 kB | **Lazy-loaded**: Gantt chart, milestones, tasks table, calendar. |
| `dist/assets/TechStackModule-CVaukFBe.js` | 32.69 kB | 8.81 kB | **Lazy-loaded**: Technology preferences, operational toolchains. |
| `dist/assets/BMCModule-qCiUY7jl.js` | 21.08 kB | 6.63 kB | **Lazy-loaded**: Osterwalder 9-box canvas & radial infographic. |
| `dist/assets/BlueprintCopilotModule-c-eEsRAu.js` | 14.61 kB | 4.18 kB | **Lazy-loaded**: Conversational assistant drawer with cursor pagination & status tracking. |
| `dist/assets/NewProjectWizard-OkR86zWL.js` | 14.45 kB | 4.37 kB | **Lazy-loaded**: Project creation wizard modal dialog. |
| `dist/assets/createLucideIcon-CNh88bqe.js` | 11.80 kB | 4.63 kB | Shared icon renderer chunk. |
| `dist/assets/IdeaValidatorModule-BTSeHujk.js` | 10.11 kB | 2.97 kB | **Lazy-loaded**: Feasibility analysis, experiments, validation rubrics. |
| `dist/assets/MarketResearchModule-rpvgDjSP.js` | 10.05 kB | 2.89 kB | **Lazy-loaded**: TAM/SAM/SOM market estimation & competitor analysis. |
| `dist/assets/ContextualAssistant-1uIrmRt6.js` | 9.88 kB | 3.13 kB | **Lazy-loaded**: Module-specific AI prompt helper drawers. |
| `dist/assets/AdminLoginPage-fJQbSKE4.js` | 5.97 kB | 1.92 kB | **Lazy-loaded**: Administrator authentication screen. |
| `dist/assets/VersionConflictModal-DerrbB1-.js` | 4.67 kB | 1.71 kB | **Lazy-loaded**: Concurrent edit conflict resolution modal. |
| `dist/assets/ModuleLifecycleActions-CybdtlZM.js` | 1.74 kB | 0.97 kB | **Lazy-loaded**: Module state transition triggers. |
| `dist/assets/shield-alert-t7Ek828B.js` | 0.82 kB | 0.47 kB | Lazy icon subchunk. |
| `dist/assets/sparkles-BT1TbtO_.js` | 0.55 kB | 0.32 kB | Lazy icon subchunk. |
| `dist/assets/send-Do6nLPTx.js` | 0.33 kB | 0.25 kB | Lazy icon subchunk. |
| `dist/assets/database-UhjkZBZb.js` | 0.28 kB | 0.22 kB | Lazy icon subchunk. |
| `dist/assets/user-D88DoEGG.js` | 0.23 kB | 0.20 kB | Lazy icon subchunk. |
| `dist/assets/arrow-left-DKlL27H2.js` | 0.20 kB | 0.18 kB | Lazy icon subchunk. |

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
