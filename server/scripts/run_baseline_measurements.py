"""Repeatable local performance baseline measurement harness for Batch 01.

Measures query counts, commit counts, response sizes, and local durations on an
isolated, disposable SQLite instance. Never connects to production databases or calls Gemini.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure server package is on sys.path
SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

# Create disposable SQLite database for baseline harness
_tmp_file = tempfile.NamedTemporaryFile(suffix=".baseline.sqlite3", delete=False)
_tmp_db_path = Path(_tmp_file.name)
_tmp_file.close()

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path.as_posix()}"
os.environ["PERF_DIAGNOSTICS"] = "true"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "harness-session-secret-key-at-least-32-chars-long"
os.environ["ADMIN_BOOTSTRAP_ENABLED"] = "false"

from alembic import command
from alembic.config import Config

# Run Alembic migrations on disposable DB
alembic_cfg = Config(str(SERVER_ROOT / "alembic.ini"))
command.upgrade(alembic_cfg, "head")

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.core.diagnostics import get_current_diagnostics
from app.db.session import SessionLocal, engine
from app.models.all_models import (
    User,
    Session as DBSession,
    Project,
    ModuleContent,
    ModuleVersion,
    RoadmapTask,
    CopilotMessage,
    gen_id,
)

settings.PERF_DIAGNOSTICS = True
client = TestClient(app)


def seed_harness_data() -> Dict[str, Any]:
    """Seed three isolated test personas: zero projects, single project with versions, and ten projects."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. User Zero: 0 projects
        user_0 = User(
            id=gen_id("usr_"),
            username="baseline_user_zero",
            email="zero@example.internal",
            hashed_password=hash_password("Password123!"),
            terms_accepted=True,
            created_at=now,
        )
        db.add(user_0)
        sess_0 = DBSession(
            id=gen_id("sess_"),
            user_id=user_0.id,
            session_token="token_zero_projects_baseline",
            expires_at=now + timedelta(days=7),
            created_at=now,
        )
        db.add(sess_0)

        # 2. User One: 1 project with multiple versions, roadmap tasks, and copilot history
        user_1 = User(
            id=gen_id("usr_"),
            username="baseline_user_one",
            email="one@example.internal",
            hashed_password=hash_password("Password123!"),
            terms_accepted=True,
            created_at=now,
        )
        db.add(user_1)
        sess_1 = DBSession(
            id=gen_id("sess_"),
            user_id=user_1.id,
            session_token="token_one_project_baseline",
            expires_at=now + timedelta(days=7),
            created_at=now,
        )
        db.add(sess_1)

        proj_1 = Project(
            id="proj_baseline_one",
            user_id=user_1.id,
            name="Apex Fleet Robotics",
            stage="Growth",
            description="Autonomous fleet management platform for industrial logistics.",
            industry="Logistics & Robotics",
            target_customers="Enterprise warehouse operations managers",
            goals="Scale to 500 active autonomous rovers by Q4",
            business_context="B2B Hardware-enabled SaaS with annual recurring service contracts.",
            budget="$250,000 Initial Seed",
            existing_stack={"backend": "FastAPI", "database": "PostgreSQL"},
            active_module="bmc",
            created_at=now,
            updated_at=now,
        )
        db.add(proj_1)

        # Add BMC module with 3 versions
        bmc_module = ModuleContent(
            id=gen_id("mod_"),
            project_id=proj_1.id,
            module_type="bmc",
            created_at=now,
            updated_at=now,
        )
        db.add(bmc_module)
        db.flush()

        v1 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=bmc_module.id,
            version_number=1,
            version_name="Initial Seed Draft",
            is_active=False,
            data={"value_propositions": ["Lower downtime", "Autonomous dispatch"]},
            created_at=now - timedelta(days=2),
        )
        v2 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=bmc_module.id,
            version_number=2,
            version_name="Revised Pricing Model",
            is_active=False,
            data={"value_propositions": ["Hardware-as-a-service lease", "24/7 SLA"]},
            created_at=now - timedelta(days=1),
        )
        v3 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=bmc_module.id,
            version_number=3,
            version_name="Production Go-to-Market",
            is_active=True,
            data={"value_propositions": ["Turnkey enterprise automation", "Fleet analytics"]},
            created_at=now,
        )
        db.add_all([v1, v2, v3])
        db.flush()
        bmc_module.active_version_id = v3.id

        # Add 5 roadmap tasks
        for idx in range(1, 6):
            t = RoadmapTask(
                id=gen_id("task_"),
                project_id=proj_1.id,
                task_code=f"TSK-{idx:03d}",
                title=f"Baseline Milestone {idx}",
                description=f"Core milestone description for phase {idx}",
                phase=f"Phase {idx}",
                timeline=f"Month {idx}",
                start_date=f"2026-10-{idx:02d}",
                end_date=f"2026-10-{idx+10:02d}",
                priority="High" if idx <= 2 else "Medium",
                status="Completed" if idx == 1 else "In Progress" if idx == 2 else "Pending",
                assigned_to="Lead Robotics Engineer",
                order_index=idx,
                is_ai_generated=False,
                is_overloaded=False,
                steps=["Step A", "Step B"],
                created_at=now,
                updated_at=now,
            )
            db.add(t)

        # Add 4 copilot messages
        for m_idx in range(1, 5):
            msg = CopilotMessage(
                id=gen_id("msg_"),
                project_id=proj_1.id,
                role="user" if m_idx % 2 == 1 else "assistant",
                content=f"Synthetic conversation turn {m_idx} regarding architecture roadmap.",
                created_at=now,
            )
            db.add(msg)

        # 3. User Ten: 10 projects
        user_10 = User(
            id=gen_id("usr_"),
            username="baseline_user_ten",
            email="ten@example.internal",
            hashed_password=hash_password("Password123!"),
            terms_accepted=True,
            created_at=now,
        )
        db.add(user_10)
        sess_10 = DBSession(
            id=gen_id("sess_"),
            user_id=user_10.id,
            session_token="token_ten_projects_baseline",
            expires_at=now + timedelta(days=7),
            created_at=now,
        )
        db.add(sess_10)

        for p_idx in range(1, 11):
            p = Project(
                id=f"proj_baseline_ten_{p_idx:02d}",
                user_id=user_10.id,
                name=f"Portfolio Venture {p_idx:02d}",
                stage="Idea / MVP",
                description=f"Synthetic test project {p_idx} description.",
                industry="Software",
                target_customers="SMB Developers",
                goals=f"Launch target beta {p_idx}",
                business_context="SaaS",
                budget="$10,000",
                existing_stack={},
                active_module="overview",
                created_at=now,
                updated_at=now,
            )
            db.add(p)

        db.commit()

        return {
            "token_0": sess_0.session_token,
            "token_1": sess_1.session_token,
            "token_10": sess_10.session_token,
            "proj_1_id": proj_1.id,
        }
    finally:
        db.close()


def run_measurement(
    client: TestClient,
    method: str,
    path: str,
    token: str = "",
    headers: Dict[str, str] = None,
) -> Dict[str, Any]:
    """Execute a single measurement against the client and capture status, duration, SQL counters, and bytes."""
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"

    res = client.request(method, path, headers=h)

    # Extract Server-Timing header if present
    st_header = res.headers.get("Server-Timing", "")
    total_dur_ms = None
    for part in st_header.split(","):
        part = part.strip()
        if part.startswith("total;dur="):
            try:
                total_dur_ms = float(part.split("=")[1])
            except (IndexError, ValueError):
                pass

    return {
        "status": res.status_code,
        "duration_ms": total_dur_ms or 0.0,
        "response_bytes": len(res.content),
        "server_timing": st_header,
    }


def main():
    print("Initializing isolated baseline measurement harness...")
    seeds = seed_harness_data()
    print("Seed data successfully created.")

    # We also execute a direct SQL statement counter inspection per endpoint
    from app.core.diagnostics import _current_diagnostics, RequestDiagnostics

    test_plan = [
        ("Process Liveness", "GET", "/health/live", "", "Zero auth, zero DB process health probe"),
        ("Session / Auth Check", "GET", "/api/auth/me", seeds["token_1"], "Authentication & user resolution"),
        ("Project Listing (0 Projects)", "GET", "/api/projects", seeds["token_0"], "Empty portfolio listing"),
        ("Project Listing (1 Project)", "GET", "/api/projects", seeds["token_1"], "Single project response formatting"),
        ("Project Listing (10 Projects)", "GET", "/api/projects", seeds["token_10"], "Full user portfolio listing"),
        ("Module Detail (3 Versions)", "GET", f"/api/projects/{seeds['proj_1_id']}/modules/bmc", seeds["token_1"], "Module JSON and version history"),
        ("Task Summary", "GET", f"/api/projects/{seeds['proj_1_id']}/tasks/summary", seeds["token_1"], "Roadmap milestone progress aggregates"),
        ("Copilot History", "GET", f"/api/projects/{seeds['proj_1_id']}/copilot", seeds["token_1"], "Bounded synthetic LLM history read"),
    ]

    print("\nExecuting baseline benchmarks with PERF_DIAGNOSTICS=true...\n")
    results = []

    for name, method, path, token, desc in test_plan:
        h = {"Authorization": f"Bearer {token}"} if token else {}
        res = client.request(method, path, headers=h)

        # Extract statement and commit counts from middleware diagnostic headers
        stmt_count = int(res.headers.get("X-SQL-Statements", 0))
        commit_count = int(res.headers.get("X-SQL-Commits", 0))

        # Extract total duration from Server-Timing
        st_header = res.headers.get("Server-Timing", "")
        dur_ms = 0.0
        for part in st_header.split(","):
            part = part.strip()
            if part.startswith("total;dur="):
                try:
                    dur_ms = float(part.split("=")[1])
                except (IndexError, ValueError):
                    pass

        results.append({
            "name": name,
            "path": path,
            "method": method,
            "status": res.status_code,
            "statements": stmt_count,
            "commits": commit_count,
            "bytes": len(res.content),
            "local_dur_ms": dur_ms,
            "env": "Disposable SQLite (Local)",
            "desc": desc,
        })

    # Print Markdown Table
    print("| Endpoint | Dataset | Status | SQL statements | Commits | Response bytes | Local duration | Environment |")
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in results:
        print(f"| `{r['method']} {r['path']}` | {r['name']} | {r['status']} | {r['statements']} | {r['commits']} | {r['bytes']} B | {r['local_dur_ms']:.1f} ms | {r['env']} |")

    # Cleanup temporary database
    engine.dispose()
    try:
        if _tmp_db_path.exists():
            _tmp_db_path.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    main()
