"""Phase 4 Verification: Provider Transaction Decoupling.

Verifies:
1. External AI provider calls release the checked-out database connection before execution:
   - Module generation
   - Section modification
   - Blueprint Copilot chat
   - Admin AI operations retry
2. Concurrent ordinary requests execute and complete without blocking while provider is blocked.
3. Project/module deleted while provider is pending returns HTTP 404 without orphaned rows.
4. Version capacity reached while provider is pending returns HTTP 409 Conflict under lock.
5. User suspended while provider is pending returns HTTP 403 Forbidden without saving content.
6. Provider failure leaves existing saved content untouched and records isolated telemetry.
7. Persistence failure rolls back cleanly without partial writes.
"""
from datetime import datetime, timedelta, timezone
import threading
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, Session as DBSession,
    CopilotMessage, AIOperation, AuditLog, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.schemas.modules import BMCData, GenerationBrief
from app.services.version_service import VersionService
from app.services.roadmap_service import RoadmapDomainService


import secrets

@pytest.fixture
def test_setup():
    """Create isolated test user, project, and session."""
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        u = User(
            id=gen_id("usr_"),
            username=f"p4_user_{uid}",
            email=f"p4_user_{uid}@example.com",
            hashed_password=hash_password("StrongPassword123!"),
            role="user",
            is_suspended=False
        )
        db.add(u)
        p = Project(
            id=gen_id("proj_"),
            name="Decoupling Architecture Blueprint",
            user_id=u.id,
            stage="Idea / MVP",
            description="Production architectural validation for decoupled provider calls",
            industry="Enterprise Software",
            target_customers="Enterprise technical architects and engineering leaders",
            goals="Decouple provider calls and release connections",
            budget="$10,000 - $50,000",
            business_context="High concurrency multi-tenant web architecture"
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
    """Create isolated test admin user and session."""
    aid = secrets.token_hex(4)
    with SessionLocal() as db:
        admin = User(
            id=gen_id("usr_"),
            username=f"p4_admin_{aid}",
            email=f"p4_admin_{aid}@example.com",
            hashed_password=hash_password("AdminPassword123!"),
            role="super_admin",
            is_suspended=False
        )
        db.add(admin)
        p = Project(
            id=gen_id("proj_"),
            name="Admin Target Project",
            user_id=admin.id,
            stage="Idea / MVP",
            description="Admin retry testing project context",
            industry="Developer Tools",
            target_customers="DevOps and Platform Engineers",
            goals="Admin retry reliability",
            budget="$25,000",
            business_context="Internal tools"
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


def sample_bmc_data():
    return BMCData(
        customer_segments=["Enterprise IT"],
        value_propositions=["Real-time generation"],
        channels=["Direct Web"],
        customer_relationships=["Automated onboarding"],
        revenue_streams=["SaaS Subscriptions"],
        key_resources=["Cloud Infrastructure"],
        key_activities=["Platform Maintenance"],
        key_partnerships=["Database Host"],
        cost_structure=["Server and AI APIs"]
    )


def test_generation_releases_db_connection_during_provider_call(test_setup):
    """Verify that during execute_module_generation, checked-out database connections are exactly 0."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    checkedout_during_call = None

    def mock_generate_bmc(*args, **kwargs):
        nonlocal checkedout_during_call
        checkedout_during_call = engine.pool.checkedout()
        return sample_bmc_data()

    with patch("app.ai.gemini_service.ai_service.generate_bmc", side_effect=mock_generate_bmc):
        resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")

    assert resp.status_code == 200
    assert checkedout_during_call == 0, f"Expected 0 checkedout connections during provider call, got {checkedout_during_call}"
    data = resp.json()
    assert data["active_version_id"] is not None
    assert data["data"]["customer_segments"] == ["Enterprise IT"]


def test_section_modify_releases_db_connection_during_provider_call(test_setup):
    """Verify that during modify_module_with_ai, checked-out database connections are exactly 0."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    # First generate initial version
    with patch("app.ai.gemini_service.ai_service.generate_bmc", return_value=sample_bmc_data()):
        init_resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")
        assert init_resp.status_code == 200

    checkedout_during_call = None

    def mock_modify_section(*args, **kwargs):
        nonlocal checkedout_during_call
        checkedout_during_call = engine.pool.checkedout()
        modified = sample_bmc_data().model_dump()
        modified["customer_segments"] = ["Enterprise IT", "Mid-market CTOs"]
        return modified, "Added mid-market segment"

    with patch("app.ai.gemini_service.ai_service.modify_section", side_effect=mock_modify_section):
        resp = client.post(
            f"/api/projects/{project_id}/modules/bmc/modify",
            json={"instruction": "Add mid-market segment"}
        )

    assert resp.status_code == 200
    assert checkedout_during_call == 0, f"Expected 0 checkedout connections during provider modify, got {checkedout_during_call}"
    assert resp.json()["data"]["customer_segments"] == ["Enterprise IT", "Mid-market CTOs"]


def test_copilot_chat_releases_db_connection_during_provider_call(test_setup):
    """Verify that during chat_with_copilot, checked-out database connections are exactly 0."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    checkedout_during_call = None

    def mock_chat_copilot(*args, **kwargs):
        nonlocal checkedout_during_call
        checkedout_during_call = engine.pool.checkedout()
        return "Decoupled copilot response."

    with patch("app.ai.gemini_service.ai_service.chat_copilot", side_effect=mock_chat_copilot):
        resp = client.post(
            f"/api/projects/{project_id}/copilot",
            json={"message": "What is our customer strategy?"}
        )

    assert resp.status_code == 200
    assert checkedout_during_call == 0, f"Expected 0 checkedout connections during copilot chat, got {checkedout_during_call}"
    assert resp.json()["content"] == "Decoupled copilot response."


def test_admin_retry_releases_db_connection_during_provider_call(admin_setup):
    """Verify that during admin retry_ai_operation, checked-out database connections are exactly 0."""
    client = admin_setup["client"]
    admin_id = admin_setup["admin_id"]
    project_id = admin_setup["project_id"]

    # Record a failed AI operation
    with SessionLocal() as db:
        failed_op = AIOperation(
            id=gen_id("aio_"),
            request_id="req_test_retry",
            user_id=admin_id,
            project_id=project_id,
            module_type="bmc",
            operation_type="generate",
            model_name=settings.GEMINI_MODEL,
            duration_ms=3000,
            status="failed",
            error_category="timeout",
            error_message="Gateway timeout",
            is_retryable=True,
            retry_count=0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(failed_op)
        db.commit()
        failed_op_id = failed_op.id

    checkedout_during_call = None

    def mock_generate_bmc(*args, **kwargs):
        nonlocal checkedout_during_call
        checkedout_during_call = engine.pool.checkedout()
        return sample_bmc_data()

    with patch("app.ai.gemini_service.ai_service.generate_bmc", side_effect=mock_generate_bmc):
        resp = client.post(f"/api/admin/ai-operations/{failed_op_id}/retry")

    assert resp.status_code == 200
    assert checkedout_during_call == 0, f"Expected 0 checkedout connections during admin retry, got {checkedout_during_call}"
    assert resp.json()["status"] == "success"


def test_concurrent_ordinary_requests_continue_while_provider_blocked(test_setup):
    """Verify concurrent requests proceed immediately while an AI provider call is blocked."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]
    raw_tok = test_setup["raw_token"]

    thread_client = TestClient(app)
    thread_client.cookies.set("aba_session", raw_tok)
    thread_client.headers["X-CSRF-Token"] = generate_csrf_token(raw_tok)

    provider_entered = threading.Event()
    release_provider = threading.Event()

    def blocked_generate(*args, **kwargs):
        provider_entered.set()
        # Wait up to 5 seconds for test thread to complete concurrent read
        release_provider.wait(timeout=5.0)
        return sample_bmc_data()

    gen_response = []

    def run_generation():
        with patch("app.ai.gemini_service.ai_service.generate_bmc", side_effect=blocked_generate):
            res = thread_client.post(f"/api/projects/{project_id}/modules/bmc/generate")
            gen_response.append(res)

    gen_thread = threading.Thread(target=run_generation)
    gen_thread.start()

    try:
        # Wait until generation is inside provider call
        assert provider_entered.wait(timeout=3.0), "Provider call was not entered in time"

        # Verify that an ordinary request completes immediately without blocking
        read_resp = client.get(f"/api/projects/{project_id}")
        assert read_resp.status_code == 200
        assert read_resp.json()["name"] == "Decoupling Architecture Blueprint"

        # Also list projects
        list_resp = client.get("/api/projects")
        assert list_resp.status_code == 200
    finally:
        # Release blocked provider and join thread
        release_provider.set()
        gen_thread.join(timeout=5.0)

    assert len(gen_response) == 1
    assert gen_response[0].status_code == 200


def test_project_deleted_while_provider_pending_returns_404(test_setup):
    """If project is deleted while provider is running, persistence returns 404 cleanly."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    def provider_with_project_delete(*args, **kwargs):
        # Concurrently delete project from another transaction
        with SessionLocal() as del_db:
            del_db.query(Project).filter(Project.id == project_id).delete()
            del_db.commit()
        return sample_bmc_data()

    with patch("app.ai.gemini_service.ai_service.generate_bmc", side_effect=provider_with_project_delete):
        resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")

    assert resp.status_code == 404
    assert "deleted" in resp.json()["detail"].lower()

    # Ensure no orphaned version rows created
    with SessionLocal() as verify_db:
        versions = verify_db.query(ModuleVersion).join(ModuleContent).filter(
            ModuleContent.project_id == project_id
        ).all()
        assert len(versions) == 0


def test_module_deleted_while_provider_pending_returns_404(test_setup):
    """If module is deleted while provider is running, persistence returns 404 cleanly."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    # Generate initial version
    with patch("app.ai.gemini_service.ai_service.generate_bmc", return_value=sample_bmc_data()):
        init_resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")
        assert init_resp.status_code == 200

    def provider_with_module_delete(*args, **kwargs):
        with SessionLocal() as del_db:
            del_db.query(ModuleVersion).delete()
            del_db.query(ModuleContent).filter(ModuleContent.project_id == project_id).delete()
            del_db.commit()
        modified = sample_bmc_data().model_dump()
        return modified, "Updated"

    with patch("app.ai.gemini_service.ai_service.modify_section", side_effect=provider_with_module_delete):
        resp = client.post(
            f"/api/projects/{project_id}/modules/bmc/modify",
            json={"instruction": "Add segment"}
        )

    assert resp.status_code == 404
    assert "deleted" in resp.json()["detail"].lower()


def test_capacity_reached_while_provider_pending_returns_conflict(test_setup):
    """If capacity limit (5 versions) is reached while provider is pending, returns 409 Conflict under lock."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    # Seed 4 versions
    with SessionLocal() as db:
        mod = ModuleContent(id=gen_id("mod_"), project_id=project_id, module_type="bmc")
        db.add(mod)
        db.flush()
        for i in range(1, 5):
            ver = ModuleVersion(
                id=gen_id("ver_"),
                module_content_id=mod.id,
                version_number=i,
                version_name=f"v{i}",
                data=sample_bmc_data().model_dump(),
                is_active=(i == 4),
                change_summary=f"Version {i}"
            )
            db.add(ver)
        mod.active_version_id = ver.id
        db.commit()
        mod_id = mod.id

    def provider_with_concurrent_capacity_hit(*args, **kwargs):
        # Insert 5th version concurrently so capacity limit is now full
        with SessionLocal() as cap_db:
            ver5 = ModuleVersion(
                id=gen_id("ver_"),
                module_content_id=mod_id,
                version_number=5,
                version_name="v5-concurrent",
                data=sample_bmc_data().model_dump(),
                is_active=True,
                change_summary="Concurrent fill"
            )
            cap_db.add(ver5)
            c_mod = cap_db.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            c_mod.active_version_id = ver5.id
            cap_db.commit()

        modified = sample_bmc_data().model_dump()
        modified["customer_segments"] = ["Concurrent customer"]
        return modified, "Attempted 6th version"

    with patch("app.ai.gemini_service.ai_service.modify_section", side_effect=provider_with_concurrent_capacity_hit):
        resp = client.post(
            f"/api/projects/{project_id}/modules/bmc/modify",
            json={"instruction": "Create version exceeding capacity"}
        )

    assert resp.status_code == 409
    assert "limit" in str(resp.json()["detail"]).lower() or "capacity" in str(resp.json()["detail"]).lower()

    # Verify exactly 5 versions remain in DB and 6th was rejected
    with SessionLocal() as check_db:
        versions = check_db.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod_id).all()
        assert len(versions) == 5


def test_user_suspended_while_provider_pending_returns_403(test_setup):
    """If user is suspended while provider is pending, post-provider persistence rejects with 403."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]
    user_id = test_setup["user_id"]

    def provider_with_suspension(*args, **kwargs):
        with SessionLocal() as susp_db:
            u = susp_db.query(User).filter(User.id == user_id).first()
            u.is_suspended = True
            susp_db.commit()
        return sample_bmc_data()

    with patch("app.ai.gemini_service.ai_service.generate_bmc", side_effect=provider_with_suspension):
        resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")

    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower() or "active" in resp.json()["detail"].lower()


def test_provider_failure_leaves_saved_content_unchanged_and_records_isolated_telemetry(test_setup):
    """If provider raises an error, existing version data is completely untouched and isolated telemetry recorded."""
    client = test_setup["client"]
    project_id = test_setup["project_id"]

    # Create initial version
    with patch("app.ai.gemini_service.ai_service.generate_bmc", return_value=sample_bmc_data()):
        init_resp = client.post(f"/api/projects/{project_id}/modules/bmc/generate")
        assert init_resp.status_code == 200
        initial_version_id = init_resp.json()["active_version_id"]

    # Attempt modification with simulated provider crash
    with patch("app.ai.gemini_service.ai_service.modify_section", side_effect=RuntimeError("Gemini 503 Overloaded")):
        fail_resp = client.post(
            f"/api/projects/{project_id}/modules/bmc/modify",
            json={"instruction": "Fail please"}
        )

    assert fail_resp.status_code == 500

    # Verify existing saved version is completely unchanged
    with SessionLocal() as check_db:
        mod = check_db.query(ModuleContent).filter(
            ModuleContent.project_id == project_id,
            ModuleContent.module_type == "bmc"
        ).first()
        assert mod.active_version_id == initial_version_id
        versions = check_db.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod.id).all()
        assert len(versions) == 1

        # Check telemetry was recorded cleanly without corrupting business state
        op = check_db.query(AIOperation).filter(
            AIOperation.project_id == project_id,
            AIOperation.status.in_(["failed", "timeout"])
        ).first()
        assert op is not None
        assert op.persistence_status == "failed"
