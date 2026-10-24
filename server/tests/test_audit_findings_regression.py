import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    CopilotMessage, SystemSetting, SecurityEvent, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_csrf_token
from app.core.admin_provisioning import provision_initial_admin
from app.services.version_service import VersionService
from app.services.system_setting_service import get_setting_bool, set_setting

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

def _create_admin_with_role(db, role: str) -> tuple[User, str, str]:
    uid = uuid.uuid4().hex[:8]
    username = f"admin_{role}_{uid}"
    password = "StrongAdminPass123!"
    admin = User(
        id=gen_id("adm_"),
        username=username,
        email=f"{username}@test.com",
        hashed_password=hash_password(password),
        role=role,
        is_suspended=False
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin, username, password

def _login_admin(client, username, password):
    resp = client.post("/api/admin/auth/login", json={
        "username": username,
        "password": password
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


# =====================================================================
# F-01: Backend startup blocker regression check
# =====================================================================
def test_f01_backend_startup_imports():
    """Verify app.main imports cleanly without NameError in auth schemas."""
    import app.main
    assert app.main.app is not None
    from app.schemas.auth import UserProfileUpdateRequest
    fields = UserProfileUpdateRequest.model_fields
    assert "username" in fields
    assert "email" in fields


# =====================================================================
# F-02: Admin bootstrap safety, credential enforcement, and idempotency
# =====================================================================
def test_f02_admin_bootstrap_disabled_by_default(db, monkeypatch):
    """When ADMIN_BOOTSTRAP_ENABLED is False, provisioning does not run."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_ENABLED", False)
    result = provision_initial_admin(db)
    assert result is False

def test_f02_admin_bootstrap_missing_or_weak_credentials(db, monkeypatch):
    """When enabled but credentials missing or weak, fails safely without creating admin."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_ENABLED", True)
    monkeypatch.setattr(settings, "INITIAL_ADMIN_USERNAME", "")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "")
    assert provision_initial_admin(db) is False

    # Weak password (<12 chars or missing symbols)
    monkeypatch.setattr(settings, "INITIAL_ADMIN_USERNAME", "SecAdmin")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "weakpass")
    assert provision_initial_admin(db) is False

def test_f02_admin_bootstrap_idempotent(db, monkeypatch):
    """Restarting must not reset an existing admin's password or re-create an account."""
    admin = db.query(User).filter(User.role == "super_admin").first()
    if not admin:
        monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_ENABLED", True)
        monkeypatch.setattr(settings, "INITIAL_ADMIN_USERNAME", "SecAdmin")
        monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "InitialStrongPass123!@#")
        assert provision_initial_admin(db) is True
        admin = db.query(User).filter(User.role == "super_admin").first()
    assert admin is not None
    original_hash = admin.hashed_password

    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_ENABLED", True)
    monkeypatch.setattr(settings, "INITIAL_ADMIN_USERNAME", admin.username)
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "NewDifferentPass123!@#")

    # Second / subsequent startup returns False and leaves existing hash intact
    rerun = provision_initial_admin(db)
    assert rerun is False
    db.refresh(admin)
    assert admin.hashed_password == original_hash


# =====================================================================
# F-03: Server-side role permission matrix enforcement
# =====================================================================
def test_f03_role_permission_matrix(db):
    """
    Test allowed and denied access for representative actions across all roles.
    - super_admin: unrestricted
    - operations_admin: system diagnostics & repairs allowed; user management denied
    - security_admin: view audit/security, revoke sessions allowed; system repair denied
    - support_admin: user read/modify allowed; system repair & ai retry denied
    - auditor: audit logs & analytics allowed; destructive operations denied
    - ordinary user / unauthenticated: all admin endpoints denied
    """
    roles = ["super_admin", "operations_admin", "security_admin", "support_admin", "auditor"]
    admins = {}
    for r in roles:
        cli = TestClient(app)
        adm, uname, pwd = _create_admin_with_role(db, r)
        csrf = _login_admin(cli, uname, pwd)
        admins[r] = (cli, csrf)

    # 1. System repair: allowed for super_admin, operations_admin; denied for others
    # super_admin: allowed
    cli_super, csrf_super = admins["super_admin"]
    r_super = cli_super.post(
        "/api/admin/integrity/repair",
        json={"action": "clean_expired_sessions", "confirmation": True},
        headers={"X-CSRF-Token": csrf_super}
    )
    assert r_super.status_code in (200, 400), f"Expected super_admin allowed, got {r_super.status_code}"

    # security_admin: denied (403)
    cli_sec, csrf_sec = admins["security_admin"]
    r_sec = cli_sec.post(
        "/api/admin/integrity/repair",
        json={"action": "clean_expired_sessions", "confirmation": True},
        headers={"X-CSRF-Token": csrf_sec}
    )
    assert r_sec.status_code == 403

    # auditor: denied (403)
    cli_aud, csrf_aud = admins["auditor"]
    r_aud = cli_aud.post(
        "/api/admin/integrity/repair",
        json={"action": "clean_expired_sessions", "confirmation": True},
        headers={"X-CSRF-Token": csrf_aud}
    )
    assert r_aud.status_code == 403

    # 2. Audit logs: allowed for auditor and security_admin; denied for support_admin
    r_aud_log = cli_aud.get("/api/admin/audit-logs")
    assert r_aud_log.status_code == 200

    cli_sup, csrf_sup = admins["support_admin"]
    r_sup_log = cli_sup.get("/api/admin/audit-logs")
    assert r_sup_log.status_code == 403

    # 3. Unauthenticated requests are rejected with 401
    unauth_client = TestClient(app)
    r_unauth = unauth_client.get("/api/admin/dashboard/stats")
    assert r_unauth.status_code == 401


# =====================================================================
# F-04: Admin dashboard empty-data failure handled gracefully
# =====================================================================
def test_f04_admin_dashboard_empty_data_handled(db):
    """Admin dashboard handles zero AI operations in a selected date range without exception."""
    cli = TestClient(app)
    adm, uname, pwd = _create_admin_with_role(db, "super_admin")
    _login_admin(cli, uname, pwd)

    # Date range in future containing zero operations
    resp = cli.get("/api/admin/dashboard/stats?range=custom&custom_start=2099-01-01T00:00:00Z&custom_end=2099-01-02T00:00:00Z")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "ai" in data
    assert data["ai"]["total_operations"] == 0
    assert data["ai"]["failure_rate"] == 0.0
    assert data["ai"]["success_rate"] == 0.0


# =====================================================================
# F-05: Admin settings affect runtime behavior
# =====================================================================
def test_f05_public_registration_disabled_rejects_new_users(client, db):
    """When public_registration_enabled is False, registration returns 403."""
    set_setting(db, "public_registration_enabled", "false", value_type="boolean")
    uid = uuid.uuid4().hex[:8]
    resp = client.post("/api/auth/register", json={
        "username": f"blocked_{uid}",
        "email": f"blocked_{uid}@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    })
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()

    # Re-enable
    set_setting(db, "public_registration_enabled", "true", value_type="boolean")

def test_f05_maintenance_mode_gates_user_api_while_preserving_admin_and_health(client, db):
    """When maintenance_mode is True, /api/* returns 503, but /health and /api/admin/* work."""
    set_setting(db, "maintenance_mode", "true", value_type="boolean")
    try:
        # User route blocked
        resp_user = client.post("/api/auth/login", json={"email_or_username": "foo", "password": "bar"})
        assert resp_user.status_code == 503
        assert "maintenance" in resp_user.json()["detail"].lower()

        # Health check available
        resp_health = client.get("/health")
        assert resp_health.status_code == 200

        # Liveness check available
        resp_live = client.get("/health/live")
        assert resp_live.status_code == 200

        # Admin login available
        resp_admin = client.post("/api/admin/auth/login", json={"username": "foo", "password": "bar"})
        assert resp_admin.status_code == 401  # Not 503!
    finally:
        set_setting(db, "maintenance_mode", "false", value_type="boolean")


# =====================================================================
# F-06: Fork New Project preserves all project work
# =====================================================================
def test_f06_fork_project_deep_copies_work(client, db):
    """Forking a project clones module contents, versions, roadmap tasks, and copilot messages."""
    uid = uuid.uuid4().hex[:8]
    pwd = "UserPass123!"
    user = User(id=gen_id("usr_"), username=f"forker_{uid}", email=f"fork_{uid}@test.com", hashed_password=hash_password(pwd), role="user")
    db.add(user)
    db.commit()

    # User login
    cli = TestClient(app)
    l_resp = cli.post("/api/auth/login", json={"email_or_username": user.username, "password": pwd})
    csrf = l_resp.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    # Create source project
    src = Project(user_id=user.id, name="Original Venture", stage="Idea / MVP", active_module="bmc")
    db.add(src)
    db.commit()

    # Add module & version
    mod = ModuleContent(project_id=src.id, module_type="bmc")
    db.add(mod)
    db.flush()
    ver = ModuleVersion(module_content_id=mod.id, version_number=1, version_name="BMC V1", data={"tagline": "Original"}, is_active=True)
    db.add(ver)
    db.flush()
    mod.active_version_id = ver.id

    # Add task
    task = RoadmapTask(project_id=src.id, task_code="TSK-01", phase="Research", title="Market Study", start_date="2026-01-01", end_date="2026-01-10", status="In Progress", assigned_to="Alice", assigned_role="Market Analyst", department="Research", steps=["Interview buyers"], is_overloaded=True, is_ai_generated=True)
    db.add(task)

    # Add copilot message
    msg = CopilotMessage(project_id=src.id, role="user", content="How do I monetize?")
    db.add(msg)
    db.commit()

    # Fork project via PUT with create_copy=True
    fork_resp = cli.put(f"/api/projects/{src.id}", json={
        "name": "Forked Venture",
        "create_copy": True
    }, headers=headers)
    assert fork_resp.status_code == 200
    fork_data = fork_resp.json()
    fork_id = fork_data["id"]
    assert fork_id != src.id
    assert fork_data["name"] == "Forked Venture"

    # Verify source project is unchanged
    db.refresh(src)
    assert src.name == "Original Venture"

    # Verify forked project has copied modules, versions, tasks, and messages
    forked_mods = db.query(ModuleContent).filter(ModuleContent.project_id == fork_id).all()
    assert len(forked_mods) == 1
    assert forked_mods[0].module_type == "bmc"
    assert forked_mods[0].active_version_id is not None
    assert forked_mods[0].active_version_id != ver.id  # New ID!

    forked_vers = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == forked_mods[0].id).all()
    assert len(forked_vers) == 1
    assert forked_vers[0].data == {"tagline": "Original"}

    forked_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == fork_id).all()
    assert len(forked_tasks) == 1
    assert forked_tasks[0].task_code == "TSK-01"
    assert forked_tasks[0].id != task.id
    assert forked_tasks[0].assigned_to == "Alice"
    assert forked_tasks[0].assigned_role == "Market Analyst"
    assert forked_tasks[0].department == "Research"
    assert forked_tasks[0].steps == ["Interview buyers"]
    assert forked_tasks[0].is_overloaded is True

    forked_msgs = db.query(CopilotMessage).filter(CopilotMessage.project_id == fork_id).all()
    assert len(forked_msgs) == 1
    assert forked_msgs[0].content == "How do I monetize?"


# =====================================================================
# F-08 & F-14: Roadmap version restore & task reconciliation
# =====================================================================
def test_f08_roadmap_restore_reconciles_tasks(client, db):
    """Restoring a roadmap version syncs tasks and preserves manual tasks."""
    uid = uuid.uuid4().hex[:8]
    pwd = "UserPass123!"
    user = User(id=gen_id("usr_"), username=f"road_{uid}", email=f"road_{uid}@test.com", hashed_password=hash_password(pwd), role="user")
    db.add(user)
    db.commit()

    cli = TestClient(app)
    l_resp = cli.post("/api/auth/login", json={"email_or_username": user.username, "password": pwd})
    csrf = l_resp.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    proj = Project(user_id=user.id, name="Roadmap Test")
    db.add(proj)
    db.commit()

    mod = ModuleContent(project_id=proj.id, module_type="execution_roadmap")
    db.add(mod)
    db.flush()

    v1_data = {
        "phases": [{"name": "Phase 1"}],
        "tasks": [
            {"task_code": "TSK-01", "phase": "Phase 1", "title": "Version 1 Task", "start_date": "2026-01-01", "end_date": "2026-01-05", "status": "In Progress"}
        ]
    }
    v2_data = {
        "phases": [{"name": "Phase 2"}],
        "tasks": [
            {"task_code": "TSK-02", "phase": "Phase 2", "title": "Version 2 Task", "start_date": "2026-02-01", "end_date": "2026-02-05", "status": "Pending"}
        ]
    }

    v1 = VersionService.save_new_version(db, mod, v1_data, "V1")
    v2 = VersionService.save_new_version(db, mod, v2_data, "V2")

    # Add a user-created manual task
    manual_task = RoadmapTask(project_id=proj.id, task_code="USER-01", phase="Custom", title="Manual Task", start_date="2026-01-01", end_date="2026-01-02", status="In Progress", is_ai_generated=False)
    db.add(manual_task)
    db.commit()

    # Restore V1
    restore_resp = cli.post(f"/api/projects/{proj.id}/modules/execution_roadmap/versions/{v1.id}/restore", headers=headers)
    assert restore_resp.status_code == 200

    # Tasks in DB should now have TSK-01 (from V1) and USER-01 (preserved manual task). TSK-02 (AI from V2) should be deleted!
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == proj.id).all()
    codes = {t.task_code for t in tasks}
    assert "TSK-01" in codes
    assert "USER-01" in codes
    assert "TSK-02" not in codes


# =====================================================================
# F-09: Module payload validation before persistence
# =====================================================================
def test_f09_module_data_validation(client, db):
    """Invalid module payload in conflict resolution is rejected with 422."""
    uid = uuid.uuid4().hex[:8]
    pwd = "UserPass123!"
    user = User(id=gen_id("usr_"), username=f"val_{uid}", email=f"val_{uid}@test.com", hashed_password=hash_password(pwd), role="user")
    db.add(user)
    db.commit()

    cli = TestClient(app)
    l_resp = cli.post("/api/auth/login", json={"email_or_username": user.username, "password": pwd})
    csrf = l_resp.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    proj = Project(user_id=user.id, name="Validation Test")
    db.add(proj)
    db.commit()

    mod = ModuleContent(project_id=proj.id, module_type="bmc")
    db.add(mod)
    db.flush()
    ver = VersionService.save_new_version(db, mod, {"customer_segments": ["A"], "value_propositions": ["B"], "channels": ["C"], "customer_relationships": ["D"], "revenue_streams": ["E"], "key_resources": ["F"], "key_activities": ["G"], "key_partnerships": ["H"], "cost_structure": ["I"]}, "V1")

    # Send invalid BMC (empty customer segments)
    invalid_resp = cli.post(f"/api/projects/{proj.id}/modules/bmc/resolve-conflict", json={
        "replace_version_id": ver.id,
        "new_data": {"customer_segments": []}  # Invalid: requires min_length 1
    }, headers=headers)
    assert invalid_resp.status_code == 422


# =====================================================================
# F-10: Module adoption side-effect free reads
# =====================================================================
def test_f10_reading_ungenerated_module_is_side_effect_free(client, db):
    """Reading an ungenerated module does not create a database row or affect analytics."""
    uid = uuid.uuid4().hex[:8]
    pwd = "UserPass123!"
    user = User(id=gen_id("usr_"), username=f"adopt_{uid}", email=f"adopt_{uid}@test.com", hashed_password=hash_password(pwd), role="user")
    db.add(user)
    db.commit()

    cli = TestClient(app)
    l_resp = cli.post("/api/auth/login", json={"email_or_username": user.username, "password": pwd})
    csrf = l_resp.json()["csrf_token"]

    proj = Project(user_id=user.id, name="Side Effect Free Test")
    db.add(proj)
    db.commit()

    # GET module before any generation
    resp = cli.get(f"/api/projects/{proj.id}/modules/tech_stack")
    assert resp.status_code == 200
    assert resp.json()["data"] is None

    # Assert no ModuleContent record was inserted
    row = db.query(ModuleContent).filter(ModuleContent.project_id == proj.id, ModuleContent.module_type == "tech_stack").first()
    assert row is None


# =====================================================================
# F-12: Health check database readiness detection
# =====================================================================
def test_f12_health_checks(client):
    """Readiness endpoint returns 200 when DB is up and checks SELECT 1; liveness returns 200."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"

    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"


# =====================================================================
# F-13: Ordinary user login rate limiting
# =====================================================================
def test_f13_user_login_rate_limiting(client, db, monkeypatch):
    """Exceeding failed login limit triggers 429 Too Many Requests."""
    from app.core.config import settings
    from app.core.auth_limiter import record_login_failure
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["testclient", "127.0.0.1"])
    ip = "192.0.2.100"
    for i in range(5):
        record_login_failure(ip, "nonexistent", is_admin=False)

    # Next attempt from same IP should get 429
    resp = client.post("/api/auth/login", json={
        "email_or_username": "nonexistent",
        "password": "WrongPassword123!"
    }, headers={"X-Forwarded-For": ip})
    assert resp.status_code == 429
    assert "Too many failed login attempts" in resp.json()["detail"]
