"""Phase 6 Verification: Generation Validation, Roadmap Semantics and Retry Intent.

Covers:
1. Invalid planning request returns controlled 422 with zero provider calls.
2. Missing/foreign task references rejected with structured MISSING_PREREQUISITE.
3. Dependency cycles detected without silent edge removal (CIRCULAR_DEPENDENCY).
4. Invalid dates rejected without silent clamping (INVALID_DATE_RANGE & SCHEDULE_CONFLICT).
5. Valid equality boundary (same-day handover: start_date == prerequisite.end_date) accepted.
6. Admin retry preserves original user planning intent (does not guess with default inputs).
7. Unsupported legacy retry returns controlled 400 explanation without guessing.
8. Provider success plus persistence conflict (version capacity) preserves existing content.
9. Snapshot and working task relational table consistency after successful paths.
"""

from datetime import date, datetime, timedelta, timezone
import secrets
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    AIOperation, AuditLog, Session as DBSession, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.schemas.modules import RoadmapPlanningRequest, ExecutionRoadmapData
from app.services.roadmap_service import RoadmapDomainService
from app.services.task_graph_validator import (
    IncompatibleTaskGraphError, TaskGraphNode, validate_candidate_task_graph
)
from app.services.version_service import VersionService
from app.core.telemetry import record_ai_operation


@pytest.fixture
def auth_setup():
    """Create isolated test user, project, and session."""
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        u = User(
            id=gen_id("usr_"),
            username=f"p6_user_{uid}",
            email=f"p6_user_{uid}@example.com",
            hashed_password=hash_password("UserPassword123!"),
            role="user",
            is_suspended=False
        )
        db.add(u)
        p = Project(
            id=gen_id("proj_"),
            name="Roadmap Semantics Blueprint",
            user_id=u.id,
            stage="Idea / MVP",
            description="Production architectural validation for roadmap semantics and retry intent",
            industry="Enterprise Software",
            target_customers="Enterprise engineering leads",
            goals="Enforce rigorous graph invariants",
            budget="$10,000 - $50,000",
            business_context="High reliability project management software"
        )
        db.add(p)
        raw_tok = generate_session_token()
        s = DBSession(
            id=gen_id("ses_"),
            user_id=u.id,
            token_digest=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(s)
        db.commit()

        user_id = u.id
        project_id = p.id

    client = TestClient(app)
    client.cookies.set("aba_session", raw_tok)
    client.headers["X-CSRF-Token"] = generate_csrf_token(raw_tok)

    return {
        "client": client,
        "user_id": user_id,
        "project_id": project_id,
        "raw_token": raw_tok
    }


@pytest.fixture
def admin_setup():
    """Create isolated admin user, target project, and session."""
    aid = secrets.token_hex(4)
    with SessionLocal() as db:
        admin = User(
            id=gen_id("usr_"),
            username=f"p6_admin_{aid}",
            email=f"p6_admin_{aid}@example.com",
            hashed_password=hash_password("AdminPassword123!"),
            role="super_admin",
            is_suspended=False
        )
        db.add(admin)
        p = Project(
            id=gen_id("proj_"),
            name="Admin Recovery Project",
            user_id=admin.id,
            stage="Idea / MVP",
            description="Validating administrative recovery and retry intent",
            industry="Enterprise Software",
            target_customers="Platform engineers",
            goals="Verify retry lineage",
            budget="$10,000 - $50,000",
            business_context="Operational recovery testing"
        )
        db.add(p)
        raw_tok = generate_session_token()
        s = DBSession(
            id=gen_id("ses_"),
            user_id=admin.id,
            token_digest=hash_session_token(raw_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(s)
        db.commit()

        admin_id = admin.id
        project_id = p.id

    client = TestClient(app)
    client.cookies.set("aba_session", raw_tok)
    client.headers["X-CSRF-Token"] = generate_csrf_token(raw_tok)

    return {
        "client": client,
        "admin_id": admin_id,
        "project_id": project_id,
        "raw_token": raw_tok
    }


# ==============================================================================
# 1. Request Validation Preflight (Zero provider calls)
# ==============================================================================

def test_invalid_planning_request_returns_422_with_zero_provider_calls(auth_setup):
    """Invalid planning input must produce controlled 422 before any provider call."""
    client = auth_setup["client"]
    pid = auth_setup["project_id"]

    with patch("app.ai.gemini_service.ai_service.generate_roadmap") as mock_gen:
        # Invalid horizon_weeks (< 1)
        resp = client.post(
            f"/api/projects/{pid}/modules/execution_roadmap/generate",
            json={"planning_inputs": {"horizon_weeks": -1}}
        )
        assert resp.status_code == 422
        assert mock_gen.call_count == 0

        # Invalid start_date
        resp2 = client.post(
            f"/api/projects/{pid}/modules/execution_roadmap/generate",
            json={"planning_inputs": {"start_date": "not-a-valid-date"}}
        )
        assert resp2.status_code == 422
        assert mock_gen.call_count == 0

        # Invalid checklist item status
        resp3 = client.post(
            f"/api/projects/{pid}/modules/execution_roadmap/generate",
            json={"planning_inputs": {"checklist": [{"item": "Plan architecture", "status": "InvalidStatus"}]}}
        )
        assert resp3.status_code == 422
        assert mock_gen.call_count == 0


# ==============================================================================
# 2. Missing/Foreign Task References
# ==============================================================================

def test_missing_foreign_task_references_rejected(auth_setup):
    """Tasks depending on nonexistent or foreign task codes must be rejected with MISSING_PREREQUISITE."""
    pid = auth_setup["project_id"]
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == pid).first()
        tasks = [
            {
                "task_code": "TSK-01",
                "phase": "Planning",
                "title": "System Design",
                "start_date": "2026-06-01",
                "end_date": "2026-06-05",
                "dependencies": ["TSK-99"]  # TSK-99 does not exist in graph
            }
        ]
        with pytest.raises(IncompatibleTaskGraphError) as exc_info:
            RoadmapDomainService.reconcile_roadmap_tasks(db, proj, tasks)

        assert exc_info.value.error_code == "MISSING_PREREQUISITE"
        assert "TSK-99" in exc_info.value.missing_prerequisite_codes


# ==============================================================================
# 3. Cycles: Detected and NOT Silently Removed
# ==============================================================================

def test_circular_dependency_detected_and_not_silently_removed(auth_setup):
    """Circular dependency must be rejected with CIRCULAR_DEPENDENCY and NOT silently broken."""
    tasks = [
        {
            "task_code": "TSK-01",
            "phase": "Architecture",
            "title": "Component Design",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "dependencies": ["TSK-02"]
        },
        {
            "task_code": "TSK-02",
            "phase": "Architecture",
            "title": "Data Modeling",
            "start_date": "2026-06-05",
            "end_date": "2026-06-10",
            "dependencies": ["TSK-01"]
        }
    ]

    # Verify normalize_roadmap_schedule does NOT silently strip edges
    planning = RoadmapPlanningRequest(start_date=date(2026, 6, 1))
    normalized = RoadmapDomainService.normalize_roadmap_schedule({"tasks": tasks}, planning)
    normalized_tasks = normalized["tasks"]
    assert "TSK-02" in normalized_tasks[0]["dependencies"]
    assert "TSK-01" in normalized_tasks[1]["dependencies"]

    # Verify candidate graph validation rejects with CIRCULAR_DEPENDENCY
    pid = auth_setup["project_id"]
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == pid).first()
        with pytest.raises(IncompatibleTaskGraphError) as exc_info:
            RoadmapDomainService.reconcile_roadmap_tasks(db, proj, normalized_tasks)

        assert exc_info.value.error_code == "CIRCULAR_DEPENDENCY"
        assert "TSK-01" in exc_info.value.affected_task_codes
        assert "TSK-02" in exc_info.value.affected_task_codes


# ==============================================================================
# 4. Invalid Dates: Rejected and NOT Silently Clamped
# ==============================================================================

def test_invalid_dates_rejected_and_not_silently_clamped(auth_setup):
    """Tasks with end_date < start_date or dependent < prerequisite must not be silently clamped."""
    future_base = date.today() + timedelta(days=60)
    start_str = (future_base + timedelta(days=10)).isoformat()
    end_str = (future_base + timedelta(days=5)).isoformat()
    tasks = [
        {
            "task_code": "TSK-01",
            "phase": "Implementation",
            "title": "Backend API",
            "start_date": start_str,
            "end_date": end_str,  # Inverted date range
            "dependencies": []
        }
    ]

    planning = RoadmapPlanningRequest(start_date=future_base)
    normalized = RoadmapDomainService.normalize_roadmap_schedule({"tasks": tasks}, planning)
    norm_task = normalized["tasks"][0]
    # Verify it was NOT silently clamped to start + 6 days
    assert norm_task["start_date"] == start_str
    assert norm_task["end_date"] == end_str

    pid = auth_setup["project_id"]
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == pid).first()
        with pytest.raises(IncompatibleTaskGraphError) as exc_info:
            RoadmapDomainService.reconcile_roadmap_tasks(db, proj, normalized["tasks"])

        assert exc_info.value.error_code == "INVALID_DATE_RANGE"

    # Schedule conflict: dependent commences strictly before prerequisite finishes
    schedule_conflict_tasks = [
        {
            "task_code": "TSK-01",
            "phase": "Phase 1",
            "title": "Foundation",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "dependencies": []
        },
        {
            "task_code": "TSK-02",
            "phase": "Phase 2",
            "title": "Dependent Work",
            "start_date": "2026-06-08",  # Starts 2 days BEFORE TSK-01 finishes
            "end_date": "2026-06-15",
            "dependencies": ["TSK-01"]
        }
    ]
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == pid).first()
        with pytest.raises(IncompatibleTaskGraphError) as exc_info2:
            RoadmapDomainService.reconcile_roadmap_tasks(db, proj, schedule_conflict_tasks)

        assert exc_info2.value.error_code == "SCHEDULE_CONFLICT"


# ==============================================================================
# 5. Valid Equality Boundary (Same-day handover)
# ==============================================================================

def test_valid_equality_boundary_same_day_handover_accepted(auth_setup):
    """Same-day handover (dependent.start_date == prerequisite.end_date) is completely valid."""
    tasks = [
        {
            "task_code": "TSK-01",
            "phase": "Phase 1",
            "title": "Prerequisite Handover",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "dependencies": []
        },
        {
            "task_code": "TSK-02",
            "phase": "Phase 2",
            "title": "Dependent Commencing",
            "start_date": "2026-06-10",  # Exact boundary equality: starts on prerequisite end date
            "end_date": "2026-06-15",
            "dependencies": ["TSK-01"]
        }
    ]

    nodes = [
        TaskGraphNode(
            task_code=t["task_code"],
            start_date=t["start_date"],
            end_date=t["end_date"],
            dependencies=t["dependencies"]
        )
        for t in tasks
    ]
    # Must validate cleanly with zero exceptions
    validate_candidate_task_graph(nodes, project_id=auth_setup["project_id"], structured_error=True)

    pid = auth_setup["project_id"]
    with SessionLocal() as db:
        proj = db.query(Project).filter(Project.id == pid).first()
        reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, proj, tasks)
        db.commit()

        assert len(reconciled) == 2
        t2 = db.query(RoadmapTask).filter(RoadmapTask.project_id == pid, RoadmapTask.task_code == "TSK-02").first()
        assert t2.dependencies == ["TSK-01"]
        assert t2.start_date == "2026-06-10"


# ==============================================================================
# 6. Retry Preserves Original User Planning Intent
# ==============================================================================

def test_retry_preserves_original_user_planning_intent(admin_setup):
    """Admin retry must recover and use the original user planning inputs rather than generic defaults."""
    client = admin_setup["client"]
    pid = admin_setup["project_id"]
    admin_id = admin_setup["admin_id"]

    # Simulate a user-specific failed roadmap generation that recorded original planning intent
    custom_planning = {
        "start_date": "2026-09-01",
        "horizon_weeks": 24,
        "team_capacity": "3 senior engineers",
        "completed_work": "Discovery and market sizing",
        "checklist": [{"item": "Core Engine", "status": "In progress"}]
    }

    with SessionLocal() as db:
        failed_op = record_ai_operation(
            db,
            module_type="execution_roadmap",
            operation_type="generate",
            model_name=settings.GEMINI_MODEL,
            duration_ms=5000,
            status="failed",
            user_id=admin_id,
            project_id=pid,
            error_category="timeout",
            error_message="Provider deadline exceeded",
            structured_validation_passed=False,
            persistence_status="failed",
            is_retryable=True,
            retry_context={
                "module_type": "execution_roadmap",
                "operation_type": "generate",
                "planning_inputs": custom_planning
            }
        )
        assert failed_op is not None
        op_id = failed_op.id

    captured_inputs = {}

    def mock_generate_roadmap(project_info, planning_inputs, *args, **kwargs):
        captured_inputs.update(planning_inputs or {})
        return {
            "tasks": [
                {
                    "task_code": "TSK-01",
                    "phase": "Delivery",
                    "title": "Recovered Task",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-07",
                    "dependencies": []
                }
            ],
            "phases": [{"name": "Delivery", "color": "#2563eb", "start_date": "2026-09-01", "end_date": "2026-09-07"}]
        }

    with patch("app.ai.gemini_service.ai_service.generate_roadmap", side_effect=mock_generate_roadmap):
        resp = client.post(f"/api/admin/ai-operations/{op_id}/retry")

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Crucial assertion: provider was called with the ORIGINAL user planning inputs, NOT defaults!
    assert captured_inputs.get("start_date") == "2026-09-01"
    assert captured_inputs.get("horizon_weeks") == 24
    assert captured_inputs.get("team_capacity") == "3 senior engineers"

    # Verify persisted version data retained planning_inputs
    with SessionLocal() as db:
        mod = db.query(ModuleContent).filter(ModuleContent.project_id == pid, ModuleContent.module_type == "execution_roadmap").first()
        ver = db.query(ModuleVersion).filter(ModuleVersion.id == mod.active_version_id).first()
        assert ver.data["planning_inputs"]["start_date"] == "2026-09-01"
        assert ver.data["planning_inputs"]["horizon_weeks"] == 24


# ==============================================================================
# 7. Unsupported Legacy Retry
# ==============================================================================

def test_unsupported_legacy_retry_returns_controlled_explanation(admin_setup):
    """Legacy failed operations with no retained intent must return controlled 400 without guessing."""
    client = admin_setup["client"]
    pid = admin_setup["project_id"]
    admin_id = admin_setup["admin_id"]

    with SessionLocal() as db:
        # Create module and active version for modification context
        mod = VersionService.get_or_create_module(db, pid, "execution_roadmap")
        VersionService.save_new_version(
            db,
            mod,
            data={"phases": [], "tasks": []},
            change_summary="Initial version",
            custom_name="V1"
        )
        db.commit()

        # Simulate legacy operation: NO retry_context passed
        failed_op = record_ai_operation(
            db,
            module_type="execution_roadmap",
            operation_type="modify",
            model_name=settings.GEMINI_MODEL,
            duration_ms=4000,
            status="failed",
            user_id=admin_id,
            project_id=pid,
            error_category="timeout",
            error_message="Legacy failure before intent tracking",
            structured_validation_passed=False,
            persistence_status="failed",
            is_retryable=True,
            retry_context=None  # Legacy
        )
        op_id = failed_op.id

    with patch("app.ai.gemini_service.ai_service.modify_section") as mock_mod:
        resp = client.post(f"/api/admin/ai-operations/{op_id}/retry")

    assert resp.status_code == 400
    assert "original modification instruction was not retained for this legacy operation and cannot be recovered" in resp.json()["detail"]
    assert mock_mod.call_count == 0  # Did not guess or call provider


# ==============================================================================
# 8. Provider Success Plus Persistence Conflict
# ==============================================================================

def test_provider_success_plus_persistence_conflict_preserves_content(auth_setup):
    """When provider succeeds but persistence encounters version capacity conflict, content is preserved."""
    client = auth_setup["client"]
    pid = auth_setup["project_id"]

    with SessionLocal() as db:
        mod = VersionService.get_or_create_module(db, pid, "execution_roadmap")
        # Populate 5 versions (maximum allowed capacity)
        for i in range(1, 6):
            VersionService.save_new_version(
                db=db,
                module=mod,
                data={
                    "tasks": [
                        {
                            "task_code": f"TSK-{i:02d}",
                            "phase": "Delivery",
                            "title": f"Initial Version {i}",
                            "start_date": "2026-06-01",
                            "end_date": "2026-06-07",
                            "dependencies": []
                        }
                    ],
                    "phases": [{"name": "Delivery", "start_date": "2026-06-01", "end_date": "2026-06-07"}]
                },
                change_summary=f"Version {i}"
            )
        initial_active = mod.active_version_id
        initial_ver = db.query(ModuleVersion).filter(ModuleVersion.id == initial_active).first()
        initial_data = dict(initial_ver.data)

    mock_generated = {
        "tasks": [
            {
                "task_code": "TSK-99",
                "phase": "Delivery",
                "title": "6th Version Task That Should Fail Persistence",
                "start_date": "2026-06-01",
                "end_date": "2026-06-07",
                "dependencies": []
            }
        ],
        "phases": [{"name": "Delivery", "start_date": "2026-06-01", "end_date": "2026-06-07"}]
    }

    with patch("app.ai.gemini_service.ai_service.generate_roadmap", return_value=mock_generated):
        resp = client.post(f"/api/projects/{pid}/modules/execution_roadmap/generate")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "VERSION_LIMIT_EXCEEDED"

    # Verify initial active version remains completely untouched
    with SessionLocal() as db:
        mod = db.query(ModuleContent).filter(ModuleContent.project_id == pid, ModuleContent.module_type == "execution_roadmap").first()
        assert mod.active_version_id == initial_active
        ver = db.query(ModuleVersion).filter(ModuleVersion.id == initial_active).first()
        assert ver.data["tasks"][0]["title"] == initial_data["tasks"][0]["title"]
        # Ensure 6th version was not committed
        assert db.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod.id).count() == 5


# ==============================================================================
# 9. Snapshot & Working Task Consistency After Successful Path
# ==============================================================================

def test_snapshot_and_working_tasks_consistency_after_successful_generation(auth_setup):
    """Active version data and working RoadmapTask relational table must have 100% agreement."""
    client = auth_setup["client"]
    pid = auth_setup["project_id"]

    mock_generated = {
        "tasks": [
            {
                "task_code": "TSK-01",
                "phase": "Planning",
                "title": "Define Scope",
                "start_date": "2026-06-01",
                "end_date": "2026-06-05",
                "dependencies": []
            },
            {
                "task_code": "TSK-02",
                "phase": "Execution",
                "title": "Build Architecture",
                "start_date": "2026-06-05",  # Same-day handover boundary
                "end_date": "2026-06-15",
                "dependencies": ["TSK-01"]
            }
        ],
        "phases": [
            {"name": "Planning", "start_date": "2026-06-01", "end_date": "2026-06-05"},
            {"name": "Execution", "start_date": "2026-06-05", "end_date": "2026-06-15"}
        ]
    }

    with patch("app.ai.gemini_service.ai_service.generate_roadmap", return_value=mock_generated):
        resp = client.post(f"/api/projects/{pid}/modules/execution_roadmap/generate")

    assert resp.status_code == 200
    res_data = resp.json()["data"]

    with SessionLocal() as db:
        mod = db.query(ModuleContent).filter(ModuleContent.project_id == pid, ModuleContent.module_type == "execution_roadmap").first()
        active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == mod.active_version_id).first()
        db_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == pid).order_by(RoadmapTask.task_code).all()

        assert len(db_tasks) == len(res_data["tasks"]) == 2
        for snapshot_t, db_t in zip(active_ver.data["tasks"], db_tasks):
            assert snapshot_t["task_code"] == db_t.task_code
            assert snapshot_t["title"] == db_t.title
            assert snapshot_t["start_date"] == db_t.start_date
            assert snapshot_t["end_date"] == db_t.end_date
            assert snapshot_t["dependencies"] == (db_t.dependencies or [])
