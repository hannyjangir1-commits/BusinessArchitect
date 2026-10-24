"""Correction Batch 06.1 - Comprehensive Regression Test Suite.

Covers:
1. Reconciliation Integrity:
   - Missing prerequisite rejected
   - Cycle rejected
   - Self-dependency rejected
   - Schedule violation rejected
   - Duplicate incoming codes rejected
   - Existing code suffix (e.g. DUP_2) avoids collision
   - Missing-code allocation avoids reserved codes
   - Whitespace normalization in snapshot and rows
   - Non-string codes return controlled validation errors
2. Preservation:
   - Omitted AI prerequisite of retained manual task rejects atomically
   - Omitted prerequisite of retained completed task is handled safely
   - Manual/generated collision does not overwrite manual work
   - Stable immutable database IDs for genuinely matching tasks
   - User execution status and assignments preserved
   - Rejected reconciliation leaves original rows unchanged
3. Integration:
   - Generation save
   - Revision save
   - Conflict replacement
   - Version restore
   - Active-version deletion fallback
   - Admin retry
   - Admin repair
4. Transaction Ownership:
   - commit=False does not commit
   - Outer rollback restores version pointer, flags, and task rows
   - Validation occurs before partial mutations persist
5. PostgreSQL Concurrency:
   - Marked pending when isolated PostgreSQL harness is unavailable
"""
import os
import concurrent.futures
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask, AIOperation, gen_id
from app.services.roadmap_service import RoadmapDomainService
from app.services.version_service import VersionService
from app.services.task_graph_validator import (
    project_first_lock,
    allocate_next_task_code,
    IncompatibleTaskGraphError
)
from app.core.security import hash_password


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def create_user_and_project(db: Session, username: str = "repro_user", email: str = "repro@test.com"):
    import uuid
    uid = uuid.uuid4().hex[:8]
    clean_username = f"{username}_{uid}"
    clean_email = f"{username}_{uid}@test.com"
    user = User(
        username=clean_username,
        email=clean_email,
        hashed_password=hash_password("StrongPassword123!"),
        role="user",
        is_suspended=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    proj = Project(
        name=f"Test Venture {uid}",
        user_id=user.id,
        stage="MVP",
        description="Testing task reconciliation"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return user, proj


def auth_client_for_user(client: TestClient, user: User) -> dict:
    resp = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "StrongPassword123!"
    })
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


# ==============================================================================
# 1. Reconciliation Integrity Tests
# ==============================================================================

def test_missing_prerequisite_rejected(db: Session):
    """Missing prerequisite is rejected before any task changes persist."""
    _, project = create_user_and_project(db, "u_missing", "missing@test.com")
    payload = [
        {"task_code": "TSK-01", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["NONEXISTENT"]}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    assert exc_info.value.status_code == 400
    assert "NONEXISTENT" in str(exc_info.value.detail)
    persisted = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(persisted) == 0


def test_cycle_rejected(db: Session):
    """Circular dependency chain (A -> B -> A) is detected and rejected."""
    _, project = create_user_and_project(db, "u_cycle", "cycle@test.com")
    payload = [
        {"task_code": "TSK-A", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["TSK-B"]},
        {"task_code": "TSK-B", "title": "B", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["TSK-A"]}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    assert exc_info.value.status_code == 400
    assert "Circular dependency" in str(exc_info.value.detail)


def test_self_dependency_rejected(db: Session):
    """Self-dependency (A -> A) is rejected."""
    _, project = create_user_and_project(db, "u_self", "self@test.com")
    payload = [
        {"task_code": "TSK-A", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["TSK-A"]}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    assert exc_info.value.status_code == 400
    assert "cannot depend on itself" in str(exc_info.value.detail)


def test_schedule_violation_rejected(db: Session):
    """Dependent starting earlier than prerequisite end date is rejected without date clamping."""
    _, project = create_user_and_project(db, "u_sched", "sched@test.com")
    payload = [
        {"task_code": "TSK-01", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-10", "dependencies": []},
        {"task_code": "TSK-02", "title": "B", "start_date": "2026-11-05", "end_date": "2026-11-15", "dependencies": ["TSK-01"]}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    assert exc_info.value.status_code == 400
    assert "Schedule conflict" in str(exc_info.value.detail)


def test_duplicate_incoming_codes_rejected(db: Session):
    """Duplicate codes in incoming plan are rejected cleanly without suffixing DUP_2."""
    _, project = create_user_and_project(db, "u_dup", "dup@test.com")
    payload = [
        {"task_code": "DUP", "title": "Step 1", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "DUP", "title": "Step 2", "start_date": "2026-11-06", "end_date": "2026-11-10"}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    assert exc_info.value.status_code == 400
    assert "Duplicate task code 'DUP'" in str(exc_info.value.detail)


def test_existing_code_suffix_does_not_cause_accidental_remapping(db: Session):
    """Existing task DUP_2 is not accidentally remapped or mutated by unrelated plan."""
    _, project = create_user_and_project(db, "u_suffix", "suffix@test.com")
    task_existing = RoadmapTask(
        project_id=project.id,
        task_code="DUP_2",
        phase="Phase 1",
        title="Custom Existing Task",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=False
    )
    db.add(task_existing)
    db.commit()

    # Reconcile incoming tasks with unassigned/missing code
    payload = [
        {"title": "Auto Task 1", "start_date": "2026-11-06", "end_date": "2026-11-10"}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    db.commit()

    # Auto code allocation allocated a non-colliding TSK-## code
    assert reconciled[0]["task_code"] == "TSK-01"
    existing = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "DUP_2").first()
    assert existing is not None
    assert existing.title == "Custom Existing Task"


def test_missing_code_allocation_avoids_all_reserved_codes(db: Session):
    """Allocating codes for tasks without task_code avoids all existing and already-assigned incoming codes."""
    _, project = create_user_and_project(db, "u_alloc", "alloc@test.com")
    task_existing = RoadmapTask(
        project_id=project.id,
        task_code="TSK-01",
        phase="Phase 1",
        title="Task 1",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=True
    )
    db.add(task_existing)
    db.commit()

    payload = [
        {"title": "Incoming without code 1", "start_date": "2026-11-06", "end_date": "2026-11-10"},
        {"title": "Incoming without code 2", "start_date": "2026-11-11", "end_date": "2026-11-15"}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    db.commit()

    codes = [t["task_code"] for t in reconciled]
    assert codes == ["TSK-02", "TSK-03"]
    assert "TSK-01" not in codes


def test_whitespace_normalization_identical_in_snapshot_and_rows(db: Session):
    """Whitespace is trimmed consistently in both the normalized dictionary and database rows."""
    _, project = create_user_and_project(db, "u_trim", "trim@test.com")
    payload = [
        {
            "task_code": "  TSK-01  ",
            "title": "First Step",
            "start_date": " 2026-11-01 ",
            "end_date": " 2026-11-05 ",
            "dependencies": []
        },
        {
            "task_code": "  TSK-02  ",
            "title": "Second Step",
            "start_date": " 2026-11-06 ",
            "end_date": " 2026-11-10 ",
            "dependencies": ["  TSK-01  "]
        }
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    db.commit()

    assert reconciled[0]["task_code"] == "TSK-01"
    assert reconciled[1]["task_code"] == "TSK-02"
    assert reconciled[1]["dependencies"] == ["TSK-01"]

    row1 = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "TSK-01").first()
    row2 = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "TSK-02").first()
    assert row1 is not None and row2 is not None
    assert row1.task_code == "TSK-01"
    assert row2.task_code == "TSK-02"
    assert row2.dependencies == ["TSK-01"]


def test_non_string_codes_return_controlled_validation_errors(db: Session):
    """Non-string task codes or dependencies raise controlled HTTPException without AttributeError."""
    _, project = create_user_and_project(db, "u_nonstr", "nonstr@test.com")

    # Integer code
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, [{"task_code": 12345, "title": "Test"}])
    assert exc_info.value.status_code == 400
    assert "Non-string task code" in str(exc_info.value.detail)

    # Non-string dependency
    with pytest.raises(HTTPException) as exc_info2:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, [{"task_code": "TSK-01", "dependencies": [123]}])
    assert exc_info2.value.status_code == 400
    assert "Non-string dependency" in str(exc_info2.value.detail)


# ==============================================================================
# 2. Preservation Tests
# ==============================================================================

def test_omitted_ai_prerequisite_of_retained_manual_task_rejects_atomically(db: Session):
    """
    Retained manual task B depends on AI task A.
    Incoming plan omits A. Reconcile must reject atomically, leaving A and B intact.
    """
    _, project = create_user_and_project(db, "u_retain_m", "retain_m@test.com")
    task_a = RoadmapTask(
        project_id=project.id,
        task_code="A",
        phase="P1",
        title="AI Prerequisite A",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=True
    )
    task_b = RoadmapTask(
        project_id=project.id,
        task_code="B",
        phase="P2",
        title="Manual Task B",
        start_date="2026-11-06",
        end_date="2026-11-10",
        status="Pending",
        dependencies=["A"],
        is_ai_generated=False
    )
    db.add(task_a)
    db.add(task_b)
    db.commit()

    incoming_plan = [
        {"task_code": "C", "title": "Task C", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_plan)

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert "retained task" in str(detail).lower() or "RETAINED_TASK_PREREQUISITE_MISSING" in str(detail)

    db.rollback()
    # Confirm both A and B are preserved
    persisted = {t.task_code: t for t in db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}
    assert "A" in persisted
    assert "B" in persisted
    assert persisted["B"].dependencies == ["A"]


def test_omitted_prerequisite_of_retained_completed_task_handled_safely(db: Session):
    """Retained completed task depending on omitted unfinished prerequisite fails validation safely."""
    _, project = create_user_and_project(db, "u_retain_c", "retain_c@test.com")
    task_a = RoadmapTask(
        project_id=project.id,
        task_code="A",
        phase="P1",
        title="Unfinished Prereq A",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=True
    )
    task_c = RoadmapTask(
        project_id=project.id,
        task_code="C",
        phase="P2",
        title="Completed Task C",
        start_date="2026-11-06",
        end_date="2026-11-10",
        status="Completed",
        dependencies=["A"],
        is_ai_generated=True
    )
    db.add(task_a)
    db.add(task_c)
    db.commit()

    # Plan omits A
    incoming_plan = [
        {"task_code": "D", "title": "Task D", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_plan)

    assert exc_info.value.status_code == 400
    db.rollback()
    persisted = {t.task_code: t for t in db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}
    assert "A" in persisted
    assert "C" in persisted


def test_manual_generated_collision_does_not_overwrite_manual_work(db: Session):
    """Incoming generated task sharing code with existing manual task raises controlled conflict."""
    _, project = create_user_and_project(db, "u_collision", "col@test.com")
    manual_task = RoadmapTask(
        project_id=project.id,
        task_code="MAN-01",
        phase="P1",
        title="Important Manual Architecture",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="In Progress",
        dependencies=[],
        is_ai_generated=False
    )
    db.add(manual_task)
    db.commit()

    incoming_plan = [
        {"task_code": "MAN-01", "title": "AI Generated Overwrite Attempt", "start_date": "2026-11-01", "end_date": "2026-11-05"}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_plan)

    assert exc_info.value.status_code == 400
    assert "conflicts with an existing manual task" in str(exc_info.value.detail)

    db.rollback()
    cur = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "MAN-01").first()
    assert cur.title == "Important Manual Architecture"
    assert cur.is_ai_generated is False


def test_ids_of_matching_existing_tasks_remain_stable(db: Session):
    """Matching tasks update in-place without altering their database primary keys."""
    _, project = create_user_and_project(db, "u_stable_id", "stable_id@test.com")
    task = RoadmapTask(
        project_id=project.id,
        task_code="STABLE-01",
        phase="P1",
        title="Original Title",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=True
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    original_id = task.id

    incoming_plan = [
        {"task_code": "STABLE-01", "title": "Updated Title", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
    ]
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_plan)
    db.commit()

    updated = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "STABLE-01").first()
    assert updated.id == original_id
    assert updated.title == "Updated Title"


def test_preserved_status_and_assignments_remain_correct(db: Session):
    """Active/finished status and custom assignments are preserved during reconciliation."""
    _, project = create_user_and_project(db, "u_preserve", "preserve@test.com")
    task = RoadmapTask(
        project_id=project.id,
        task_code="TSK-01",
        phase="P1",
        title="Execution Task",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="In Progress",
        assigned_to="Lead Engineer Alice",
        assigned_role="Architect",
        department="Engineering",
        dependencies=[],
        is_ai_generated=True
    )
    db.add(task)
    db.commit()

    incoming_plan = [
        {
            "task_code": "TSK-01",
            "title": "Execution Task Revised",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
            "status": "Pending",  # Incoming wants to reset to Pending
            "assigned_to": "Unassigned"
        }
    ]
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming_plan)
    db.commit()

    updated = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "TSK-01").first()
    assert updated.status == "In Progress"
    assert updated.assigned_to == "Lead Engineer Alice"
    assert updated.assigned_role == "Architect"
    assert updated.department == "Engineering"


# ==============================================================================
# 3. Integration Tests
# ==============================================================================

def test_conflict_replacement_with_invalid_graph_rolls_back(client: TestClient, db: Session):
    """In resolve_version_conflict, an invalid candidate graph rolls back without dropping target version."""
    user, project = create_user_and_project(db, "u_int_conflict", "int_conf@test.com")
    headers = auth_client_for_user(client, user)

    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={"tasks": [{"task_code": "V1-01", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V1"
    )
    v1_id = v1.id

    # Seed manual task depending on V1-01
    manual_t = RoadmapTask(
        project_id=project.id,
        task_code="MAN-DEP",
        phase="P2",
        title="Manual Task",
        start_date="2026-11-06",
        end_date="2026-11-10",
        status="Pending",
        dependencies=["V1-01"],
        is_ai_generated=False
    )
    db.add(manual_t)
    db.commit()

    # Attempt to replace V1 with a new plan omitting V1-01
    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/resolve-conflict",
        json={
            "replace_version_id": v1_id,
            "new_data": {
                "phases": [{"name": "P1", "description": "D1"}],
                "tasks": [{"task_code": "V2-01", "phase": "P1", "title": "T2", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
            }
        },
        headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "RETAINED_TASK_PREREQUISITE_MISSING"

    # Confirm V1 still exists and was not deleted
    db.expire_all()
    v1_check = db.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
    assert v1_check is not None
    # Confirm manual task still exists
    man_check = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.task_code == "MAN-DEP").first()
    assert man_check is not None


def test_version_restore_with_invalid_graph_rolls_back(client: TestClient, db: Session):
    """Restoring an older version whose plan conflicts with retained manual work rolls back atomically."""
    user, project = create_user_and_project(db, "u_int_restore", "int_rest@test.com")
    headers = auth_client_for_user(client, user)

    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    # V1 has only task X
    v1 = VersionService.save_new_version(
        db, module,
        data={"tasks": [{"task_code": "X", "title": "X", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V1"
    )
    # V2 has task Y
    v2 = VersionService.save_new_version(
        db, module,
        data={"tasks": [{"task_code": "Y", "title": "Y", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V2"
    )
    module.active_version_id = v2.id
    db.commit()

    # Seed manual task depending on Y (active version)
    manual_t = RoadmapTask(
        project_id=project.id,
        task_code="MAN-Y",
        phase="P2",
        title="Manual depending on Y",
        start_date="2026-11-06",
        end_date="2026-11-10",
        status="Pending",
        dependencies=["Y"],
        is_ai_generated=False
    )
    db.add(manual_t)
    db.commit()

    # Attempt to restore V1 (which omits Y)
    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/versions/{v1.id}/restore",
        headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "RETAINED_TASK_PREREQUISITE_MISSING"

    # Active pointer must still point to V2
    db.expire_all()
    mod_check = db.query(ModuleContent).filter(ModuleContent.id == module.id).first()
    assert mod_check.active_version_id == v2.id


def test_generation_save_with_invalid_graph_rolls_back(client: TestClient, db: Session):
    """In execute_module_generation, an invalid generated task graph rolls back without committing."""
    from unittest.mock import patch
    user, project = create_user_and_project(db, "u_gen_inv", "gen_inv@test.com")
    headers = auth_client_for_user(client, user)

    mock_roadmap = {
        "phases": [{"name": "P1", "description": "D1"}],
        "tasks": [
            {"task_code": "TSK-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["MISSING"]}
        ]
    }
    with patch("app.ai.gemini_service.ai_service.generate_roadmap", return_value=mock_roadmap) as mock_gen:
        resp = client.post(
            f"/api/projects/{project.id}/modules/execution_roadmap/generate",
            json={},
            headers=headers
        )
        assert mock_gen.called, "Mock provider should be invoked to exercise post-provider graph validation"
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "MISSING_PREREQUISITE"

    db.expire_all()
    # Confirm no version was saved
    module = db.query(ModuleContent).filter(ModuleContent.project_id == project.id, ModuleContent.module_type == "execution_roadmap").first()
    if module:
        versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).all()
        assert len(versions) == 0
    # Confirm no tasks persisted
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(tasks) == 0


def test_revision_modify_with_invalid_graph_rolls_back(client: TestClient, db: Session):
    """In modify_module_with_ai, an invalid modified task graph rolls back without committing."""
    from unittest.mock import patch
    user, project = create_user_and_project(db, "u_mod_inv", "mod_inv@test.com")
    headers = auth_client_for_user(client, user)

    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P1", "description": "D1"}],
            "tasks": [{"task_code": "V1-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
        },
        change_summary="V1"
    )
    v1_id = v1.id
    db.commit()

    mock_modified = {
        "phases": [{"name": "P1", "description": "D1"}],
        "tasks": [
            {"task_code": "V2-01", "phase": "P1", "title": "T2", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["MISSING_DEP"]}
        ]
    }
    with patch("app.ai.gemini_service.ai_service.modify_section", return_value=(mock_modified, "Summary")) as mock_mod:
        resp = client.post(
            f"/api/projects/{project.id}/modules/execution_roadmap/modify",
            json={"instruction": "Add invalid dependency"},
            headers=headers
        )
        assert mock_mod.called, "Mock provider should be invoked to exercise post-provider graph validation"
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "MISSING_PREREQUISITE"

    db.expire_all()
    # Confirm V1 is still the only version and active
    mod_check = db.query(ModuleContent).filter(ModuleContent.id == module.id).first()
    assert mod_check.active_version_id == v1_id
    versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).all()
    assert len(versions) == 1


def test_active_version_deletion_fallback_reconciles_roadmap(client: TestClient, db: Session):
    """Deleting an active version falls back to previous version and reconciles tasks properly."""
    user, project = create_user_and_project(db, "u_del_fallback", "del_fb@test.com")
    headers = auth_client_for_user(client, user)

    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P1", "description": "D1"}],
            "tasks": [{"task_code": "V1-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
        },
        change_summary="V1"
    )
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v1.data["tasks"])
    db.commit()

    v2 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P2", "description": "D2"}],
            "tasks": [{"task_code": "V2-01", "phase": "P2", "title": "T2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}]
        },
        change_summary="V2"
    )
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v2.data["tasks"])
    db.commit()

    # Delete V2 (currently active)
    resp = client.delete(
        f"/api/projects/{project.id}/modules/execution_roadmap/versions/{v2.id}",
        headers=headers
    )
    assert resp.status_code == 200

    db.expire_all()
    mod_check = db.query(ModuleContent).filter(ModuleContent.id == module.id).first()
    assert mod_check.active_version_id == v1.id
    # Tasks must reflect V1 (V1-01 present, V2-01 removed)
    tasks = {t.task_code: t for t in db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}
    assert "V1-01" in tasks
    assert "V2-01" not in tasks


def test_admin_repair_active_version_reconciles_roadmap(client: TestClient, db: Session):
    """Admin repair action fix_missing_active_versions repairs pointer and reconciles roadmap tasks."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    admin = User(
        username=f"admin_repair_{uid}",
        email=f"admin_rep_{uid}@test.com",
        hashed_password=hash_password("StrongPassword123!"),
        role="super_admin",
        is_suspended=False
    )
    db.add(admin)
    db.commit()
    admin_headers = auth_client_for_user(client, admin)

    user, project = create_user_and_project(db, "u_rep_user", "rep_user@test.com")
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P1", "description": "D1"}],
            "tasks": [{"task_code": "REP-01", "phase": "P1", "title": "Repair Task 1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
        },
        change_summary="V1"
    )
    db.commit()

    # Simulate broken active pointer
    module.active_version_id = None
    db.commit()

    # Execute repair
    resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "fix_missing_active_versions", "confirmation": True},
        headers=admin_headers
    )
    assert resp.status_code == 200

    db.expire_all()
    mod_check = db.query(ModuleContent).filter(ModuleContent.id == module.id).first()
    assert mod_check.active_version_id == v1.id

    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(tasks) == 1
    assert tasks[0].task_code == "REP-01"


def test_admin_retry_reconciles_roadmap_under_project_lock(client: TestClient, db: Session):
    """Admin retry on failed AI operation persists version and tasks atomically under project lock."""
    import uuid
    from unittest.mock import patch
    uid = uuid.uuid4().hex[:8]
    admin = User(
        username=f"admin_retry_{uid}",
        email=f"admin_ret_{uid}@test.com",
        hashed_password=hash_password("StrongPassword123!"),
        role="super_admin",
        is_suspended=False
    )
    db.add(admin)
    db.commit()
    admin_headers = auth_client_for_user(client, admin)

    user, project = create_user_and_project(db, "u_retry_user", "retry_user@test.com")

    # Failed AIOperation record
    failed_op = AIOperation(
        id=gen_id("aio_"),
        request_id="req_fail_123",
        user_id=user.id,
        project_id=project.id,
        module_type="execution_roadmap",
        operation_type="generate",
        model_name="test-model",
        duration_ms=1000,
        status="failed",
        error_category="provider_error",
        error_message="Simulated upstream failure",
        is_retryable=True,
        retry_count=0
    )
    db.add(failed_op)
    db.commit()

    mock_roadmap = {
        "phases": [{"name": "P1", "description": "D1"}],
        "tasks": [{"task_code": "RETRY-01", "phase": "P1", "title": "Recovered Task", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
    }
    with patch("app.ai.gemini_service.ai_service.generate_roadmap", return_value=mock_roadmap):
        resp = client.post(
            f"/api/admin/ai-operations/{failed_op.id}/retry",
            headers=admin_headers
        )
    assert resp.status_code == 200

    db.expire_all()
    # Confirm version was saved and tasks reconciled
    module = db.query(ModuleContent).filter(ModuleContent.project_id == project.id, ModuleContent.module_type == "execution_roadmap").first()
    assert module is not None
    assert module.active_version_id is not None
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(tasks) == 1
    assert tasks[0].task_code == "RETRY-01"


# ==============================================================================
# 4. Transaction Ownership Tests
# ==============================================================================

def test_commit_false_reconciliation_does_not_commit(db: Session):
    """Calling reconcile_roadmap_tasks flushes but does not commit."""
    _, project = create_user_and_project(db, "u_commit_false", "cf@test.com")
    payload = [
        {"task_code": "TSK-01", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
    ]
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)
    # Staged in session, but not committed yet.
    # Calling rollback must discard it completely.
    db.rollback()

    persisted = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(persisted) == 0


def test_outer_rollback_restores_version_pointer_flags_and_task_rows(db: Session):
    """Outer rollback in a failed transaction restores module version pointer and task rows."""
    _, project = create_user_and_project(db, "u_outer_rb", "outer_rb@test.com")
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    v1 = VersionService.save_new_version(
        db, module,
        data={"tasks": [{"task_code": "ORIG-01", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V1"
    )
    v1_id = v1.id
    db.commit()

    try:
        with project_first_lock(db, project.id, module.id):
            v2 = VersionService.save_new_version(
                db, module,
                data={"tasks": [{"task_code": "V2-01", "title": "T2", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                commit=False
            )
            # Reconcile an invalid graph (missing prereq)
            invalid_tasks = [{"task_code": "V2-01", "title": "T2", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": ["MISSING"]}]
            RoadmapDomainService.reconcile_roadmap_tasks(db, project, invalid_tasks)
            db.commit()
    except HTTPException:
        db.rollback()

    # Active pointer must still be v1
    db.expire_all()
    m_check = db.query(ModuleContent).filter(ModuleContent.id == module.id).first()
    assert m_check.active_version_id == v1_id
    # Only v1 exists
    versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id).all()
    assert len(versions) == 1
    assert versions[0].id == v1_id


def test_validation_happens_before_partial_task_mutations_are_flushed(db: Session):
    """If candidate graph has invalid dependencies midway through, none of the tasks are persisted."""
    _, project = create_user_and_project(db, "u_midway", "midway@test.com")
    payload = [
        {"task_code": "VALID-01", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
        {"task_code": "VALID-02", "title": "T2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["VALID-01"]},
        {"task_code": "INVALID-03", "title": "T3", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["DOES_NOT_EXIST"]}
    ]
    with pytest.raises(HTTPException):
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, payload)

    db.rollback()
    persisted = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(persisted) == 0


# ==============================================================================
# 5. PostgreSQL Concurrency Tests (Isolated Disposable Harness)
# ==============================================================================

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _run_pg_concurrency_test(test_fn):
    """
    Bootstrap an isolated, disposable PostgreSQL schema for concurrency testing.
    Never prints or leaks credentials. Uses bounded timeouts and reliable teardown.
    """
    from urllib.parse import urlparse
    import uuid
    import threading
    from sqlalchemy import create_engine, text, event
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base

    schema_name = f"conc_{uuid.uuid4().hex[:8]}"
    bootstrap_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True
    )
    with bootstrap_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c search_path={schema_name}"
        },
        pool_pre_ping=True
    )

    @event.listens_for(test_engine, "connect")
    def set_search_path(dbapi_conn, conn_record):
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema_name}"')

    Base.metadata.create_all(bind=test_engine)
    PGSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    try:
        test_fn(PGSessionLocal, schema_name)
    finally:
        test_engine.dispose()
        try:
            with bootstrap_engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            bootstrap_engine.dispose()
        except Exception:
            pass


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_manual_mutation_vs_roadmap_restore():
    """
    Worker A holds project lock on project P in transaction 1 and mutates manual task.
    Worker B attempts roadmap restore on P in transaction 2.
    Proves Worker B blocks until Worker A commits, then restores while preserving manual work.
    """
    import threading
    import time

    def run(PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_mut_rest")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            v1 = VersionService.save_new_version(
                init_s, mod,
                data={"tasks": [{"task_code": "V1-01", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary="V1"
            )
            v1_id = v1.id
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id

        worker_a_holding = threading.Event()
        worker_a_release = threading.Event()
        worker_b_finished = threading.Event()
        worker_errors = []

        def worker_a():
            try:
                with PGSessionLocal() as s_a:
                    with project_first_lock(s_a, proj_id, mod_id):
                        task = RoadmapTask(
                            project_id=proj_id,
                            task_code="MAN-LOCK",
                            phase="P1",
                            title="Manual While Locked",
                            start_date="2026-11-01",
                            end_date="2026-11-05",
                            status="Pending",
                            dependencies=[],
                            is_ai_generated=False
                        )
                        s_a.add(task)
                        s_a.flush()
                        worker_a_holding.set()
                        if not worker_a_release.wait(timeout=5):
                            raise TimeoutError("Worker A wait timed out")
                        s_a.commit()
            except Exception as e:
                worker_errors.append(f"Worker A: {e}")

        def worker_b():
            try:
                if not worker_a_holding.wait(timeout=5):
                    raise TimeoutError("Worker B wait for A timed out")
                with PGSessionLocal() as s_b:
                    mod_b = s_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
                    with project_first_lock(s_b, proj_id, mod_id):
                        VersionService.restore_version(s_b, mod_b, v1_id, commit=False)
                        tasks_data = [{"task_code": "V1-01", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
                        RoadmapDomainService.reconcile_roadmap_tasks(s_b, mod_b.project, tasks_data)
                        s_b.commit()
                        worker_b_finished.set()
            except Exception as e:
                worker_errors.append(f"Worker B: {e}")

        t_a = threading.Thread(target=worker_a)
        t_b = threading.Thread(target=worker_b)
        t_a.start()
        t_b.start()

        assert worker_a_holding.wait(timeout=5)
        # Worker B must NOT finish while Worker A holds lock
        time.sleep(0.3)
        assert not worker_b_finished.is_set(), "Worker B must be blocked by Worker A's project lock"

        # Release Worker A
        worker_a_release.set()
        t_a.join(timeout=5)
        t_b.join(timeout=5)

        assert not worker_errors, f"Thread errors: {worker_errors}"
        assert worker_b_finished.is_set()

        with PGSessionLocal() as final_s:
            tasks = {t.task_code: t for t in final_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()}
            assert "MAN-LOCK" in tasks, "Manual task created under lock must survive restore"
            assert "V1-01" in tasks

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_manual_mutation_vs_generation_persistence():
    """
    Manual task creation serializes with concurrent roadmap generation persistence
    under PostgreSQL row locks, preventing phantom code collisions.
    """
    import threading
    import time

    def run(PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_mut_gen")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id

        a_locked = threading.Event()
        a_release = threading.Event()
        b_done = threading.Event()
        errors = []

        def worker_a():
            try:
                with PGSessionLocal() as s_a:
                    with project_first_lock(s_a, proj_id, mod_id):
                        t = RoadmapTask(
                            project_id=proj_id,
                            task_code="TSK-01",
                            phase="P1",
                            title="Manual 1",
                            start_date="2026-11-01",
                            end_date="2026-11-05",
                            status="Pending",
                            dependencies=[],
                            is_ai_generated=False
                        )
                        s_a.add(t)
                        s_a.flush()
                        a_locked.set()
                        if not a_release.wait(timeout=5):
                            raise TimeoutError("A timed out")
                        s_a.commit()
            except Exception as e:
                errors.append(f"Worker A: {e}")

        def worker_b():
            try:
                if not a_locked.wait(timeout=5):
                    raise TimeoutError("B wait timed out")
                with PGSessionLocal() as s_b:
                    mod_b = s_b.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
                    with project_first_lock(s_b, proj_id, mod_id):
                        # Generation persistence allocates next code avoiding TSK-01
                        payload = [{"title": "Generated 1", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}]
                        reconciled = RoadmapDomainService.reconcile_roadmap_tasks(s_b, mod_b.project, payload)
                        VersionService.save_new_version(
                            s_b, mod_b,
                            data={"tasks": reconciled},
                            change_summary="Gen 1",
                            commit=False
                        )
                        s_b.commit()
                        b_done.set()
            except Exception as e:
                errors.append(f"Worker B: {e}")

        t_a = threading.Thread(target=worker_a)
        t_b = threading.Thread(target=worker_b)
        t_a.start()
        t_b.start()

        assert a_locked.wait(timeout=5)
        time.sleep(0.3)
        assert not b_done.is_set(), "Generation persistence must wait for manual transaction to commit"

        a_release.set()
        t_a.join(timeout=5)
        t_b.join(timeout=5)

        assert not errors, f"Errors: {errors}"
        assert b_done.is_set()

        with PGSessionLocal() as final_s:
            tasks = {t.task_code: t for t in final_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()}
            assert "TSK-01" in tasks
            assert "TSK-02" in tasks, "Generated task must receive next available code without colliding with TSK-01"

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_restore_vs_repair_same_roadmap():
    """
    Concurrent restore and repair targeting the same roadmap serialize cleanly
    under PostgreSQL row locks without leaving broken pointers or dangling tasks.
    """
    import threading

    def run(PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_rest_rep")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            v1 = VersionService.save_new_version(
                init_s, mod,
                data={"tasks": [{"task_code": "V1", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary="V1"
            )
            v2 = VersionService.save_new_version(
                init_s, mod,
                data={"tasks": [{"task_code": "V2", "title": "V2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}]},
                change_summary="V2"
            )
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id
            v1_id = v1.id

        errors = []

        def worker_restore():
            try:
                with PGSessionLocal() as s:
                    m = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
                    with project_first_lock(s, proj_id, mod_id):
                        VersionService.restore_version(s, m, v1_id, commit=False)
                        RoadmapDomainService.reconcile_roadmap_tasks(s, m.project, m.active_version.data.get("tasks", []))
                        s.commit()
            except Exception as e:
                errors.append(f"Restore error: {e}")

        def worker_repair():
            try:
                with PGSessionLocal() as s:
                    m = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
                    with project_first_lock(s, proj_id, mod_id):
                        VersionService.repair_active_version_for_module(s, m)
                        s.commit()
            except Exception as e:
                errors.append(f"Repair error: {e}")

        t1 = threading.Thread(target=worker_restore)
        t2 = threading.Thread(target=worker_repair)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Errors: {errors}"

        with PGSessionLocal() as final_s:
            m = final_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            assert m.active_version_id is not None
            active_v = final_s.query(ModuleVersion).filter(ModuleVersion.id == m.active_version_id).first()
            assert active_v.is_active is True

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_independent_projects_progress_separately():
    """
    Independent projects proceed separately: holding lock on Project 1 does not block
    task mutations or generation on Project 2.
    """
    import threading
    import time

    def run(PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            u1, p1 = create_user_and_project(init_s, "pg_indep_p1")
            u2, p2 = create_user_and_project(init_s, "pg_indep_p2")
            init_s.commit()
            p1_id = p1.id
            p2_id = p2.id

        p1_holding = threading.Event()
        p1_release = threading.Event()
        p2_done = threading.Event()
        errors = []

        def worker_p1():
            try:
                with PGSessionLocal() as s1:
                    with project_first_lock(s1, p1_id):
                        p1_holding.set()
                        if not p1_release.wait(timeout=5):
                            raise TimeoutError("P1 timed out")
                        s1.commit()
            except Exception as e:
                errors.append(f"P1: {e}")

        def worker_p2():
            try:
                if not p1_holding.wait(timeout=5):
                    raise TimeoutError("P2 wait timed out")
                with PGSessionLocal() as s2:
                    # While P1 is locked, P2 must complete immediately without waiting
                    with project_first_lock(s2, p2_id):
                        t = RoadmapTask(
                            project_id=p2_id,
                            task_code="P2-TASK",
                            phase="P1",
                            title="P2 Task",
                            start_date="2026-11-01",
                            end_date="2026-11-05",
                            status="Pending",
                            dependencies=[],
                            is_ai_generated=True
                        )
                        s2.add(t)
                        s2.commit()
                        p2_done.set()
            except Exception as e:
                errors.append(f"P2: {e}")

        t1 = threading.Thread(target=worker_p1)
        t2 = threading.Thread(target=worker_p2)
        t1.start()
        t2.start()

        assert p1_holding.wait(timeout=5)
        # P2 must finish while P1 is STILL holding its lock!
        assert p2_done.wait(timeout=3), "Project 2 operation must complete without waiting for Project 1 lock"

        p1_release.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Errors: {errors}"
        with PGSessionLocal() as final_s:
            p2_task = final_s.query(RoadmapTask).filter(RoadmapTask.project_id == p2_id, RoadmapTask.task_code == "P2-TASK").first()
            assert p2_task is not None

    _run_pg_concurrency_test(run)
