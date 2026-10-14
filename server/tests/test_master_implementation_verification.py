import uuid
# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion,
    AIOperation, gen_id
)
from app.db.session import SessionLocal
from app.services.readiness_service import ReadinessValidationService
from app.services.version_service import VersionService

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_user(db):
    uid = uuid.uuid4().hex[:8]
    user = User(
        id=gen_id("usr_"),
        username=f"verif_user_{uid}",
        email=f"verif_{uid}@test.com",
        hashed_password=hash_password("ValidPassword123!"),
        role="user",
        is_suspended=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = TestClient(app)
    resp = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "ValidPassword123!"
    })
    csrf_token = resp.json()["csrf_token"]
    session_cookie = client.cookies.get(settings.COOKIE_NAME)

    return {
        "user": user,
        "client": client,
        "csrf_token": csrf_token,
        "session_cookie": session_cookie
    }

@pytest.fixture
def test_admin(db):
    uid = uuid.uuid4().hex[:8]
    admin = User(
        id=gen_id("usr_"),
        username=f"verif_admin_{uid}",
        email=f"verif_admin_{uid}@test.com",
        hashed_password=hash_password("AdminPass123!"),
        role="super_admin",
        is_suspended=False
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    client = TestClient(app)
    resp = client.post("/api/admin/auth/login", json={
        "username": admin.username,
        "password": "AdminPass123!"
    })
    csrf_token = resp.json()["csrf_token"]
    session_cookie = client.cookies.get(settings.COOKIE_NAME)

    return {
        "admin": admin,
        "client": client,
        "csrf_token": csrf_token,
        "session_cookie": session_cookie
    }


# ==============================================================================
# PHASE 2 TESTS: Centralized Readiness Validation
# ==============================================================================

def test_readiness_validation_unit():
    """Unit tests for ReadinessValidationService covering gibberish, empty, and module rules."""
    validator = ReadinessValidationService()

    # 1. Empty description
    p_empty = Project(name="Project X", description="   ", target_customers="Developers", industry="Tech", stage="MVP")
    is_ready, missing, errs = validator.validate_project_readiness(p_empty, "bmc")
    assert not is_ready
    assert "description" in missing

    # 2. Random gibberish / consonant keyboard smash
    p_gibberish = Project(name="Project X", description="asdfghjkl zxcvbnm qwertyuiop", target_customers="Devs", industry="Tech", stage="MVP")
    is_ready, missing, errs = validator.validate_project_readiness(p_gibberish, "bmc")
    assert not is_ready
    assert any("placeholder" in r.lower() or "random" in r.lower() or "semantic" in r.lower() for r in errs)

    # 3. Repeated single character or token
    p_repeated = Project(name="Project X", description="zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", target_customers="Devs", industry="Tech", stage="MVP")
    is_ready, missing, errs = validator.validate_project_readiness(p_repeated, "bmc")
    assert not is_ready

    # 4. Valid short coherent idea
    p_valid = Project(
        name="CoffeeDrop",
        description="On-demand specialty coffee delivery for co-working spaces",
        target_customers="Freelancers and remote teams",
        industry="Food & Beverage",
        stage="Seed"
    )
    is_ready, missing, errs = validator.validate_project_readiness(p_valid, "bmc")
    assert is_ready
    assert len(missing) == 0

    # 5. BMC missing target customers
    p_no_target = Project(
        name="CoffeeDrop",
        description="On-demand specialty coffee delivery",
        target_customers="",
        industry="Food & Beverage",
        stage="Seed"
    )
    is_ready, missing, errs = validator.validate_project_readiness(p_no_target, "bmc")
    assert not is_ready
    assert "target_customers" in missing

    # 6. Tech Stack with technical constraints/context
    p_tech = Project(
        name="DataEngine",
        description="High-throughput real-time telemetry processing pipeline handling 100k events/sec with sub-second latency",
        target_customers="DevOps engineers",
        industry="Infrastructure",
        stage="Growth"
    )
    is_ready, missing, errs = validator.validate_project_readiness(p_tech, "tech_stack")
    assert is_ready


def test_readiness_validation_api_blocks_gemini_and_preserves_version(test_user, db):
    """Ensure HTTP 422 READINESS_VALIDATION_FAILED is returned without invoking Gemini or creating a version."""
    user = test_user["user"]
    client = test_user["client"]
    headers = {"X-CSRF-Token": test_user["csrf_token"]}

    # Create project with missing/insufficient info
    sparse_project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name="Sparse App",
        description="asdf",
        target_customers="",
        industry="Software",
        stage="Idea"
    )
    db.add(sparse_project)
    db.commit()

    with patch("app.api.modules.ai_service.generate_bmc") as mock_gemini:
        resp = client.post(
            f"/api/projects/{sparse_project.id}/modules/bmc/generate",
            headers=headers
        )
        assert resp.status_code == 422
        body = resp.json()["detail"]
        assert body["error"] == "READINESS_VALIDATION_FAILED"
        assert "target_customers" in body["missing_fields"]
        assert len(body["reasons"]) > 0

        # Verify Gemini was never called
        mock_gemini.assert_not_called()

        # Verify no version was created
        mod = db.query(ModuleContent).filter(
            ModuleContent.project_id == sparse_project.id,
            ModuleContent.module_type == "bmc"
        ).first()
        if mod:
            versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod.id).all()
            assert len(versions) == 0


# ==============================================================================
# PHASE 6 TESTS: Historical Version Immutability
# ==============================================================================

def test_historical_version_immutability_on_conflict_resolution(db, test_user):
    """
    Ensure resolving conflict by replacing an older version does NOT mutate
    the remaining historical versions in place.
    """
    user = test_user["user"]
    project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name="Version Immutable Proj",
        description="Valid description for enterprise cloud operations",
        target_customers="CTOs",
        industry="Tech",
        stage="Seed"
    )
    db.add(project)
    db.commit()

    module = VersionService.get_or_create_module(db, project.id, "bmc")

    # Create 5 distinct versions
    versions = []
    for i in range(1, 6):
        data = {"block": f"value_{i}", "version_number": i}
        v = VersionService.save_new_version(
            db=db,
            module=module,
            data=data,
            change_summary=f"Created V{i}"
        )
        versions.append(v)

    # Record snapshot of V2, V3, V4, V5 data
    v2_id, v2_data = versions[1].id, dict(versions[1].data)
    v3_id, v3_data = versions[2].id, dict(versions[2].data)
    v4_id, v4_data = versions[3].id, dict(versions[3].data)
    v5_id, v5_data = versions[4].id, dict(versions[4].data)
    target_id_to_delete = versions[0].id # Delete V1

    new_data = {"block": "brand_new_v6_data", "version_number": 6}

    # Resolve conflict by deleting V1 slot and saving new version
    res = VersionService.resolve_conflict_and_replace(
        db=db,
        module=module,
        replace_version_id=target_id_to_delete,
        new_data=new_data,
        change_summary="Replaced V1 with V6"
    )

    db.expire_all()

    # Verify target was deleted
    deleted = db.query(ModuleVersion).filter(ModuleVersion.id == target_id_to_delete).first()
    assert deleted is None

    # Verify remaining versions V2, V3, V4, V5 are EXACTLY unchanged
    v2_after = db.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()
    v3_after = db.query(ModuleVersion).filter(ModuleVersion.id == v3_id).first()
    v4_after = db.query(ModuleVersion).filter(ModuleVersion.id == v4_id).first()
    v5_after = db.query(ModuleVersion).filter(ModuleVersion.id == v5_id).first()

    assert v2_after.data == v2_data
    assert v3_after.data == v3_data
    assert v4_after.data == v4_data
    assert v5_after.data == v5_data

    # Verify total count is still 5
    all_current = db.query(ModuleVersion).filter(
        ModuleVersion.module_content_id == module.id
    ).all()
    assert len(all_current) == 5
    assert res.data["block"] == "brand_new_v6_data"


# ==============================================================================
# PHASE 14 TESTS: Admin Telemetry & AI Recovery Safety
# ==============================================================================

def test_admin_zero_operations_metrics_displays_none(test_admin, db):
    """
    Ensure when 0 AI operations exist in the window, success_rate is None (N/A)
    rather than a fabricated 100.0%.
    """
    client = test_admin["client"]
    headers = {"X-CSRF-Token": test_admin["csrf_token"]}

    resp = client.get("/api/admin/dashboard/stats?window=1h", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()

    ai_stats = stats.get("ai_operations", {})
    # If total operations is 0, success_rate must be None (not 100.0)
    if ai_stats.get("total_ai_ops", 0) == 0:
        assert ai_stats.get("success_rate") is None


def test_admin_ai_retry_refuses_when_project_missing(test_admin, db):
    """
    Ensure admin AI retry refuses when project context is missing,
    and NEVER fabricates a synthetic project.
    """
    client = test_admin["client"]
    headers = {"X-CSRF-Token": test_admin["csrf_token"]}

    # Create an AIOperation with non-existent project_id
    ghost_project_id = "prj_nonexistent_99999"
    op = AIOperation(
        id=gen_id("aio_"),
        project_id=ghost_project_id,
        user_id=test_admin["admin"].id,
        module_type="bmc",
        operation_type="generation",
        model_name="gemini-2.5-flash",
        status="failed",
        duration_ms=120,
        retry_count=0,
        error_category="network",
        error_message="Simulated past network timeout"
    )
    db.add(op)
    db.commit()

    resp = client.post(f"/api/admin/ai-operations/{op.id}/retry", headers=headers)
    assert resp.status_code == 400
    assert "original project no longer exists" in resp.text.lower()

    # Verify no project with ghost_project_id was created
    ghost_proj = db.query(Project).filter(Project.id == ghost_project_id).first()
    assert ghost_proj is None


def test_failed_save_during_conflict_resolution_rolls_back_and_preserves_target(db, test_user):
    """
    Simulate a failure after target deletion but before commit.
    Verify transaction rollback preserves the target version in full.
    """
    user = test_user["user"]
    project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name="Rollback Test Proj",
        description="Testing transactional version safety",
        target_customers="QA Engineers",
        industry="DevTools",
        stage="MVP"
    )
    db.add(project)
    db.commit()

    module = VersionService.get_or_create_module(db, project.id, "bmc")
    v1 = VersionService.save_new_version(db, module, {"block": "v1_original"}, change_summary="V1")
    target_id = v1.id

    # Simulate database error during new version insertion
    with patch.object(db, "add", side_effect=RuntimeError("Simulated database constraint or disk error")):
        with pytest.raises(RuntimeError):
            VersionService.resolve_conflict_and_replace(
                db=db,
                module=module,
                replace_version_id=target_id,
                new_data={"block": "v_failing"}
            )

    db.expire_all()

    # Verify target was NOT deleted; it rolled back and is preserved
    preserved_v1 = db.query(ModuleVersion).filter(ModuleVersion.id == target_id).first()
    assert preserved_v1 is not None
    assert preserved_v1.data == {"block": "v1_original"}


def test_restore_version_creates_new_snapshot_without_mutating_source(db, test_user):
    """
    Verify that restoring a historical version creates a new snapshot
    and NEVER mutates the source historical version.
    """
    user = test_user["user"]
    project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name="Restore Safety Proj",
        description="Testing restore immutability",
        target_customers="Archivists",
        industry="Storage",
        stage="Seed"
    )
    db.add(project)
    db.commit()

    module = VersionService.get_or_create_module(db, project.id, "bmc")
    v1 = VersionService.save_new_version(db, module, {"state": "initial_v1"}, change_summary="V1 Initial")
    v2 = VersionService.save_new_version(db, module, {"state": "modified_v2"}, change_summary="V2 Pivot")

    v1_id = v1.id
    v1_original_data = dict(v1.data)
    v1_original_name = v1.version_name

    # Restore V1
    restored = VersionService.restore_version(db, module, v1_id)

    db.expire_all()

    # Verify source V1 is completely unchanged
    source_v1 = db.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
    assert source_v1.data == v1_original_data
    assert source_v1.version_name == v1_original_name

    # Verify restored is a brand-new version with its own ID
    assert restored.id != v1_id
    assert restored.version_number == 3
    assert restored.data == v1_original_data


def test_concurrent_version_creation_respects_five_version_limit(db, test_user):
    """
    Submit concurrent requests against the 5-version limit.
    Verify the limit of 5 is strictly enforced and no race condition creates >5 versions.
    """
    import concurrent.futures
    user = test_user["user"]
    project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name="Concurrency Test Proj",
        description="Testing concurrent version limit enforcement",
        target_customers="Engineers",
        industry="Cloud",
        stage="Seed"
    )
    db.add(project)
    db.commit()

    module = VersionService.get_or_create_module(db, project.id, "bmc")

    results = []
    errors = []

    def attempt_create(idx):
        from app.db.session import SessionLocal
        local_db = SessionLocal()
        try:
            mod = VersionService.get_or_create_module(local_db, project.id, "bmc")
            v = VersionService.save_new_version(
                db=local_db,
                module=mod,
                data={"worker": idx},
                change_summary=f"Worker {idx}"
            )
            return ("success", v.version_number)
        except Exception as e:
            return ("error", str(e))
        finally:
            local_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(attempt_create, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            st, detail = f.result()
            if st == "success":
                results.append(detail)
            else:
                errors.append(detail)

    db.expire_all()
    all_versions = db.query(ModuleVersion).filter(
        ModuleVersion.module_content_id == module.id
    ).all()

    # The maximum number of versions stored must NEVER exceed 5
    assert len(all_versions) <= 5
    # Excess concurrent requests must have received the 409 Version Limit error
    assert any("VERSION_LIMIT_EXCEEDED" in str(err) or "maximum of 5" in str(err).lower() for err in errors)

