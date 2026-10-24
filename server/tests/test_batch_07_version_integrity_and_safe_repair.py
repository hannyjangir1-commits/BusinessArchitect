import uuid
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import concurrent.futures

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask, AuditLog, gen_id
from app.services.version_service import VersionService, MAX_VERSIONS_LIMIT
from app.services.roadmap_service import RoadmapDomainService
from app.core.security import hash_password


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def create_user_fixture(db: Session, username: str, role: str = "user", password: str = "TestPassword123!") -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.role = role
        user.is_suspended = False
        user.hashed_password = hash_password(password)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        id=gen_id("usr_"),
        username=username,
        email=f"{username.lower()}@test.com",
        hashed_password=hash_password(password),
        role=role,
        is_suspended=False,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project_fixture(db: Session, user: User, name: str = "Test Project") -> Project:
    project = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name=name,
        description="Version & integrity test project",
        stage="Idea / MVP",
        industry="Technology",
        budget="50k-100k",
        target_customers="Developers",
        goals="Automated Venture Architecture",
        business_context="SaaS",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def login_user(client: TestClient, username: str, password: str = "TestPassword123!"):
    resp = client.post("/api/auth/login", json={"email_or_username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    csrf = resp.json().get("csrf_token")
    return {"cookies": resp.cookies, "headers": {"X-CSRF-Token": csrf}}


def login_admin(client: TestClient, username: str, password: str = "TestPassword123!"):
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Admin login failed for {username}: {resp.text}"
    csrf = resp.json().get("csrf_token")
    return {"cookies": resp.cookies, "headers": {"X-CSRF-Token": csrf}}


# ==============================================================================
# 1. B06 REPRODUCTION & FIX: Restored older version preserved by repair
# ==============================================================================

def test_b06_healthy_restored_older_version_preserved_by_repair(db: Session, client: TestClient):
    """
    Defect B06 reproduction:
    User creates V1, V2, V3. User restores V1 as active.
    Previous broken fix_missing_active_versions blindly overwrote active_version_id with V3 (latest).
    Fixed repair MUST leave V1 active, leave all flags untouched, and report 0 repairs.
    """
    user = create_user_fixture(db, "b06_user", role="user")
    project = create_project_fixture(db, user, "B06 Restored Preservation")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    v1 = VersionService.save_new_version(db, module, {"tagline": "V1 Original"}, change_summary="V1")
    v2 = VersionService.save_new_version(db, module, {"tagline": "V2 Pivot"}, change_summary="V2")
    v3 = VersionService.save_new_version(db, module, {"tagline": "V3 Current"}, change_summary="V3")

    # User restores V1
    VersionService.restore_version(db, module, v1.id, commit=True)
    db.refresh(module)
    assert module.active_version_id == v1.id
    db.refresh(v1)
    db.refresh(v3)
    assert v1.is_active is True
    assert v3.is_active is False

    # Admin executes repair
    admin = create_user_fixture(db, "b06_admin", role="super_admin")
    auth = login_admin(client, "b06_admin")
    repair_resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": True},
        cookies=auth["cookies"],
        headers=auth["headers"]
    )
    assert repair_resp.status_code == 200
    # Must report 0 repairs for this module because it's already healthy
    db.refresh(module)
    db.refresh(v1)
    db.refresh(v3)

    # Restored V1 MUST BE PRESERVED!
    assert module.active_version_id == v1.id, f"Expected active V1 ({v1.id}), got {module.active_version_id}"
    assert v1.is_active is True
    assert v3.is_active is False


# ==============================================================================
# 2. Pointer / Flag Mismatch Repaired
# ==============================================================================

def test_pointer_flag_mismatch_repaired(db: Session):
    """
    If module.active_version_id points to V1, but V1.is_active is False or V2.is_active is True,
    repair must synchronize flags without changing the active pointer.
    """
    user = create_user_fixture(db, "mismatch_user")
    project = create_project_fixture(db, user, "Mismatch Project")
    module = VersionService.get_or_create_module(db, project.id, "tech_stack")

    v1 = VersionService.save_new_version(db, module, {"tier": 1}, change_summary="V1")
    v2 = VersionService.save_new_version(db, module, {"tier": 2}, change_summary="V2")

    # Simulate flag corruption: module points to V1, but flags are corrupted
    module.active_version_id = v1.id
    v1.is_active = False
    v2.is_active = True
    db.commit()

    repaired = VersionService.repair_active_version_for_module(db, module)
    assert repaired is True
    db.commit()

    db.refresh(module)
    db.refresh(v1)
    db.refresh(v2)
    assert module.active_version_id == v1.id
    assert v1.is_active is True
    assert v2.is_active is False


# ==============================================================================
# 3. Foreign Module Pointer Repaired Safely
# ==============================================================================

def test_foreign_module_pointer_repaired(db: Session):
    """
    If module A points to a version belonging to module B, repair detects the foreign pointer,
    falls back to the newest valid version of module A, and sets flags cleanly.
    """
    user = create_user_fixture(db, "foreign_ptr_user")
    project = create_project_fixture(db, user, "Foreign Ptr Project")
    mod_a = VersionService.get_or_create_module(db, project.id, "bmc")
    mod_b = VersionService.get_or_create_module(db, project.id, "market_research")

    v1_a = VersionService.save_new_version(db, mod_a, {"v": "1A"}, change_summary="1A")
    v2_a = VersionService.save_new_version(db, mod_a, {"v": "2A"}, change_summary="2A")
    v1_b = VersionService.save_new_version(db, mod_b, {"v": "1B"}, change_summary="1B")

    # Corrupt mod_a to point to v1_b
    mod_a.active_version_id = v1_b.id
    db.commit()

    repaired = VersionService.repair_active_version_for_module(db, mod_a)
    assert repaired is True
    db.commit()

    db.refresh(mod_a)
    db.refresh(v1_a)
    db.refresh(v2_a)
    # Fallback chooses newest version of mod_a (v2_a)
    assert mod_a.active_version_id == v2_a.id
    assert v2_a.is_active is True
    assert v1_a.is_active is False


# ==============================================================================
# 4. Empty Module Invariants
# ==============================================================================

def test_empty_module_invariants(db: Session):
    """Empty module must have active_version_id = None and no active flags."""
    user = create_user_fixture(db, "empty_mod_user")
    project = create_project_fixture(db, user, "Empty Mod Project")
    module = VersionService.get_or_create_module(db, project.id, "idea_validator")

    # If active_version_id was set to something dangling
    module.active_version_id = "nonexistent_ver_id"
    db.commit()

    repaired = VersionService.repair_active_version_for_module(db, module)
    assert repaired is True
    db.commit()

    db.refresh(module)
    assert module.active_version_id is None

    # Idempotency on empty module
    repaired_again = VersionService.repair_active_version_for_module(db, module)
    assert repaired_again is False


# ==============================================================================
# 5. Repair Idempotency
# ==============================================================================

def test_repair_idempotency(db: Session):
    """Running repair twice performs mutations on run 1 and reports 0 changes on run 2."""
    user = create_user_fixture(db, "idempotent_user")
    project = create_project_fixture(db, user, "Idempotent Project")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    v1 = VersionService.save_new_version(db, module, {"v": 1}, change_summary="V1")
    v2 = VersionService.save_new_version(db, module, {"v": 2}, change_summary="V2")

    # Corrupt pointer to None
    module.active_version_id = None
    v1.is_active = False
    v2.is_active = False
    db.commit()

    # Run 1: repairs pointer to newest v2
    assert VersionService.repair_active_version_for_module(db, module) is True
    db.commit()
    db.refresh(module)
    assert module.active_version_id == v2.id

    # Run 2: already clean, returns False
    assert VersionService.repair_active_version_for_module(db, module) is False


# ==============================================================================
# 6. P07 REPRODUCTION & FIX: Pruning keeps active oldest
# ==============================================================================

def test_p07_pruning_keeps_active_oldest(db: Session):
    """
    Defect P07 reproduction:
    Module has 6 versions (V1..V6). User restored V1 as active.
    Previous broken pruning kept top 5 newest (V6..V2) and deleted V1, leaving dangling active_version_id!
    Fixed pruning MUST keep active V1 + newest 4 (V6, V5, V4, V3), deleting only V2.
    """
    user = create_user_fixture(db, "p07_user")
    project = create_project_fixture(db, user, "P07 Prune Oldest")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    # Save V1..V5
    versions = []
    for i in range(1, 6):
        v = VersionService.save_new_version(db, module, {"tier": i}, change_summary=f"V{i}")
        versions.append(v)

    # Manually create V6 in database to simulate legacy/unpruned state
    v6 = ModuleVersion(
        id=gen_id("ver_"),
        module_content_id=module.id,
        version_number=6,
        version_name="BMC V6",
        data={"tier": 6},
        change_summary="V6",
        is_active=False
    )
    db.add(v6)
    db.commit()
    versions.append(v6)

    # User restores V1 as active
    v1 = versions[0]
    VersionService.restore_version(db, module, v1.id, commit=True)
    db.refresh(module)
    assert module.active_version_id == v1.id

    # Total versions in DB before prune is 6
    all_vers = VersionService.get_versions(db, module.id)
    assert len(all_vers) == 6

    # Run safe pruning
    deleted_count = VersionService.prune_excess_versions_for_module(db, module, limit=5)
    db.commit()

    assert deleted_count == 1
    remaining = VersionService.get_versions(db, module.id)
    assert len(remaining) == 5

    remaining_ids = {r.id for r in remaining}
    # V1 MUST BE IN REMAINING!
    assert v1.id in remaining_ids, "Critical regression: active oldest V1 was deleted!"
    # V6, V5, V4, V3 must be kept
    assert v6.id in remaining_ids
    assert versions[4].id in remaining_ids  # V5
    assert versions[3].id in remaining_ids  # V4
    assert versions[2].id in remaining_ids  # V3
    # V2 was pruned
    assert versions[1].id not in remaining_ids  # V2 deleted

    # Pointer is still valid and points to V1
    db.refresh(module)
    assert module.active_version_id == v1.id
    db.refresh(v1)
    assert v1.is_active is True


def test_pruning_keeps_active_newest(db: Session):
    """When active version is the newest (V6), pruning deletes oldest (V1)."""
    user = create_user_fixture(db, "prune_newest_user")
    project = create_project_fixture(db, user, "Prune Newest")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    versions = []
    for i in range(1, 6):
        v = VersionService.save_new_version(db, module, {"tier": i}, change_summary=f"V{i}")
        versions.append(v)

    # Add V6 as active
    v6 = ModuleVersion(
        id=gen_id("ver_"),
        module_content_id=module.id,
        version_number=6,
        version_name="BMC V6",
        data={"tier": 6},
        change_summary="V6",
        is_active=True
    )
    for v in versions:
        v.is_active = False
    db.add(v6)
    module.active_version_id = v6.id
    db.commit()

    deleted = VersionService.prune_excess_versions_for_module(db, module, limit=5)
    db.commit()

    assert deleted == 1
    remaining = VersionService.get_versions(db, module.id)
    assert len(remaining) == 5
    remaining_nums = [r.version_number for r in remaining]
    assert remaining_nums == [2, 3, 4, 5, 6]
    assert v6.id == module.active_version_id


# ==============================================================================
# 7. B08 REPRODUCTION & FIX: Version-capacity preflight makes zero provider calls
# ==============================================================================

def test_b08_capacity_preflight_makes_zero_provider_calls(db: Session):
    """
    Defect B08 reproduction:
    When a module already has 5 saved versions, invoking generation must fail
    at Stage 0 capacity preflight and make ZERO calls to AI provider or Gemini synthesis.
    """
    user = create_user_fixture(db, "b08_user")
    project = create_project_fixture(db, user, "B08 Capacity Preflight")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    # Seed 5 versions
    for i in range(1, 6):
        VersionService.save_new_version(db, module, {"tagline": f"V{i}"}, change_summary=f"V{i}")

    from app.services.module_orchestration_service import ModuleOrchestrationService
    from app.ai.gemini_service import ai_service

    provider_spy = MagicMock(side_effect=Exception("Provider should never be called!"))

    with patch.object(ai_service, "generate_bmc", provider_spy):
        with pytest.raises(HTTPException) as exc_info:
            ModuleOrchestrationService.execute_module_generation(
                db=db,
                project=project,
                module=module,
                module_type="bmc"
            )

        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert detail["error"] == "VERSION_LIMIT_EXCEEDED"
        assert len(detail["existing_versions"]) == 5

        # Provider spy was called ZERO times!
        assert provider_spy.call_count == 0, f"Expected 0 provider calls, got {provider_spy.call_count}"


# ==============================================================================
# 8. Save-Time Race Still Returns Controlled Conflict
# ==============================================================================

def test_save_time_race_enforces_capacity(db: Session):
    """
    Even if preflight passes (e.g. 4 versions), if another transaction inserts a 5th version,
    save_new_version under row lock catches the race and raises 409 conflict.
    """
    user = create_user_fixture(db, "race_cap_user")
    project = create_project_fixture(db, user, "Race Capacity")
    module = VersionService.get_or_create_module(db, project.id, "tech_stack")

    for i in range(1, 6):
        VersionService.save_new_version(db, module, {"v": i}, change_summary=f"V{i}")

    # Attempt direct save_new_version
    with pytest.raises(HTTPException) as exc_info:
        VersionService.save_new_version(db, module, {"v": 6}, change_summary="V6")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "VERSION_LIMIT_EXCEEDED"


# ==============================================================================
# 9. Commit=False Rollback Restores the Entire Operation
# ==============================================================================

def test_commit_false_rollback_restores_entire_operation(db: Session):
    """When commit=False is passed, db.rollback() in caller discards the new version completely."""
    user = create_user_fixture(db, "rollback_user")
    project = create_project_fixture(db, user, "Rollback Project")
    module = VersionService.get_or_create_module(db, project.id, "bmc")

    v1 = VersionService.save_new_version(db, module, {"v": 1}, change_summary="Initial", commit=True)
    initial_active = module.active_version_id

    # Save new version with commit=False
    v2 = VersionService.save_new_version(db, module, {"v": 2}, change_summary="Uncommitted", commit=False)

    # Roll back transaction
    db.rollback()

    # Verify state from a fresh query
    fresh_session = SessionLocal()
    try:
        fresh_module = fresh_session.query(ModuleContent).filter(ModuleContent.id == module.id).first()
        fresh_versions = fresh_session.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).all()
        assert len(fresh_versions) == 1
        assert fresh_versions[0].id == v1.id
        assert fresh_module.active_version_id == initial_active
    finally:
        fresh_session.close()


# ==============================================================================
# 10. Roadmap Working Tasks Synchronized on Restore and Repair
# ==============================================================================

def test_roadmap_tasks_synchronized_after_restore_and_repair(db: Session, client: TestClient):
    """Restoring an older roadmap version synchronizes relational RoadmapTask rows."""
    user = create_user_fixture(db, "roadmap_sync_user")
    project = create_project_fixture(db, user, "Roadmap Sync Project")
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    v1_tasks = [{"task_code": "TSK-01", "title": "Setup Arch", "start_date": "2026-11-01", "end_date": "2026-11-05"}]
    v2_tasks = [
        {"task_code": "TSK-01", "title": "Setup Arch", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "TSK-02", "title": "Build UI", "start_date": "2026-11-05", "end_date": "2026-11-10", "dependencies": ["TSK-01"]}
    ]

    v1 = VersionService.save_new_version(db, module, {"tasks": v1_tasks}, change_summary="V1 Single Task")
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v1_tasks)
    db.commit()

    v2 = VersionService.save_new_version(db, module, {"tasks": v2_tasks}, change_summary="V2 Two Tasks")
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v2_tasks)
    db.commit()

    tasks_v2 = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(tasks_v2) == 2

    # Restore V1
    VersionService.restore_version(db, module, v1.id, commit=False)
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v1_tasks)
    db.commit()

    tasks_after_restore = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(tasks_after_restore) == 1
    assert tasks_after_restore[0].task_code == "TSK-01"


# ==============================================================================
# 11. Multi-Threaded Concurrency: Different Modules Independent
# ==============================================================================

def test_different_module_concurrency_independence(db: Session):
    """Mutations on different modules proceed independently on separate striped locks."""
    user = create_user_fixture(db, "diff_mod_user")
    project = create_project_fixture(db, user, "Diff Mod Project")
    mod_a = VersionService.get_or_create_module(db, project.id, "bmc")
    mod_b = VersionService.get_or_create_module(db, project.id, "tech_stack")

    mod_a_id = str(mod_a.id)
    mod_b_id = str(mod_b.id)

    def save_a():
        s = SessionLocal()
        try:
            m = s.query(ModuleContent).filter(ModuleContent.id == mod_a_id).first()
            VersionService.save_new_version(s, m, {"key": "A"}, change_summary="A1")
            return "A_OK"
        finally:
            s.close()

    def save_b():
        s = SessionLocal()
        try:
            m = s.query(ModuleContent).filter(ModuleContent.id == mod_b_id).first()
            VersionService.save_new_version(s, m, {"key": "B"}, change_summary="B1")
            return "B_OK"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(save_a)
        f_b = executor.submit(save_b)
        res_a = f_a.result()
        res_b = f_b.result()

    assert res_a == "A_OK"
    assert res_b == "B_OK"
    assert len(VersionService.get_versions(db, mod_a_id)) == 1
    assert len(VersionService.get_versions(db, mod_b_id)) == 1


# ==============================================================================
# 12. Same-Module Concurrent Capacity Enforcement
# ==============================================================================

def test_same_module_concurrent_capacity_enforcement(db: Session):
    """Two concurrent saves on a module with 4 versions: exactly 1 succeeds, 1 gets 409 conflict."""
    user = create_user_fixture(db, "same_mod_cap_user")
    project = create_project_fixture(db, user, "Same Mod Cap Project")
    module = VersionService.get_or_create_module(db, project.id, "market_research")

    for i in range(1, 5):
        VersionService.save_new_version(db, module, {"i": i}, change_summary=f"V{i}")

    module_id = str(module.id)
    results = []

    def try_save(val: int):
        s = SessionLocal()
        try:
            m = s.query(ModuleContent).filter(ModuleContent.id == module_id).first()
            VersionService.save_new_version(s, m, {"val": val}, change_summary=f"Concurrent {val}")
            results.append("SUCCESS")
        except HTTPException as e:
            results.append(f"CONFLICT_{e.status_code}")
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(try_save, 1)
        f2 = executor.submit(try_save, 2)
        f1.result()
        f2.result()

    assert "SUCCESS" in results
    assert "CONFLICT_409" in results
    # Module must have exactly 5 versions
    assert len(VersionService.get_versions(db, module.id)) == 5


# ==============================================================================
# 13. Tenant Isolation, CSRF and Admin Permission Checks
# ==============================================================================

def test_tenant_isolation_csrf_and_admin_permission(db: Session, client: TestClient):
    """Normal user cannot run admin repair; admin repair requires CSRF and confirmation."""
    normal_user = create_user_fixture(db, "normal_repair_user", role="user")
    auth_user = login_user(client, "normal_repair_user")

    # 1. Normal user forbidden
    resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": True},
        cookies=auth_user["cookies"],
        headers=auth_user["headers"]
    )
    assert resp.status_code == 403

    # 2. Admin missing CSRF
    admin = create_user_fixture(db, "admin_csrf_user", role="super_admin")
    auth_admin = login_admin(client, "admin_csrf_user")
    resp_no_csrf = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": True},
        cookies=auth_admin["cookies"],
        headers={}
    )
    assert resp_no_csrf.status_code == 403

    # 3. Admin missing confirmation
    resp_no_conf = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": False},
        cookies=auth_admin["cookies"],
        headers=auth_admin["headers"]
    )
    assert resp_no_conf.status_code == 400
    assert "explicit confirmation" in resp_no_conf.text


# ==============================================================================
# 14. Audit Log Recorded on Repair Execution
# ==============================================================================

def test_admin_audit_log_recorded_on_repair(db: Session, client: TestClient):
    """Admin repair executions record audit logs with outcome and repaired count."""
    admin = create_user_fixture(db, "audit_repair_admin", role="super_admin")
    auth = login_admin(client, "audit_repair_admin")

    resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": True},
        cookies=auth["cookies"],
        headers=auth["headers"]
    )
    assert resp.status_code == 200

    log = db.query(AuditLog).filter(
        AuditLog.actor_id == admin.id,
        AuditLog.action == "integrity_repair_fix_missing_active_versions"
    ).order_by(AuditLog.created_at.desc()).first()

    assert log is not None
    assert log.outcome == "success"
    assert "repaired_count" in log.details
