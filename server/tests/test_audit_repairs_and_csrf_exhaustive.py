import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, generate_csrf_token
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    AIOperation, AuditLog, Session as DbSession, gen_id
)
from app.db.session import SessionLocal
from app.core.admin_provisioning import provision_initial_admin
from app.api.modules import _reconcile_roadmap_tasks

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def registered_user(db):
    uid = uuid.uuid4().hex[:8]
    username = f"audit_user_{uid}"
    email = f"{username}@test.com"
    password = "SecurePassword123!"

    user = User(
        id=gen_id("usr_"),
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role="user",
        is_suspended=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = TestClient(app)
    login_resp = client.post("/api/auth/login", json={
        "email_or_username": username,
        "password": password
    })
    assert login_resp.status_code == 200
    csrf_token = login_resp.json()["csrf_token"]

    return {
        "client": client,
        "user": user,
        "username": username,
        "password": password,
        "csrf_token": csrf_token
    }

@pytest.fixture
def test_project(db, registered_user):
    user = registered_user["user"]
    proj = Project(
        id=gen_id("proj_"),
        name="Audit Test Corp",
        user_id=user.id,
        stage="MVP",
        industry="SaaS",
        description="Testing enterprise audit and CSRF fixes",
        target_customers="SMB Enterprises"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


# ==============================================================================
# PHASE 2: CSRF EXHAUSTIVE VALIDATION
# ==============================================================================

def test_csrf_missing_session_cookie(test_project):
    """Mutations without session cookie must fail with 401 Unauthorized."""
    anonymous_client = TestClient(app)
    resp = anonymous_client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "T-01",
        "phase": "Phase 1",
        "title": "Unauthenticated Task",
        "timeline": "Week 1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "priority": "Medium",
        "status": "Pending"
    }, headers={"X-CSRF-Token": "some_random_token"})
    assert resp.status_code == 401

def test_csrf_invalid_or_expired_session(test_project):
    """Mutations with invalid session cookie must fail with 401 Unauthorized."""
    client = TestClient(app)
    client.cookies.set("aba_session", "invalid_expired_session_token_12345")
    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "T-02",
        "phase": "Phase 1",
        "title": "Expired Session Task",
        "timeline": "Week 1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "priority": "Medium",
        "status": "Pending"
    }, headers={"X-CSRF-Token": "valid_looking_token"})
    assert resp.status_code == 401

def test_csrf_missing_csrf_header_rejected(registered_user, test_project):
    """Valid session cookie with missing X-CSRF-Token header must fail with 403 Forbidden."""
    client = registered_user["client"]
    # Send mutation WITHOUT X-CSRF-Token header
    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "T-03",
        "phase": "Phase 1",
        "title": "Missing CSRF Task",
        "timeline": "Week 1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "priority": "Medium",
        "status": "Pending"
    })
    assert resp.status_code == 403
    assert "CSRF" in resp.json().get("detail", "")

def test_csrf_invalid_csrf_header_rejected(registered_user, test_project):
    """Valid session cookie with mismatched/tampered X-CSRF-Token must fail with 403 Forbidden."""
    client = registered_user["client"]
    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "T-04",
        "phase": "Phase 1",
        "title": "Tampered CSRF Task",
        "timeline": "Week 1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "priority": "Medium",
        "status": "Pending"
    }, headers={"X-CSRF-Token": "tampered_csrf_token_value_xyz"})
    assert resp.status_code == 403
    assert "CSRF" in resp.json().get("detail", "")

def test_csrf_valid_session_and_token_succeeds(registered_user, test_project):
    """Valid session and valid CSRF header successfully executes state-changing mutation."""
    client = registered_user["client"]
    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "T-05",
        "phase": "Phase 1",
        "title": "Valid CSRF Task",
        "timeline": "Week 1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "priority": "High",
        "status": "Ongoing"
    }, headers={"X-CSRF-Token": registered_user["csrf_token"]})
    assert resp.status_code == 201
    assert resp.json()["task_code"] == "T-05"
    assert resp.json()["status"] == "Ongoing"

def test_csrf_me_endpoint_sets_csrf_cookie(registered_user):
    """Calling /api/auth/me sets the readable aba_csrf cookie so frontend can auto-recover."""
    client = registered_user["client"]
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert "aba_csrf" in resp.cookies
    assert resp.cookies["aba_csrf"] == registered_user["csrf_token"]

def test_admin_csrf_protection_and_user_isolation(registered_user, db):
    """Normal user cannot access admin mutation, and admin mutation without CSRF is blocked."""
    provision_initial_admin(db)
    normal_client = registered_user["client"]

    # Normal user blocked from admin endpoint
    resp = normal_client.post("/api/admin/maintenance/toggle", json={
        "enabled": True,
        "reason": "Security test"
    }, headers={
        "X-CSRF-Token": registered_user["csrf_token"]
    })
    assert resp.status_code == 403

    # Admin login
    admin_client = TestClient(app)
    admin_login = admin_client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "Hanny@BusinessArchitect"
    })
    assert admin_login.status_code == 200
    admin_csrf = admin_login.json()["csrf_token"]

    # Admin mutation without CSRF header rejected
    admin_no_csrf = admin_client.post("/api/admin/maintenance/toggle", json={
        "enabled": True,
        "reason": "Security test"
    })
    assert admin_no_csrf.status_code == 403

    # Admin mutation with CSRF header succeeds
    admin_with_csrf = admin_client.post("/api/admin/maintenance/toggle", json={
        "enabled": True,
        "reason": "Security test"
    }, headers={
        "X-CSRF-Token": admin_csrf
    })
    assert admin_with_csrf.status_code == 200


# ==============================================================================
# PHASE 3: 5-VERSION LIMIT CONFLICT RESOLUTION WITH PENDING INSTRUCTION
# ==============================================================================

def test_version_conflict_resolution_with_instruction(registered_user, test_project, db):
    """
    When module reaches 5-version limit, resolving conflict with a pending instruction
    applies the instruction to active data and safely replaces the chosen version.
    """
    client = registered_user["client"]
    headers = {"X-CSRF-Token": registered_user["csrf_token"]}

    from app.services.version_service import VersionService
    module = VersionService.get_or_create_module(db, test_project.id, "bmc")

    # Create 5 versions to fill capacity
    v_ids = []
    for i in range(1, 6):
        data = {
            "tagline": f"Tagline v{i}",
            "customer_segments": [f"Segment {i}"],
            "value_propositions": [f"Value {i}"],
            "channels": [f"Channel {i}"],
            "customer_relationships": ["Automated"],
            "revenue_streams": ["SaaS Subscription"],
            "key_resources": ["Core Tech"],
            "key_activities": ["Dev"],
            "key_partnerships": ["Cloud"],
            "cost_structure": ["Hosting"]
        }
        v = VersionService.save_new_version(db, module, data, change_summary=f"Version {i}")
        v_ids.append(v.id)

    assert db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).count() == 5

    # Mock modify_section to verify instruction execution
    mock_modified_data = {
        "tagline": "AI Augmented Tagline",
        "customer_segments": ["Enterprise Segment"],
        "value_propositions": ["Scalable Value"],
        "channels": ["Direct Sales"],
        "customer_relationships": ["Dedicated"],
        "revenue_streams": ["Enterprise License"],
        "key_resources": ["Proprietary Models"],
        "key_activities": ["Enterprise Support"],
        "key_partnerships": ["Global SI"],
        "cost_structure": ["Compliance & Compute"]
    }

    with patch("app.api.modules.ai_service.modify_section", return_value=(mock_modified_data, "Applied AI instruction")):
        resolve_resp = client.post(
            f"/api/projects/{test_project.id}/modules/bmc/resolve-conflict",
            json={
                "replace_version_id": v_ids[0],
                "instruction": "Expand value proposition for enterprise clients"
            },
            headers=headers
        )
        assert resolve_resp.status_code == 200
        result = resolve_resp.json()
        assert result["data"]["tagline"] == "AI Augmented Tagline"
        assert result["data"]["customer_segments"] == ["Enterprise Segment"]
        assert any("Applied AI instruction" in (v.get("change_summary") or "") for v in result["versions"])

    # Verify total version count remains strictly 5
    assert db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).count() == 5


# ==============================================================================
# PHASE 4: ROADMAP TASK DEPENDENCIES & DATE VALIDATIONS
# ==============================================================================

def test_task_circular_dependency_rejected(registered_user, test_project):
    """Detect circular dependency graph and reject with 400 Bad Request."""
    client = registered_user["client"]
    headers = {"X-CSRF-Token": registered_user["csrf_token"]}

    # Create Task A
    t_a = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "TASK-A",
        "phase": "Phase 1",
        "title": "Architecture Setup",
        "timeline": "Week 1",
        "start_date": "2026-02-01",
        "end_date": "2026-02-05",
        "priority": "High",
        "status": "Pending",
        "dependencies": []
    }, headers=headers)
    assert t_a.status_code == 201

    # Create Task B depending on TASK-A
    t_b = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "TASK-B",
        "phase": "Phase 1",
        "title": "Database Schema",
        "timeline": "Week 2",
        "start_date": "2026-02-06",
        "end_date": "2026-02-10",
        "priority": "High",
        "status": "Pending",
        "dependencies": ["TASK-A"]
    }, headers=headers)
    assert t_b.status_code == 201

    # Attempt to update Task A to depend on TASK-B (creates circular dependency cycle: A -> B -> A)
    cycle_update = client.put(f"/api/projects/{test_project.id}/tasks/{t_a.json()['id']}", json={
        "dependencies": ["TASK-B"]
    }, headers=headers)
    assert cycle_update.status_code == 400
    assert "circular dependency" in cycle_update.json()["detail"].lower()

def test_task_self_dependency_rejected(registered_user, test_project):
    """Task cannot depend on itself."""
    client = registered_user["client"]
    headers = {"X-CSRF-Token": registered_user["csrf_token"]}

    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "SELF-01",
        "phase": "Phase 1",
        "title": "Self Dependent Task",
        "timeline": "Week 1",
        "start_date": "2026-02-01",
        "end_date": "2026-02-05",
        "priority": "Medium",
        "status": "Pending",
        "dependencies": ["SELF-01"]
    }, headers=headers)
    assert resp.status_code == 400
    assert "cannot depend on itself" in resp.json()["detail"].lower()

def test_task_invalid_date_range_rejected(registered_user, test_project):
    """Task with end_date before start_date must be rejected with 400."""
    client = registered_user["client"]
    headers = {"X-CSRF-Token": registered_user["csrf_token"]}

    resp = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "DATE-ERR",
        "phase": "Phase 1",
        "title": "Invalid Date Task",
        "timeline": "Week 1",
        "start_date": "2026-02-15",
        "end_date": "2026-02-01",  # End before start
        "priority": "Medium",
        "status": "Pending"
    }, headers=headers)
    assert resp.status_code == 400
    assert "cannot be earlier than start date" in resp.json()["detail"].lower()

def test_task_canonical_status_transitions(registered_user, test_project):
    """Verify canonical status vocabulary ('Pending', 'Ongoing', 'Finished') and alias 'In Progress'."""
    client = registered_user["client"]
    headers = {"X-CSRF-Token": registered_user["csrf_token"]}

    # Create with 'Ongoing'
    t1 = client.post(f"/api/projects/{test_project.id}/tasks", json={
        "task_code": "STAT-01",
        "phase": "Phase 1",
        "title": "Ongoing Task",
        "timeline": "Week 1",
        "start_date": "2026-02-01",
        "end_date": "2026-02-05",
        "priority": "High",
        "status": "Ongoing"
    }, headers=headers)
    assert t1.status_code == 201
    assert t1.json()["status"] == "Ongoing"

    # Transition to 'Finished'
    t1_done = client.put(f"/api/projects/{test_project.id}/tasks/{t1.json()['id']}", json={
        "status": "Finished"
    }, headers=headers)
    assert t1_done.status_code == 200
    assert t1_done.json()["status"] == "Finished"

    # Invalid status rejected
    t1_bad = client.put(f"/api/projects/{test_project.id}/tasks/{t1.json()['id']}", json={
        "status": "Completed"  # Not in allowed vocabulary
    }, headers=headers)
    assert t1_bad.status_code == 400

def test_roadmap_task_reconciliation_preserves_user_edits(test_project, db):
    """
    Reconciling generated tasks with existing tasks must preserve user-edited
    task status ('Ongoing', 'Finished') and not overwrite progress.
    """
    # Create an initial task and advance it to 'Ongoing'
    task1 = RoadmapTask(
        id=gen_id("tsk_"),
        project_id=test_project.id,
        task_code="REC-01",
        phase="Phase 1",
        title="Setup Cloud Environment",
        timeline="Week 1",
        start_date="2026-01-01",
        end_date="2026-01-05",
        priority="High",
        status="Ongoing",
        dependencies=[]
    )
    db.add(task1)
    db.commit()

    # Incoming newly generated tasks including REC-01 (regenerated) and REC-02 (new)
    incoming_tasks = [
        {
            "task_code": "REC-01",
            "phase": "Phase 1",
            "title": "Setup Cloud Environment - Regenerated",
            "timeline": "Week 1",
            "start_date": "2026-01-01",
            "end_date": "2026-01-06",
            "priority": "High",
            "status": "Pending",  # Regenerated says Pending
            "dependencies": []
        },
        {
            "task_code": "REC-02",
            "phase": "Phase 1",
            "title": "Configure Auth Service",
            "timeline": "Week 2",
            "start_date": "2026-01-07",
            "end_date": "2026-01-14",
            "priority": "Medium",
            "status": "Pending",
            "dependencies": ["REC-01"]
        }
    ]

    _reconcile_roadmap_tasks(db, test_project, incoming_tasks)

    # Verify task1 retained its user-edited 'Ongoing' status!
    t1_refreshed = db.query(RoadmapTask).filter(RoadmapTask.task_code == "REC-01", RoadmapTask.project_id == test_project.id).first()
    assert t1_refreshed is not None
    assert t1_refreshed.status == "Ongoing"  # Not reverted to Pending!

    # Verify new task was added
    t2_new = db.query(RoadmapTask).filter(RoadmapTask.task_code == "REC-02", RoadmapTask.project_id == test_project.id).first()
    assert t2_new is not None
    assert t2_new.status == "Pending"
