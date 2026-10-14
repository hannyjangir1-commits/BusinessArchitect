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

### 1. Backend Setup
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
