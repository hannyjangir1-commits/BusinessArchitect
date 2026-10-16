import os
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import hash_password, verify_password, generate_csrf_token
from app.models.all_models import (
    User, Project, RoadmapTask, AIOperation, Session as DBSession,
    SecurityEvent, AuditLog, gen_id
)
from app.db.session import SessionLocal
from app.core.admin_provisioning import (
    seed_development_admin,
    validate_production_credentials_safety,
    KNOWN_DEV_PASSWORDS
)

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

def get_auth_cookies(client, username, password):
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    csrf = resp.json()["csrf_token"]
    cookies = dict(resp.cookies)
    headers = {"X-CSRF-Token": csrf}
    return cookies, headers

# -------------------------------------------------------------
# 1. Dev Bootstrap & Production Credential Safety
# -------------------------------------------------------------
def test_development_bootstrap_and_hannyadmin_login(client, db):
    """Verify local development seed idempotently creates HannyAdmin / HannyAdmin and allows login."""
    # Run seed
    seed_development_admin(db)
    admin = db.query(User).filter(User.username == "HannyAdmin").first()
    assert admin is not None
    assert admin.role == "super_admin"
    assert verify_password("HannyAdmin", admin.hashed_password) is True

    # Re-running seed is idempotent
    result = seed_development_admin(db)
    assert result is False

    # Login with HannyAdmin / HannyAdmin works
    login_resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["username"] == "HannyAdmin"
    assert data["user"]["role"] == "super_admin"
    assert "view_dashboard" in data["permissions"]

def test_production_safety_rejects_known_dev_credentials(monkeypatch):
    """Verify that in production environment, known development passwords raise RuntimeError."""
    monkeypatch.setattr(settings, "IS_PROD", True)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "HannyAdmin")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_credentials_safety()
    assert "insecure development credentials" in str(exc_info.value).lower()

    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError) as exc_info2:
        validate_production_credentials_safety()
    assert "at least 12 characters" in str(exc_info2.value)

    # Strong password passes
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "V3ry$tr0ng!Prod#Secret2026")
    validate_production_credentials_safety()

# -------------------------------------------------------------
# 2. Administrator Self-Sessions Listing & Revocation
# -------------------------------------------------------------
def test_admin_sessions_listing_and_revocation(client, db):
    """Verify admin can list own active sessions and revoke them."""
    seed_development_admin(db)
    cookies, headers = get_auth_cookies(client, "HannyAdmin", "HannyAdmin")

    # List sessions
    res = client.get("/api/admin/auth/sessions", cookies=cookies)
    assert res.status_code == 200
    sessions_data = res.json()
    sessions_list = sessions_data.get("sessions", sessions_data) if isinstance(sessions_data, dict) else sessions_data
    assert len(sessions_list) >= 1
    current_session = next((s for s in sessions_list if s["is_current"]), None)
    assert current_session is not None

    # Create a secondary session for HannyAdmin
    admin = db.query(User).filter(User.username == "HannyAdmin").first()
    sec_token = gen_id("tok_sec_")
    sec_session = DBSession(
        id=gen_id("ses_"),
        user_id=admin.id,
        session_token=sec_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db.add(sec_session)
    db.commit()

    # Re-fetch sessions
    res2 = client.get("/api/admin/auth/sessions", cookies=cookies)
    s2_list = res2.json().get("sessions", res2.json()) if isinstance(res2.json(), dict) else res2.json()
    assert any(s["id"] == sec_session.id for s in s2_list)

    # Revoke specific session
    revoke_res = client.post(
        f"/api/admin/auth/sessions/{sec_session.id}/revoke",
        cookies=cookies,
        headers=headers
    )
    assert revoke_res.status_code == 200

    # Verify secondary session is gone
    res3 = client.get("/api/admin/auth/sessions", cookies=cookies)
    s3_list = res3.json().get("sessions", res3.json()) if isinstance(res3.json(), dict) else res3.json()
    assert not any(s["id"] == sec_session.id for s in s3_list)

    # Test revoke-others endpoint
    sec_session2 = DBSession(
        id=gen_id("ses_"),
        user_id=admin.id,
        session_token=gen_id("tok_sec2_"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db.add(sec_session2)
    db.commit()

    rev_others_res = client.post(
        "/api/admin/auth/sessions/revoke-others",
        cookies=cookies,
        headers=headers
    )
    assert rev_others_res.status_code == 200

    res4 = client.get("/api/admin/auth/sessions", cookies=cookies)
    s4_list = res4.json().get("sessions", res4.json()) if isinstance(res4.json(), dict) else res4.json()
    assert len(s4_list) == 1
    assert s4_list[0]["is_current"] is True

# -------------------------------------------------------------
# 3. Role & Permission Authorization Matrix
# -------------------------------------------------------------
def test_admin_role_permission_matrix(client, db):
    """Verify backend enforces role-specific permissions and denies unauthorized requests."""
    seed_development_admin(db)

    # Create an Auditor account
    auditor = db.query(User).filter(User.username == "test_auditor_matrix").first()
    if not auditor:
        auditor = User(
            id=gen_id("usr_"),
            username="test_auditor_matrix",
            email="auditor_matrix@example.com",
            hashed_password=hash_password("AuditorMatrixPass1"),
            role="auditor",
            terms_accepted=True
        )
        db.add(auditor)
        db.commit()

    aud_cookies, aud_headers = get_auth_cookies(client, "test_auditor_matrix", "AuditorMatrixPass1")

    # Auditor CAN view dashboard
    dash_res = client.get("/api/admin/dashboard/stats", cookies=aud_cookies)
    assert dash_res.status_code == 200

    # Auditor CANNOT manage users
    user_res = client.post("/api/admin/users", json={
        "username": "unauthorized_user_create",
        "email": "unauth@example.com",
        "password": "Password123"
    }, cookies=aud_cookies, headers=aud_headers)
    assert user_res.status_code == 403

    # Auditor CANNOT manage projects
    transfer_res = client.post("/api/admin/projects/proj_fake/transfer", json={
        "new_owner_username": "nobody"
    }, cookies=aud_cookies, headers=aud_headers)
    assert transfer_res.status_code == 403

# -------------------------------------------------------------
# 4. User Management Actions & Last Super-Admin Protection
# -------------------------------------------------------------
def test_user_management_crud_and_last_super_admin_guard(client, db):
    """Test user creation, update, suspension, session revocation, and last super admin protection."""
    seed_development_admin(db)
    super_cookies, super_headers = get_auth_cookies(client, "HannyAdmin", "HannyAdmin")
    hanny = db.query(User).filter(User.username == "HannyAdmin").first()

    # 1. Create new user
    uname = f"test_user_{int(datetime.now().timestamp())}"
    create_res = client.post("/api/admin/users", json={
        "username": uname,
        "email": f"{uname}@example.com",
        "password": "SecurePassword123",
        "role": "operations_admin"
    }, cookies=super_cookies, headers=super_headers)
    assert create_res.status_code in (200, 201)
    created_res_data = create_res.json()
    created_user = created_res_data.get("user", created_res_data)
    user_id = created_user["id"]
    assert created_user["username"] == uname
    assert created_user["role"] == "operations_admin"

    # 2. Update user
    update_res = client.put(f"/api/admin/users/{user_id}", json={
        "role": "support_admin"
    }, cookies=super_cookies, headers=super_headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert (updated_data.get("user", updated_data))["role"] == "support_admin"

    # 3. Suspend and Reactivate
    susp_res = client.post(f"/api/admin/users/{user_id}/suspend", json={
        "reason": "Administrative testing"
    }, cookies=super_cookies, headers=super_headers)
    assert susp_res.status_code == 200
    assert susp_res.json()["is_suspended"] is True

    react_res = client.post(f"/api/admin/users/{user_id}/reactivate", cookies=super_cookies, headers=super_headers)
    assert react_res.status_code == 200
    assert react_res.json()["is_suspended"] is False

    # 4. Revoke sessions for user
    rev_res = client.post(f"/api/admin/users/{user_id}/revoke-sessions", cookies=super_cookies, headers=super_headers)
    assert rev_res.status_code == 200

    # 5. Delete the test user
    del_res = client.delete(f"/api/admin/users/{user_id}?confirm_username={uname}", cookies=super_cookies, headers=super_headers)
    assert del_res.status_code == 200

    # 6. LAST USABLE SUPER ADMIN PROTECTION:
    # Ensure hanny is the only active super admin in test database
    db.query(User).filter(User.role == "super_admin", User.id != hanny.id).delete()
    db.commit()

    # Attempting to delete own account is rejected
    del_hanny_res = client.delete(
        f"/api/admin/users/{hanny.id}?confirm_username=HannyAdmin",
        cookies=super_cookies,
        headers=super_headers
    )
    assert del_hanny_res.status_code == 400
    assert "cannot delete their own account" in del_hanny_res.json()["detail"].lower()

    # Attempting to demote the last super admin is rejected with 400
    demote_res = client.put(
        f"/api/admin/users/{hanny.id}",
        json={"role": "user"},
        cookies=super_cookies,
        headers=super_headers
    )
    assert demote_res.status_code == 400
    assert "last active super admin" in demote_res.json()["detail"].lower()

    # Attempting to suspend own account is rejected with 400
    susp_hanny_res = client.post(
        f"/api/admin/users/{hanny.id}/suspend",
        json={"reason": "test"},
        cookies=super_cookies,
        headers=super_headers
    )
    assert susp_hanny_res.status_code == 400
    assert "cannot suspend their own account" in susp_hanny_res.json()["detail"].lower()

# -------------------------------------------------------------
# 5. Project Management Actions & Transaction Safety
# -------------------------------------------------------------
def test_project_management_ownership_transfer_and_deletion(client, db):
    """Test project listing, detail, transactional ownership transfer, and safe deletion."""
    seed_development_admin(db)
    super_cookies, super_headers = get_auth_cookies(client, "HannyAdmin", "HannyAdmin")

    hanny = db.query(User).filter(User.username == "HannyAdmin").first()

    # Create a secondary user for transfer
    target_user = db.query(User).filter(User.username == "target_transfer_user").first()
    if not target_user:
        target_user = User(
            id=gen_id("usr_"),
            username="target_transfer_user",
            email="target_transfer@example.com",
            hashed_password=hash_password("TargetPass123"),
            role="user",
            terms_accepted=True
        )
        db.add(target_user)
        db.commit()

    # Create a test project
    test_proj = Project(
        id=gen_id("prj_"),
        user_id=hanny.id,
        name="Test Governance Project",
        stage="mvp",
        description="Testing admin governance"
    )
    db.add(test_proj)
    db.commit()

    # 1. Project Detail
    det_res = client.get(f"/api/admin/projects/{test_proj.id}", cookies=super_cookies)
    assert det_res.status_code == 200
    assert det_res.json()["project"]["name"] == "Test Governance Project"

    # 2. Failed Transfer (invalid username) must rollback and leave ownership unchanged
    fail_transfer = client.post(
        f"/api/admin/projects/{test_proj.id}/transfer",
        json={"new_owner_username": "non_existent_user_999"},
        cookies=super_cookies,
        headers=super_headers
    )
    assert fail_transfer.status_code == 404
    db.refresh(test_proj)
    assert test_proj.user_id == hanny.id

    # 3. Successful Transfer
    succ_transfer = client.post(
        f"/api/admin/projects/{test_proj.id}/transfer",
        json={"new_owner_username": "target_transfer_user"},
        cookies=super_cookies,
        headers=super_headers
    )
    assert succ_transfer.status_code == 200
    db.refresh(test_proj)
    assert test_proj.user_id == target_user.id

    # 4. Deletion with incorrect confirmation name fails
    bad_del = client.delete(
        f"/api/admin/projects/{test_proj.id}?confirm_project_name=WrongName",
        cookies=super_cookies,
        headers=super_headers
    )
    assert bad_del.status_code == 400

    # 5. Successful deletion
    succ_del = client.delete(
        f"/api/admin/projects/{test_proj.id}?confirm_project_name=Test Governance Project",
        cookies=super_cookies,
        headers=super_headers
    )
    assert succ_del.status_code == 200
    assert db.query(Project).filter(Project.id == test_proj.id).first() is None

# -------------------------------------------------------------
# 6. Empty Dashboard & Empty AI Activity Data
# -------------------------------------------------------------
def test_empty_dashboard_and_ai_activity(client, db):
    """Verify that empty database or empty time window returns stable numeric values without errors."""
    seed_development_admin(db)
    super_cookies, super_headers = get_auth_cookies(client, "HannyAdmin", "HannyAdmin")

    # Fetch stats with 24h range
    stats_res = client.get("/api/admin/dashboard/stats?range=24h", cookies=super_cookies)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert isinstance(stats["users"]["total"], int)
    assert isinstance(stats["projects"]["total"], int)
    assert isinstance(stats["ai"]["success_rate"], (int, float))
    assert isinstance(stats["ai"]["total_operations"], int)

    # Fetch trends
    trends_res = client.get("/api/admin/dashboard/trends?range=24h", cookies=super_cookies)
    assert trends_res.status_code == 200
    assert "points" in trends_res.json()

    # AI Quality metrics
    qual_res = client.get("/api/admin/ai-operations/quality", cookies=super_cookies)
    assert qual_res.status_code == 200
    qual = qual_res.json()
    assert isinstance(qual["structured_validation_rate"], (int, float))
    assert isinstance(qual["parse_failures"], int)

# -------------------------------------------------------------
# 7. AI Retry Protections
# -------------------------------------------------------------
def test_ai_retry_protections(client, db):
    """Verify retry protections: cannot retry success, non-retryable, missing project, or duplicate."""
    seed_development_admin(db)
    super_cookies, super_headers = get_auth_cookies(client, "HannyAdmin", "HannyAdmin")

    hanny = db.query(User).filter(User.username == "HannyAdmin").first()

    # Create successful operation
    succ_op = AIOperation(
        id=gen_id("aio_"),
        request_id="req_succ_1",
        user_id=hanny.id,
        module_type="bmc",
        operation_type="generate",
        model_name="gemini-2.5-flash",
        status="success",
        duration_ms=1200,
        is_retryable=False
    )
    db.add(succ_op)
    db.commit()

    # 1. Attempt retry on successful operation -> 400
    res1 = client.post(f"/api/admin/ai-operations/{succ_op.id}/retry", cookies=super_cookies, headers=super_headers)
    assert res1.status_code == 400
    assert "already successful" in res1.json()["detail"].lower()

    # 2. Failed operation with no project context -> 400
    no_proj_op = AIOperation(
        id=gen_id("aio_"),
        request_id="req_fail_1",
        user_id=hanny.id,
        project_id=None,
        module_type="bmc",
        operation_type="generate",
        model_name="gemini-2.5-flash",
        duration_ms=500,
        status="failed",
        error_category="network_error",
        error_message="Connection timed out",
        is_retryable=True
    )
    db.add(no_proj_op)
    db.commit()

    res2 = client.post(f"/api/admin/ai-operations/{no_proj_op.id}/retry", cookies=super_cookies, headers=super_headers)
    assert res2.status_code == 400
    assert "no associated project context" in res2.json()["detail"].lower()

    # 3. Failed operation on non-existent project -> 400
    missing_proj_op = AIOperation(
        id=gen_id("aio_"),
        request_id="req_fail_missing_prj",
        user_id=hanny.id,
        project_id="prj_non_existent_999",
        module_type="bmc",
        operation_type="generate",
        model_name="gemini-2.5-flash",
        duration_ms=500,
        status="failed",
        error_category="network_error",
        error_message="Project missing",
        is_retryable=True
    )
    db.add(missing_proj_op)
    db.commit()

    res_missing = client.post(f"/api/admin/ai-operations/{missing_proj_op.id}/retry", cookies=super_cookies, headers=super_headers)
    assert res_missing.status_code == 400
    assert "project no longer exists" in res_missing.json()["detail"].lower()

    # 4. Failed operation marked is_retryable=False on genuine project -> 400
    valid_proj = Project(
        id=gen_id("prj_"),
        user_id=hanny.id,
        name="Retry Test Project",
        stage="mvp"
    )
    db.add(valid_proj)
    db.commit()

    non_retry_op = AIOperation(
        id=gen_id("aio_"),
        request_id="req_fail_2",
        user_id=hanny.id,
        project_id=valid_proj.id,
        module_type="bmc",
        operation_type="generate",
        model_name="gemini-2.5-flash",
        duration_ms=500,
        status="failed",
        error_category="validation_error",
        error_message="Invalid schema",
        is_retryable=False
    )
    db.add(non_retry_op)
    db.commit()

    res3 = client.post(f"/api/admin/ai-operations/{non_retry_op.id}/retry", cookies=super_cookies, headers=super_headers)
    assert res3.status_code == 400
    assert "non-retryable" in res3.json()["detail"].lower()

# -------------------------------------------------------------
# 8. Legacy Manual Task Preservation During Reconciliation
# -------------------------------------------------------------
def test_legacy_manual_task_preservation_and_ai_task_identification(db):
    """
    Verify that manual/legacy tasks (is_ai_generated=False) survive reconciliation,
    and only is_ai_generated=True tasks are removed during AI sync/reconciliation.
    """
    hanny = db.query(User).filter(User.username == "HannyAdmin").first()

    # Create a project
    proj = Project(
        id=gen_id("prj_"),
        user_id=hanny.id,
        name="Task Preservation Project",
        stage="mvp"
    )
    db.add(proj)
    db.commit()

    # Create a legacy manual task (is_ai_generated=False)
    manual_task = RoadmapTask(
        id=gen_id("tsk_"),
        project_id=proj.id,
        task_code="TSK-MANUAL-01",
        title="Custom User Task That Must Survive",
        description="User explicitly added this task",
        phase="Phase 1",
        start_date="2026-01-01",
        end_date="2026-01-15",
        status="in_progress",
        is_ai_generated=False
    )
    # Create an AI-generated task (is_ai_generated=True)
    ai_task = RoadmapTask(
        id=gen_id("tsk_"),
        project_id=proj.id,
        task_code="TSK-AI-01",
        title="Old AI Generated Task",
        description="To be replaced by AI regeneration",
        phase="Phase 1",
        start_date="2026-01-01",
        end_date="2026-01-15",
        status="todo",
        is_ai_generated=True
    )
    db.add_all([manual_task, ai_task])
    db.commit()

    # Simulate AI roadmap regeneration/reconciliation:
    # Reconciliation deletes old AI-generated tasks while strictly preserving manual tasks
    deleted_ai_count = db.query(RoadmapTask).filter(
        RoadmapTask.project_id == proj.id,
        RoadmapTask.is_ai_generated == True
    ).delete(synchronize_session=False)
    db.commit()

    assert deleted_ai_count == 1

    # Verify manual task survived completely intact
    surviving_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == proj.id).all()
    assert len(surviving_tasks) == 1
    assert surviving_tasks[0].id == manual_task.id
    assert surviving_tasks[0].title == "Custom User Task That Must Survive"
    assert surviving_tasks[0].is_ai_generated is False

    # Clean up test project
    db.delete(surviving_tasks[0])
    db.delete(proj)
    db.commit()
