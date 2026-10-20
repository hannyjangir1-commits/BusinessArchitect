import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    AIOperation, AnalyticsEvent, AuditLog, gen_id
)
from app.db.session import SessionLocal
from app.core.admin_provisioning import provision_initial_admin
from app.core.telemetry import record_ai_operation, record_audit_log

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def admin_client(db):
    from app.core.admin_provisioning import seed_development_admin
    seed_development_admin(db)
    client = TestClient(app)
    resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert resp.status_code == 200
    csrf_token = resp.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf_token
    return client

def test_dashboard_stats_and_trends(admin_client):
    """Verify admin dashboard returns real metrics and time-series trends."""
    resp = admin_client.get("/api/admin/dashboard/stats?range=30d")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "projects" in data
    assert "ai" in data
    assert "infrastructure" in data
    assert data["infrastructure"]["database_status"] == "connected"
    assert data["infrastructure"]["backend_status"] == "healthy"

    # Trends
    trend_resp = admin_client.get("/api/admin/dashboard/trends?range=30d")
    assert trend_resp.status_code == 200
    trend_data = trend_resp.json()
    assert "points" in trend_data
    assert len(trend_data["points"]) > 0

def test_user_management_lifecycle(admin_client, db):
    """Verify user listing, details, suspension, reactivation, and session revocation."""
    # Ensure test user exists
    test_user = db.query(User).filter(User.username == "mgmt_test_user").first()
    if not test_user:
        test_user = User(
            id=gen_id("usr_"),
            username="mgmt_test_user",
            email="mgmt_test@example.com",
            hashed_password=hash_password("MgmtUserPass123"),
            role="user",
            terms_accepted=True
        )
        db.add(test_user)
        db.commit()

    # List users
    list_resp = admin_client.get("/api/admin/users?search=mgmt_test_user")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(u["username"] == "mgmt_test_user" for u in items)

    # User detail
    detail_resp = admin_client.get(f"/api/admin/users/{test_user.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["user"]["username"] == "mgmt_test_user"

    # Suspend user
    suspend_resp = admin_client.post(
        f"/api/admin/users/{test_user.id}/suspend",
        json={"reason": "Security verification required"}
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["is_suspended"] is True

    # Reactivate user
    reactivate_resp = admin_client.post(f"/api/admin/users/{test_user.id}/reactivate")
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_suspended"] is False

    # Revoke sessions
    revoke_resp = admin_client.post(f"/api/admin/users/{test_user.id}/revoke-sessions")
    assert revoke_resp.status_code == 200

def test_project_management_and_transfer(admin_client, db):
    """Verify project listing, detail view, and safe ownership transfer."""
    user1 = db.query(User).filter(User.username == "mgmt_test_user").first()
    user2 = db.query(User).filter(User.username == "HannyAdmin").first()

    # Create test project
    proj = Project(
        id=gen_id("prj_"),
        user_id=user1.id,
        name="Test Transfer Enterprise Project",
        stage="Idea / MVP",
        industry="SaaS"
    )
    db.add(proj)
    db.commit()

    # List projects
    list_resp = admin_client.get(f"/api/admin/projects?search={proj.name}")
    assert list_resp.status_code == 200
    assert any(p["name"] == proj.name for p in list_resp.json()["items"])

    # Project detail
    detail_resp = admin_client.get(f"/api/admin/projects/{proj.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["project"]["name"] == proj.name

    # Transfer ownership to user2
    transfer_resp = admin_client.post(
        f"/api/admin/projects/{proj.id}/transfer",
        json={"new_owner_username": user2.username}
    )
    assert transfer_resp.status_code == 200
    assert transfer_resp.json()["new_owner_username"] == user2.username

    # Delete project
    del_resp = admin_client.delete(f"/api/admin/projects/{proj.id}?confirm_project_name={proj.name}")
    assert del_resp.status_code == 200

def test_ai_operations_explorer_and_retry(admin_client, db):
    """Verify AI operations listing, quality stats, and controlled retry."""
    user = db.query(User).filter(User.username == "HannyAdmin").first()

    # Create genuine project context for failed operation
    proj = Project(
        id=gen_id("proj_"),
        name="Admin Recovery Blueprint",
        user_id=user.id,
        stage="Idea / MVP",
        industry="Enterprise Software",
        description="Testing real admin recovery workflow with project context",
        target_customers="Enterprise IT Managers"
    )
    db.add(proj)
    db.commit()

    # Insert simulated failed operation associated with genuine project
    failed_op = record_ai_operation(
        db,
        module_type="bmc",
        operation_type="generate",
        model_name=settings.GEMINI_MODEL,
        duration_ms=4500,
        status="failed",
        user_id=user.id,
        project_id=proj.id,
        error_category="timeout",
        error_message="HTTP connection timed out after 30s",
        structured_validation_passed=False,
        persistence_status="failed",
        is_retryable=True
    )
    assert failed_op is not None

    # List AI operations
    list_resp = admin_client.get("/api/admin/ai-operations?status=failed")
    assert list_resp.status_code == 200
    assert any(o["id"] == failed_op.id for o in list_resp.json()["items"])

    # Stats
    stats_resp = admin_client.get("/api/admin/ai-operations/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["total_operations"] > 0

    # Retry failed operation
    from unittest.mock import patch
    from app.schemas.modules import BMCData
    retry_canvas = BMCData(
        customer_segments=["Enterprise IT teams"], value_propositions=["Reliable planning"],
        channels=["Direct sales"], customer_relationships=["Dedicated onboarding"],
        revenue_streams=["Subscription"], key_resources=["Product team"],
        key_activities=["Build and support"], key_partnerships=["Cloud provider"],
        cost_structure=["Engineering and hosting"],
    )
    # Keep the retry test deterministic and offline: it verifies the admin retry,
    # validation, version write, and idempotency path without contacting Gemini.
    with patch("app.ai.gemini_service.ai_service.generate_bmc", return_value=retry_canvas):
        retry_resp = admin_client.post(f"/api/admin/ai-operations/{failed_op.id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "success"

    # Verify idempotency (cannot retry second time)
    retry_again = admin_client.post(f"/api/admin/ai-operations/{failed_op.id}/retry")
    assert retry_again.status_code == 400

def test_data_integrity_scan_and_repair(admin_client, db):
    """Verify data integrity scan finds issues and transactional repair resolves them."""
    scan_resp = admin_client.get("/api/admin/integrity/scan")
    assert scan_resp.status_code == 200
    assert "findings" in scan_resp.json()

    # Test clean expired sessions repair
    repair_resp = admin_client.post(
        "/api/admin/integrity/repair",
        json={"action": "clean_expired_sessions", "confirmation": True}
    )
    assert repair_resp.status_code == 200
    assert "repaired_count" in repair_resp.json()

def test_system_settings_configuration(admin_client):
    """Verify configuration center allows safe runtime setting updates with validation."""
    get_resp = admin_client.get("/api/admin/configuration")
    assert get_resp.status_code == 200
    assert "runtime_settings" in get_resp.json()
    assert "environment_status" in get_resp.json()

    # Update valid setting
    update_resp = admin_client.post(
        "/api/admin/configuration",
        json={"settings": {"ai_timeout_seconds": "50", "alert_ai_failure_pct": "25"}}
    )
    assert update_resp.status_code == 200
    assert "ai_timeout_seconds" in update_resp.json()["updated_keys"]

    # Reject invalid setting
    invalid_resp = admin_client.post(
        "/api/admin/configuration",
        json={"settings": {"ai_timeout_seconds": "9999"}}
    )
    assert invalid_resp.status_code == 400

def test_maintenance_mode_controls(admin_client):
    """Verify maintenance mode toggle and audit trail."""
    # Enable maintenance
    enable_resp = admin_client.post(
        "/api/admin/maintenance/toggle",
        json={"enabled": True, "reason": "Database optimization maintenance"}
    )
    assert enable_resp.status_code == 200
    assert enable_resp.json()["maintenance_mode_active"] is True

    # Check status
    status_resp = admin_client.get("/api/admin/maintenance/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["maintenance_mode_active"] is True

    # Disable maintenance
    disable_resp = admin_client.post(
        "/api/admin/maintenance/toggle",
        json={"enabled": False, "reason": "Maintenance complete"}
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["maintenance_mode_active"] is False

def test_csv_export_formula_injection_defense(admin_client, db):
    """Verify CSV export sanitizes spreadsheet formula injection characters (=, +, -, @)."""
    # Create a user with potentially malicious formula name
    malicious_user = db.query(User).filter(User.username == "=cmd|' /C calc'!A0").first()
    if not malicious_user:
        malicious_user = User(
            id=gen_id("usr_"),
            username="=cmd|' /C calc'!A0",
            email="malicious@example.com",
            hashed_password=hash_password("SafePassword123"),
            terms_accepted=True
        )
        db.add(malicious_user)
        db.commit()

    resp = admin_client.get("/api/admin/reports/export-csv?report_type=users")
    assert resp.status_code == 200
    content = resp.text
    # Cell starting with '=' must be prepended with single quote "'"
    assert "'=cmd|' /C calc'!A0" in content

    # Clean up test user
    db.delete(malicious_user)
    db.commit()

def test_summary_pdf_generation(admin_client):
    """Verify executive summary PDF generates with valid PDF headers."""
    resp = admin_client.get("/api/admin/reports/summary-pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
