import copy
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask, AuditLog, gen_id
from app.services.version_service import VersionService, MAX_VERSIONS_LIMIT
from app.services.roadmap_service import RoadmapDomainService
from app.services.task_graph_validator import IncompatibleTaskGraphError
from app.core.security import hash_password
from app.ai.gemini_service import ai_service


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


def create_user(db: Session, username: str, role: str = "user") -> User:
    u = db.query(User).filter(User.username == username).first()
    if u:
        return u
    u = User(
        id=gen_id("usr_"),
        username=username,
        email=f"{username}@test.com",
        hashed_password=hash_password("Password123!"),
        role=role,
        is_suspended=False,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc)
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def create_project(db: Session, user: User, name: str = "P71 Project") -> Project:
    p = Project(
        id=gen_id("prj_"),
        user_id=user.id,
        name=name,
        description="Batch 07.1 test project",
        stage="Idea / MVP",
        industry="Technology",
        budget="50k-100k",
        target_customers="Enterprise",
        goals="Autonomous Architecture",
        business_context="SaaS",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def login(client: TestClient, username: str, role: str = "user"):
    url = "/api/admin/auth/login" if role in ("admin", "super_admin") else "/api/auth/login"
    body = {"username": username, "password": "Password123!"} if role in ("admin", "super_admin") else {"email_or_username": username, "password": "Password123!"}
    resp = client.post(url, json=body)
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    csrf = resp.json().get("csrf_token")
    return {"cookies": resp.cookies, "headers": {"X-CSRF-Token": csrf}}


# ==============================================================================
# SECTION 2: DETERMINISTIC REGRESSION: STALE IN-MEMORY FLAGS PRESERVED ON RESTORE
# ==============================================================================

def test_stale_in_memory_version_flags_authoritatively_updated_on_restore():
    """
    Independent reproduction:
    A. Create module M with V1 active=True, V2 active=False, M.active_version_id=V1.
    B. Session A loads and retains both version objects.
    C. Session B restores V2 and commits.
    D. Session A restores V1 and commits.
    Required Contract:
    M.active_version_id becomes V1.
    V1 is active=True, V2 is active=False in both Session A and a fresh Session C.
    """
    with SessionLocal() as s_init:
        user = create_user(s_init, "stale_flags_user")
        proj = create_project(s_init, user, "Stale Flags Proj")
        mod = VersionService.get_or_create_module(s_init, proj.id, "bmc")
        v1 = VersionService.save_new_version(s_init, mod, {"key": "v1_original"}, change_summary="V1")
        v2 = VersionService.save_new_version(s_init, mod, {"key": "v2_pivot"}, change_summary="V2")
        # Ensure V1 is active, V2 is inactive
        VersionService.restore_version(s_init, mod, v1.id)
        s_init.commit()
        mod_id = mod.id
        v1_id = v1.id
        v2_id = v2.id

    session_a = SessionLocal()
    session_b = SessionLocal()

    try:
        # Step B: Session A loads and retains both version objects
        mod_a = session_a.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        v1_a = session_a.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        v2_a = session_a.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()
        assert v1_a.is_active is True
        assert v2_a.is_active is False
        assert mod_a.active_version_id == v1_id

        # Step C: Session B restores V2 and commits
        mod_b = session_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        VersionService.restore_version(session_b, mod_b, v2_id)
        session_b.commit()

        # Verify Session B persisted V2=True, V1=False
        with SessionLocal() as s_check:
            chk_v1 = s_check.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
            chk_v2 = s_check.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()
            assert chk_v1.is_active is False
            assert chk_v2.is_active is True

        # Step D: Session A restores V1 and commits
        VersionService.restore_version(session_a, mod_a, v1_id)
        session_a.commit()

        # Inspect persisted results from fresh session
        with SessionLocal() as session_c:
            fresh_mod = session_c.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            fresh_v1 = session_c.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
            fresh_v2 = session_c.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()

            assert fresh_mod.active_version_id == v1_id, "active_version_id must be V1"
            assert fresh_v1.is_active is True, "V1 must be active in database"
            assert fresh_v2.is_active is False, "V2 must be inactive in database"
    finally:
        session_a.close()
        session_b.close()


# ==============================================================================
# SECTION 3: STALE-STATE VARIANTS ACROSS MUTATIONS
# ==============================================================================

def test_stale_cache_across_save_new_version():
    """Session A has cached V1. Session B creates V2. Session A creates V3. Only V3 is active."""
    with SessionLocal() as s_init:
        user = create_user(s_init, "stale_save_user")
        proj = create_project(s_init, user, "Stale Save Proj")
        mod = VersionService.get_or_create_module(s_init, proj.id, "tech_stack")
        v1 = VersionService.save_new_version(s_init, mod, {"tier": 1}, change_summary="V1")
        mod_id = mod.id
        v1_id = v1.id

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        # Session A loads V1
        mod_a = session_a.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        v1_a = session_a.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        assert v1_a.is_active is True

        # Session B creates V2
        mod_b = session_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        v2 = VersionService.save_new_version(session_b, mod_b, {"tier": 2}, change_summary="V2")
        session_b.commit()
        v2_id = v2.id

        # Session A creates V3
        v3 = VersionService.save_new_version(session_a, mod_a, {"tier": 3}, change_summary="V3")
        session_a.commit()
        v3_id = v3.id

        with SessionLocal() as fresh_s:
            fresh_mod = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            fresh_v1 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
            fresh_v2 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()
            fresh_v3 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v3_id).first()

            assert fresh_mod.active_version_id == v3_id
            assert fresh_v1.is_active is False
            assert fresh_v2.is_active is False
            assert fresh_v3.is_active is True
    finally:
        session_a.close()
        session_b.close()


def test_stale_cache_across_resolve_conflict_and_replace():
    """Session A has cached versions. Session B changes active version. Session A replaces version."""
    with SessionLocal() as s_init:
        user = create_user(s_init, "stale_replace_user")
        proj = create_project(s_init, user, "Stale Replace Proj")
        mod = VersionService.get_or_create_module(s_init, proj.id, "idea_validator")
        for i in range(1, 6):
            VersionService.save_new_version(s_init, mod, {"score": i}, change_summary=f"V{i}")
        mod_id = mod.id
        all_v = VersionService.get_versions(s_init, mod_id)
        v1_id = all_v[0].id
        v2_id = all_v[1].id
        v5_id = all_v[4].id

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        mod_a = session_a.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        vers_a = session_a.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod_id).all()
        assert len(vers_a) == 5

        # Session B restores V1
        mod_b = session_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        VersionService.restore_version(session_b, mod_b, v1_id)
        session_b.commit()

        # Session A replaces V2
        replaced = VersionService.resolve_conflict_and_replace(
            session_a, mod_a, replace_version_id=v2_id, new_data={"score": 6}, change_summary="Replaced V2"
        )
        session_a.commit()
        new_id = replaced.id

        with SessionLocal() as fresh_s:
            fresh_mod = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            fresh_vers = fresh_s.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod_id).all()
            assert len(fresh_vers) == 5
            assert fresh_mod.active_version_id == new_id

            active_vers = [v for v in fresh_vers if v.is_active]
            assert len(active_vers) == 1
            assert active_vers[0].id == new_id
    finally:
        session_a.close()
        session_b.close()


def test_stale_cache_across_delete_version():
    """Deleting active version selects deterministic fallback even if identity map is stale."""
    with SessionLocal() as s_init:
        user = create_user(s_init, "stale_delete_user")
        proj = create_project(s_init, user, "Stale Delete Proj")
        mod = VersionService.get_or_create_module(s_init, proj.id, "market_research")
        v1 = VersionService.save_new_version(s_init, mod, {"tam": "1B"}, change_summary="V1")
        v2 = VersionService.save_new_version(s_init, mod, {"tam": "2B"}, change_summary="V2")
        mod_id = mod.id
        v1_id = v1.id
        v2_id = v2.id

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        mod_a = session_a.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        v1_a = session_a.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        v2_a = session_a.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()

        # Session B restores V1
        mod_b = session_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        VersionService.restore_version(session_b, mod_b, v1_id)
        session_b.commit()

        # Session A deletes V1 (which is active in DB, but inactive in Session A's stale memory)
        VersionService.delete_version(session_a, mod_a, v1_id)
        session_a.commit()

        with SessionLocal() as fresh_s:
            fresh_mod = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            fresh_vers = fresh_s.query(ModuleVersion).filter(ModuleVersion.module_content_id == mod_id).all()
            assert len(fresh_vers) == 1
            assert fresh_vers[0].id == v2_id
            assert fresh_vers[0].is_active is True
            assert fresh_mod.active_version_id == v2_id
    finally:
        session_a.close()
        session_b.close()


# ==============================================================================
# SECTION 4: PRUNING-ROADMAP DESYNCHRONIZATION REGRESSION
# ==============================================================================

def test_admin_prune_excess_versions_synchronizes_roadmap_tasks(client: TestClient):
    """
    Independent reproduction:
    - Roadmap module has six versions.
    - V6 is flagged active and contains task NEW.
    - active_version_id is missing (None).
    - Current relational task table contains unfinished AI task OLD.
    - Run the real admin prune_excess_versions action.
    Required Contract:
    Pointer repairs to V6, AND task table reconciles with V6 (OLD replaced with NEW).
    """
    with SessionLocal() as s:
        admin = create_user(s, "prune_sync_admin", role="super_admin")
        user = create_user(s, "prune_sync_user")
        proj = create_project(s, user, "Prune Sync Proj")
        mod = VersionService.get_or_create_module(s, proj.id, "execution_roadmap")

        # Create 5 older versions
        for i in range(1, 6):
            VersionService.save_new_version(
                s, mod,
                data={"tasks": [{"task_code": f"T-0{i}", "title": f"Task {i}", "phase": "P1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary=f"V{i}"
            )

        # Create V6 with TASK-NEW directly in DB as 6th version
        v6 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=mod.id,
            version_number=6,
            version_name="Roadmap V6",
            data={"tasks": [{"task_code": "TASK-NEW", "title": "New Task", "phase": "P1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
            change_summary="V6 New",
            is_active=True
        )
        s.add(v6)
        s.flush()
        v6_id = v6.id

        # Intentionally break pointer and seed relational task table with TASK-OLD
        mod.active_version_id = None
        s.query(RoadmapTask).filter(RoadmapTask.project_id == proj.id).delete()
        old_task = RoadmapTask(
            project_id=proj.id,
            task_code="TASK-OLD",
            phase="P1",
            title="Old Stale Task",
            timeline="30-day",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            is_ai_generated=True
        )
        s.add(old_task)
        s.commit()
        proj_id = proj.id
        mod_id = mod.id

    auth = login(client, "prune_sync_admin", role="super_admin")
    resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "prune_excess_versions", "confirmation": True},
        cookies=auth["cookies"],
        headers=auth["headers"]
    )
    assert resp.status_code == 200, f"Prune repair failed: {resp.text}"

    with SessionLocal() as fresh_s:
        fresh_mod = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        assert fresh_mod.active_version_id == v6_id, "Pointer must repair to V6"

        tasks = fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()
        task_codes = [t.task_code for t in tasks]
        assert "TASK-NEW" in task_codes, "Relational tasks must synchronize to V6 active version"
        assert "TASK-OLD" not in task_codes, "Stale task OLD must be reconciled and removed"


# ==============================================================================
# SECTION 5 & 6: GRAPH CONFLICT CAUSES ATOMIC ROLLBACK
# ==============================================================================

def test_roadmap_graph_conflict_rolls_back_entire_operation(client: TestClient):
    """
    If restoring/repairing an active version causes an incompatible task graph
    with retained work, the entire transaction rolls back without mutating versions.
    """
    with SessionLocal() as s:
        user = create_user(s, "graph_rollback_user")
        proj = create_project(s, user, "Graph Rollback Proj")
        mod = VersionService.get_or_create_module(s, proj.id, "execution_roadmap")

        v1 = VersionService.save_new_version(
            s, mod,
            data={"tasks": [{"task_code": "T1", "title": "Task 1", "phase": "P1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
            change_summary="V1"
        )
        v2 = VersionService.save_new_version(
            s, mod,
            data={"tasks": [
                {"task_code": "T1", "title": "Task 1", "phase": "P1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
                {"task_code": "T2", "title": "Task 2", "phase": "P1", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["T1"]}
            ]},
            change_summary="V2"
        )
        s.commit()

        # Reconcile relational tasks for active version V2
        RoadmapDomainService.reconcile_roadmap_tasks(s, proj, v2.data["tasks"])

        # User adds a retained manual task MAN-1 depending on T2
        man_task = RoadmapTask(
            project_id=proj.id,
            task_code="MAN-1",
            phase="P1",
            title="Manual Task",
            timeline="30-day",
            start_date="2026-11-11",
            end_date="2026-11-15",
            status="In Progress",
            dependencies=["T2"],
            is_ai_generated=False
        )
        s.add(man_task)
        s.commit()
        proj_id = proj.id
        mod_id = mod.id
        v1_id = v1.id
        v2_id = v2.id

    auth = login(client, "graph_rollback_user")
    # Restoring V1 (which omits T2) must fail with 400 because retained MAN-1 depends on T2
    resp = client.post(
        f"/api/projects/{proj_id}/modules/execution_roadmap/versions/{v1_id}/restore",
        cookies=auth["cookies"],
        headers=auth["headers"]
    )
    assert resp.status_code == 400
    assert "RETAINED_TASK_PREREQUISITE_MISSING" in resp.text

    # Verify atomic rollback: V2 remains active, V1 remains inactive
    with SessionLocal() as fresh_s:
        m = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        v1_fresh = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        v2_fresh = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()

        assert m.active_version_id == v2_id, "active_version_id must remain V2"
        assert v2_fresh.is_active is True
        assert v1_fresh.is_active is False

        # Tasks must remain intact
        tasks = fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()
        codes = {t.task_code for t in tasks}
        assert "MAN-1" in codes
        assert "T2" in codes


# ==============================================================================
# SECTION 6: PRESERVE RESTORED OLDER VERSIONS DURING REPAIR AND PRUNING
# ==============================================================================

def test_pruning_and_repair_invariants():
    """Verify pruning limits, deterministic ordering, tie breaking, and empty module invariants."""
    with SessionLocal() as s:
        user = create_user(s, "invariants_user")
        proj = create_project(s, user, "Invariants Proj")
        mod = VersionService.get_or_create_module(s, proj.id, "bmc")

        # 1. Unsupported limit validation
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            VersionService.prune_excess_versions_for_module(s, mod, limit=0)

        with pytest.raises(ValueError, match="limit must be a positive integer"):
            VersionService.prune_excess_versions_for_module(s, mod, limit=-5)

        # 2. Empty module invariants
        assert VersionService.repair_active_version_for_module(s, mod) is False
        assert mod.active_version_id is None

        # 3. Create 5 versions via service, then insert 6th directly
        for i in range(1, 6):
            VersionService.save_new_version(s, mod, {"v": i}, change_summary=f"V{i}")

        v6 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=mod.id,
            version_number=6,
            version_name="BMC V6",
            data={"v": 6},
            change_summary="V6",
            is_active=False
        )
        s.add(v6)
        s.flush()

        all_v = VersionService.get_versions(s, mod.id)
        assert len(all_v) == 6
        v1 = all_v[0]

        # Restore V1 (oldest version)
        VersionService.restore_version(s, mod, v1.id)
        s.commit()

        # Prune with limit=5: V1 (oldest active) MUST SURVIVE
        deleted = VersionService.prune_excess_versions_for_module(s, mod, limit=5)
        assert deleted == 1
        s.commit()

        with SessionLocal() as fresh_s:
            rem = VersionService.get_versions(fresh_s, mod.id)
            rem_ids = {v.id for v in rem}
            assert len(rem) == 5
            assert v1.id in rem_ids, "Restored oldest version V1 must be preserved during pruning"
            fresh_m = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod.id).first()
            assert fresh_m.active_version_id == v1.id

            # Verify idempotency: second prune deletes 0
            del_second = VersionService.prune_excess_versions_for_module(fresh_s, fresh_m, limit=5)
            assert del_second == 0


def test_foreign_module_pointer_repaired():
    """A foreign pointer pointing to another module's version is repaired to a valid version of this module."""
    with SessionLocal() as s:
        user = create_user(s, "foreign_pointer_user")
        proj = create_project(s, user, "Foreign Pointer Proj")
        mod_a = VersionService.get_or_create_module(s, proj.id, "bmc")
        mod_b = VersionService.get_or_create_module(s, proj.id, "tech_stack")

        va = VersionService.save_new_version(s, mod_a, {"mod": "a"}, change_summary="VA")
        vb = VersionService.save_new_version(s, mod_b, {"mod": "b"}, change_summary="VB")
        s.commit()

        # Set mod_a's pointer to mod_b's version
        mod_a.active_version_id = vb.id
        s.commit()

        # Repair mod_a
        was_repaired = VersionService.repair_active_version_for_module(s, mod_a)
        assert was_repaired is True
        s.commit()

        with SessionLocal() as fresh_s:
            fresh_a = fresh_s.query(ModuleContent).filter(ModuleContent.id == mod_a.id).first()
            assert fresh_a.active_version_id == va.id, "Pointer must be repaired to mod_a's own version"


# ==============================================================================
# SECTION 8: CAPACITY ENFORCEMENT & PREFLIGHT
# ==============================================================================

def test_version_capacity_enforcement_and_zero_provider_calls(client: TestClient):
    """At 5 versions, generation/modify returns 409 Conflict with 0 provider calls."""
    with SessionLocal() as s:
        user = create_user(s, "capacity_409_user")
        proj = create_project(s, user, "Capacity Proj")
        mod = VersionService.get_or_create_module(s, proj.id, "bmc")
        for i in range(1, 6):
            VersionService.save_new_version(s, mod, {"i": i}, change_summary=f"V{i}")
        s.commit()
        proj_id = proj.id

    auth = login(client, "capacity_409_user")

    with patch.object(ai_service, "generate_bmc") as mock_gen, \
         patch.object(ai_service, "modify_section") as mock_mod:

        # Attempt generate on full module
        resp_gen = client.post(
            f"/api/projects/{proj_id}/modules/bmc/generate",
            cookies=auth["cookies"],
            headers=auth["headers"]
        )
        assert resp_gen.status_code == 409
        assert resp_gen.json()["detail"]["error"] == "VERSION_LIMIT_EXCEEDED"
        assert mock_gen.call_count == 0, "Zero provider calls must be made on capacity conflict"

        # Attempt modify on full module
        resp_mod = client.post(
            f"/api/projects/{proj_id}/modules/bmc/modify",
            json={"instruction": "Add more details"},
            cookies=auth["cookies"],
            headers=auth["headers"]
        )
        assert resp_mod.status_code == 409
        assert resp_mod.json()["detail"]["error"] == "VERSION_LIMIT_EXCEEDED"
        assert mock_mod.call_count == 0, "Zero provider calls must be made on capacity conflict"


# ==============================================================================
# SECTION 3 & 9: METADATA LISTING AVOIDS INACTIVE PAYLOAD LOADS & IMMUTABILITY
# ==============================================================================

def test_metadata_listing_and_historical_immutability():
    """Metadata listing defers large payload; historical version data is never mutated."""
    with SessionLocal() as s:
        user = create_user(s, "meta_immut_user")
        proj = create_project(s, user, "Meta Immut Proj")
        mod = VersionService.get_or_create_module(s, proj.id, "bmc")
        v1 = VersionService.save_new_version(s, mod, {"complex": "data_v1"}, change_summary="V1")
        v2 = VersionService.save_new_version(s, mod, {"complex": "data_v2"}, change_summary="V2")
        s.commit()
        mod_id = mod.id
        v1_id = v1.id
        v2_id = v2.id

    with SessionLocal() as s:
        # Load metadata only
        meta = VersionService.get_version_metadata(s, mod_id)
        assert len(meta) == 2
        # 'data' attribute is deferred
        assert "data" not in meta[0].__dict__

        # Restore V1
        mod = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
        VersionService.restore_version(s, mod, v1_id)
        s.commit()

    with SessionLocal() as fresh_s:
        fresh_v1 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        fresh_v2 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v2_id).first()
        assert fresh_v1.data == {"complex": "data_v1"}, "V1 payload must remain immutable"
        assert fresh_v2.data == {"complex": "data_v2"}, "V2 payload must remain immutable"
