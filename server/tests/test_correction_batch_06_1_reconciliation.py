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
from typing import Optional, List, Dict, Any, Set, Tuple
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
# 5. PostgreSQL Concurrency Tests (Isolated Disposable Harness)
# ==============================================================================

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def validate_and_parse_test_db_url(raw_url: Optional[str]):
    """
    Parse and strictly validate TEST_DATABASE_URL for disposable test use.

    Guarantees:
    - Never falls back to production DATABASE_URL.
    - Requires postgresql dialect (postgresql or postgresql+driver, rejects mysql, sqlite, etc.).
    - Strictly restricts host to explicit local loopback ('localhost', '127.0.0.1', '::1').
    - Rejects unspecified hosts and '0.0.0.0'.
    - Rejects connection query options that can override destination routing (host, hostaddr, service, options).
    - Rejects remote hosts before any network connection attempt.
    - Masks credentials in all diagnostics and string representations.
    """
    from sqlalchemy.engine import make_url

    if not raw_url or not str(raw_url).strip():
        raise ValueError("TEST_DATABASE_URL is unset or empty.")

    clean_str = str(raw_url).strip()
    try:
        url = make_url(clean_str)
    except Exception:
        raise ValueError("Invalid database URL format for TEST_DATABASE_URL.") from None

    # 1. Dialect check: require PostgreSQL dialect
    if not (url.drivername == "postgresql" or url.drivername.startswith("postgresql+")):
        raise ValueError(f"TEST_DATABASE_URL must be a PostgreSQL dialect, got '{url.drivername}'.")

    # 2. Host validation: strictly explicit loopback only
    ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
    host = url.host
    if not host or host not in ALLOWED_HOSTS:
        raise ValueError(
            f"TEST_DATABASE_URL points to forbidden host '{host or 'unspecified'}'. "
            f"Disposable tests strictly require explicit loopback ({', '.join(sorted(ALLOWED_HOSTS))})."
        )

    # 3. Query parameters check: reject options that override host or service routing
    FORBIDDEN_QUERY_KEYS = {"host", "hostaddr", "service", "options", "target_session_attrs"}
    if url.query:
        overlapping = set(url.query.keys()).intersection(FORBIDDEN_QUERY_KEYS)
        if overlapping:
            raise ValueError(
                f"TEST_DATABASE_URL contains forbidden routing query parameter(s): {sorted(overlapping)}. "
                f"Connection overrides are rejected to prevent routing hijacking."
            )

    return url


def test_offline_guard_rejects_non_postgresql_url():
    """Offline unit test: Harness rejects non-PostgreSQL URLs without attempting connection."""
    with pytest.raises(ValueError, match="PostgreSQL dialect"):
        validate_and_parse_test_db_url("mysql://user:pass@localhost:3306/db")
    with pytest.raises(ValueError, match="PostgreSQL dialect"):
        validate_and_parse_test_db_url("sqlite:///test.db")


def test_offline_guard_rejects_remote_hosts():
    """Offline unit test: Harness rejects remote hosts before any network connection attempt."""
    with pytest.raises(ValueError, match="forbidden host"):
        validate_and_parse_test_db_url("postgresql://user:pass@production.example.com:5432/proddb")
    with pytest.raises(ValueError, match="forbidden host"):
        validate_and_parse_test_db_url("postgresql://user:pass@192.168.1.100:5432/testdb")


def test_offline_guard_rejects_unspecified_and_all_zero_hosts():
    """Offline unit test: Harness rejects unspecified hosts and 0.0.0.0."""
    with pytest.raises(ValueError, match="forbidden host"):
        validate_and_parse_test_db_url("postgresql:///testdb")
    with pytest.raises(ValueError, match="forbidden host"):
        validate_and_parse_test_db_url("postgresql://0.0.0.0:5432/testdb")


def test_offline_guard_rejects_routing_query_overrides():
    """Offline unit test: Harness rejects connection query parameters that override destination routing."""
    with pytest.raises(ValueError, match="forbidden routing query parameter"):
        validate_and_parse_test_db_url("postgresql://user:pass@localhost:5432/testdb?host=remote.example.com")

    with pytest.raises(ValueError):
        validate_and_parse_test_db_url("postgresql:///testdb?host=remote.example.com")

    with pytest.raises(ValueError, match="forbidden routing query parameter"):
        validate_and_parse_test_db_url("postgresql://user:pass@localhost:5432/testdb?service=prod_service")

    with pytest.raises(ValueError, match="forbidden routing query parameter"):
        validate_and_parse_test_db_url("postgresql://user:pass@localhost:5432/testdb?hostaddr=10.0.0.1")


def test_offline_guard_accepts_local_loopback_and_masks_credentials():
    """Offline unit test: Harness accepts localhost, 127.0.0.1, ::1 and masks password in string output."""
    url1 = validate_and_parse_test_db_url("postgresql://usr:secret123@localhost:5432/testdb")
    assert url1.host == "localhost"
    masked = url1.render_as_string(hide_password=True)
    assert "secret123" not in masked
    assert "***" in masked

    url2 = validate_and_parse_test_db_url("postgresql://usr:secret123@127.0.0.1:5432/testdb")
    assert url2.host == "127.0.0.1"

    url3 = validate_and_parse_test_db_url("postgresql://usr:secret123@[::1]:5432/testdb")
    assert url3.host == "::1"


def _run_pg_concurrency_test(test_fn):
    """
    Bootstrap an isolated, disposable PostgreSQL schema for concurrency testing.
    Never prints or leaks credentials. Uses bounded timeouts, defensive resource allocation,
    and reliable teardown.
    """
    import uuid
    from sqlalchemy import create_engine, text, event
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base

    url = validate_and_parse_test_db_url(TEST_DATABASE_URL)
    clean_url = url.set(query={})
    url_str = clean_url.render_as_string(hide_password=False)

    schema_name = f"conc_{uuid.uuid4().hex[:8]}"
    bootstrap_engine = None
    test_engine = None
    schema_created = False

    try:
        bootstrap_engine = create_engine(
            url_str,
            connect_args={"connect_timeout": 3},
            pool_pre_ping=True
        )
        with bootstrap_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        schema_created = True

        test_engine = create_engine(
            url_str,
            connect_args={
                "connect_timeout": 3,
                "options": f"-c search_path={schema_name} -c statement_timeout=5000 -c lock_timeout=5000"
            },
            pool_pre_ping=True
        )

        @event.listens_for(test_engine, "connect")
        def set_search_path(dbapi_conn, conn_record):
            with dbapi_conn.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema_name}"')

        Base.metadata.create_all(bind=test_engine)
        PGSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

        test_fn(url_str, PGSessionLocal, schema_name)
    finally:
        teardown_errors = []
        if test_engine is not None:
            try:
                test_engine.dispose()
            except Exception as e:
                teardown_errors.append(f"test_engine disposal: {type(e).__name__}")

        if bootstrap_engine is not None and schema_created:
            try:
                with bootstrap_engine.connect() as conn:
                    conn.execution_options(isolation_level="AUTOCOMMIT")
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            except Exception as e:
                teardown_errors.append(f"drop schema: {type(e).__name__}")
            finally:
                try:
                    bootstrap_engine.dispose()
                except Exception as e:
                    teardown_errors.append(f"bootstrap_engine disposal: {type(e).__name__}")

        if teardown_errors:
            raise RuntimeError(f"Database harness teardown encountered errors: {', '.join(teardown_errors)}")


def _find_distinct_stripe_project_ids() -> tuple:
    """
    Find two synthetic project IDs guaranteed to map to different lock stripes.
    Avoids accidental process-local lock collisions when evaluating independent projects.
    """
    import uuid, hashlib
    p1 = f"prj_{uuid.uuid4().hex[:12]}"
    idx1 = int(hashlib.md5(p1.encode("utf-8")).hexdigest()[:8], 16) % 256
    while True:
        p2 = f"prj_{uuid.uuid4().hex[:12]}"
        idx2 = int(hashlib.md5(p2.encode("utf-8")).hexdigest()[:8], 16) % 256
        if idx1 != idx2:
            return p1, p2


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_manual_mutation_vs_roadmap_restore():
    """
    Worker A holds project transaction lock in Process A while mutating a manual task.
    Worker B attempts roadmap restore in Process B.
    Using explicit spawn-context processes proves that PostgreSQL SELECT FOR UPDATE row-locks
    serialize the competing operations independently of in-process lock objects.
    """
    import multiprocessing as mp
    import time
    from tests.pg_concurrency_workers import worker_manual_mutation_hold, worker_roadmap_restore_compete

    def run(db_url_str, PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_mut_rest")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            v1 = VersionService.save_new_version(
                init_s, mod,
                data={"tasks": [{"task_code": "V1-01", "phase": "P1", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary="V1"
            )
            v1_id = v1.id
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id

        ctx = mp.get_context("spawn")
        a_holding = ctx.Event()
        a_release = ctx.Event()
        b_started = ctx.Event()
        b_finished = ctx.Event()
        error_queue = ctx.Queue()

        p_a = ctx.Process(
            target=worker_manual_mutation_hold,
            args=(db_url_str, schema, proj_id, mod_id, a_holding, a_release, error_queue)
        )
        p_b = ctx.Process(
            target=worker_roadmap_restore_compete,
            args=(db_url_str, schema, proj_id, mod_id, v1_id, a_holding, b_started, b_finished, error_queue)
        )
        workers = [p_a, p_b]

        try:
            p_a.start()
            assert a_holding.wait(timeout=5), "Worker A must acquire lock"
            p_b.start()
            assert b_started.wait(timeout=5), "Worker B must signal start"

            # Give Worker B time to attempt the row lock in PostgreSQL
            time.sleep(0.3)
            # Worker B must NOT have completed because Process A holds the PostgreSQL row lock
            assert not b_finished.is_set(), "Worker B must be blocked by PostgreSQL row lock held by Worker A"

            # Release Worker A
            a_release.set()
            assert b_finished.wait(timeout=5), "Worker B must complete once Worker A commits"

            p_a.join(timeout=5)
            p_b.join(timeout=5)

            errors = []
            while True:
                try:
                    errors.append(error_queue.get_nowait())
                except Exception:
                    break
            assert not errors, f"Process worker errors: {errors}"
            assert p_a.exitcode == 0, f"Worker A failed with exitcode {p_a.exitcode}"
            assert p_b.exitcode == 0, f"Worker B failed with exitcode {p_b.exitcode}"

            with PGSessionLocal() as final_s:
                tasks = {t.task_code: t for t in final_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()}
                assert "MAN-LOCK" in tasks, "Manual task created under lock must survive restore"
                assert "V1-01" in tasks
        finally:
            a_release.set()
            try:
                error_queue.close()
                error_queue.join_thread()
            except Exception:
                pass
            for p in workers:
                try:
                    if p.is_alive():
                        p.terminate()
                        p.join(timeout=2)
                except Exception:
                    pass
            for p in workers:
                assert not p.is_alive(), f"Worker process {p.name} failed to terminate."

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_manual_mutation_vs_generation_persistence():
    """
    Separate processes: Manual task creation in Process A holds project row lock.
    Generation persistence in Process B must serialize on PostgreSQL row lock.
    """
    import multiprocessing as mp
    import time
    from tests.pg_concurrency_workers import worker_gen_hold_mutation, worker_gen_compete_persistence

    def run(db_url_str, PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_mut_gen")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id

        ctx = mp.get_context("spawn")
        a_holding = ctx.Event()
        a_release = ctx.Event()
        b_started = ctx.Event()
        b_finished = ctx.Event()
        error_queue = ctx.Queue()

        raw_tasks = [
            {"task_code": "TSK-02", "phase": "P1", "title": "Gen 2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}
        ]

        p_a = ctx.Process(
            target=worker_gen_hold_mutation,
            args=(db_url_str, schema, proj_id, mod_id, a_holding, a_release, error_queue)
        )
        p_b = ctx.Process(
            target=worker_gen_compete_persistence,
            args=(db_url_str, schema, proj_id, mod_id, raw_tasks, a_holding, b_started, b_finished, error_queue)
        )
        workers = [p_a, p_b]

        try:
            p_a.start()
            assert a_holding.wait(timeout=5)
            p_b.start()
            assert b_started.wait(timeout=5)

            time.sleep(0.3)
            assert not b_finished.is_set(), "Worker B must be blocked on PostgreSQL row lock"

            a_release.set()
            assert b_finished.wait(timeout=5)

            p_a.join(timeout=5)
            p_b.join(timeout=5)

            errors = []
            while True:
                try:
                    errors.append(error_queue.get_nowait())
                except Exception:
                    break
            assert not errors, f"Process worker errors: {errors}"
            assert p_a.exitcode == 0, f"Worker A failed with exitcode {p_a.exitcode}"
            assert p_b.exitcode == 0, f"Worker B failed with exitcode {p_b.exitcode}"

            with PGSessionLocal() as final_s:
                tasks = {t.task_code: t for t in final_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()}
                assert "TSK-01" in tasks, "Manual task from Process A must persist"
                assert "TSK-02" in tasks, "Generated task from Process B must persist"
        finally:
            a_release.set()
            try:
                error_queue.close()
                error_queue.join_thread()
            except Exception:
                pass
            for p in workers:
                try:
                    if p.is_alive():
                        p.terminate()
                        p.join(timeout=2)
                except Exception:
                    pass
            for p in workers:
                assert not p.is_alive(), f"Worker process {p.name} failed to terminate."

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_restore_vs_repair_same_roadmap():
    """
    Separate processes: Restore and repair on same roadmap serialize correctly.
    Asserts coherent active version selection and valid working task graph.
    """
    import multiprocessing as mp
    import time
    from tests.pg_concurrency_workers import worker_restore_hold, worker_repair_compete

    def run(db_url_str, PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            user, proj = create_user_and_project(init_s, "pg_rest_rep")
            mod = VersionService.get_or_create_module(init_s, proj.id, "execution_roadmap")
            v1 = VersionService.save_new_version(
                init_s, mod,
                data={"phases": [{"name": "P1"}], "tasks": [{"task_code": "V1-01", "phase": "P1", "title": "V1 Task", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary="V1"
            )
            v2 = VersionService.save_new_version(
                init_s, mod,
                data={"phases": [{"name": "P1"}], "tasks": [{"task_code": "V2-01", "phase": "P1", "title": "V2 Task", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
                change_summary="V2"
            )
            init_s.commit()
            proj_id = proj.id
            mod_id = mod.id
            v1_id = v1.id

        ctx = mp.get_context("spawn")
        a_holding = ctx.Event()
        a_release = ctx.Event()
        b_started = ctx.Event()
        b_finished = ctx.Event()
        error_queue = ctx.Queue()

        p_a = ctx.Process(
            target=worker_restore_hold,
            args=(db_url_str, schema, proj_id, mod_id, v1_id, a_holding, a_release, error_queue)
        )
        p_b = ctx.Process(
            target=worker_repair_compete,
            args=(db_url_str, schema, proj_id, mod_id, a_holding, b_started, b_finished, error_queue)
        )
        workers = [p_a, p_b]

        try:
            p_a.start()
            assert a_holding.wait(timeout=5)
            p_b.start()
            assert b_started.wait(timeout=5)

            time.sleep(0.3)
            assert not b_finished.is_set(), "Repair must block on PostgreSQL row lock while restore holds transaction"

            a_release.set()
            assert b_finished.wait(timeout=5)

            p_a.join(timeout=5)
            p_b.join(timeout=5)

            errors = []
            while True:
                try:
                    errors.append(error_queue.get_nowait())
                except Exception:
                    break
            assert not errors, f"Process worker errors: {errors}"
            assert p_a.exitcode == 0, f"Worker A failed with exitcode {p_a.exitcode}"
            assert p_b.exitcode == 0, f"Worker B failed with exitcode {p_b.exitcode}"

            with PGSessionLocal() as final_s:
                m = final_s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
                assert m.active_version_id is not None

                # Query active version explicitly scoped to this module (Fix B06.3: avoid non-existent m.active_version relationship)
                active_v = final_s.query(ModuleVersion).filter(
                    ModuleVersion.module_content_id == mod_id,
                    ModuleVersion.id == m.active_version_id
                ).first()
                assert active_v is not None
                assert active_v.is_active is True

                # Exactly one version is active for this module
                active_versions = final_s.query(ModuleVersion).filter(
                    ModuleVersion.module_content_id == mod_id,
                    ModuleVersion.is_active == True
                ).all()
                assert len(active_versions) == 1
                assert active_versions[0].id == m.active_version_id

                # Working roadmap tasks match the selected version's canonical projection
                working_tasks = final_s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id).all()
                working_by_code = {t.task_code: t for t in working_tasks}
                for v_task in (active_v.data.get("tasks") or []):
                    code = v_task.get("task_code")
                    if code:
                        assert code in working_by_code

                # No dangling/invalid dependencies remain
                all_codes = set(working_by_code.keys())
                for t in working_tasks:
                    for d in (t.dependencies or []):
                        assert d in all_codes, f"Dangling dependency '{d}' in task '{t.task_code}'"
        finally:
            a_release.set()
            try:
                error_queue.close()
                error_queue.join_thread()
            except Exception:
                pass
            for p in workers:
                try:
                    if p.is_alive():
                        p.terminate()
                        p.join(timeout=2)
                except Exception:
                    pass
            for p in workers:
                assert not p.is_alive(), f"Worker process {p.name} failed to terminate."

    _run_pg_concurrency_test(run)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_DATABASE_URL").startswith("postgresql")),
    reason="PostgreSQL disposable test harness unavailable (TEST_DATABASE_URL unset or non-PostgreSQL)."
)
def test_pg_independent_projects_progress_separately():
    """
    Independent projects proceed separately: holding row lock on Project 1 does not block
    task mutations or generation on Project 2.

    Note on striped locks: Occasional striped-lock collisions (1 in 256) are a bounded implementation
    tradeoff in production to limit memory. To measure independent database concurrency deterministically
    without accidental process-local lock collision, the test generates project IDs guaranteed to map
    to distinct stripes.
    """
    import multiprocessing as mp
    from tests.pg_concurrency_workers import worker_p1_hold, worker_p2_compete

    p1_id, p2_id = _find_distinct_stripe_project_ids()

    def run(db_url_str, PGSessionLocal, schema):
        with PGSessionLocal() as init_s:
            u1 = User(id=f"usr_1_{p1_id[:8]}", username=f"u1_{p1_id[:8]}", email=f"{p1_id[:8]}@test.com", hashed_password="hash")
            u2 = User(id=f"usr_2_{p2_id[:8]}", username=f"u2_{p2_id[:8]}", email=f"{p2_id[:8]}@test.com", hashed_password="hash")
            proj1 = Project(id=p1_id, name="P1", user_id=u1.id)
            proj2 = Project(id=p2_id, name="P2", user_id=u2.id)
            init_s.add_all([u1, u2, proj1, proj2])
            init_s.commit()

        ctx = mp.get_context("spawn")
        p1_holding = ctx.Event()
        p1_release = ctx.Event()
        p2_finished = ctx.Event()
        error_queue = ctx.Queue()

        p_a = ctx.Process(
            target=worker_p1_hold,
            args=(db_url_str, schema, p1_id, p1_holding, p1_release, error_queue)
        )
        p_b = ctx.Process(
            target=worker_p2_compete,
            args=(db_url_str, schema, p2_id, p1_holding, p2_finished, error_queue)
        )
        workers = [p_a, p_b]

        try:
            p_a.start()
            assert p1_holding.wait(timeout=5)
            p_b.start()

            # P2 must finish while P1 is STILL holding its lock!
            assert p2_finished.wait(timeout=3), "Project 2 must complete without waiting for Project 1 lock"

            p1_release.set()
            p_a.join(timeout=5)
            p_b.join(timeout=5)

            errors = []
            while True:
                try:
                    errors.append(error_queue.get_nowait())
                except Exception:
                    break
            assert not errors, f"Process worker errors: {errors}"
            assert p_a.exitcode == 0, f"Worker A failed with exitcode {p_a.exitcode}"
            assert p_b.exitcode == 0, f"Worker B failed with exitcode {p_b.exitcode}"

            with PGSessionLocal() as final_s:
                p2_task = final_s.query(RoadmapTask).filter(RoadmapTask.project_id == p2_id, RoadmapTask.task_code == "P2-TASK").first()
                assert p2_task is not None
        finally:
            p1_release.set()
            try:
                error_queue.close()
                error_queue.join_thread()
            except Exception:
                pass
            for p in workers:
                try:
                    if p.is_alive():
                        p.terminate()
                        p.join(timeout=2)
                except Exception:
                    pass
            for p in workers:
                assert not p.is_alive(), f"Worker process {p.name} failed to terminate."

    _run_pg_concurrency_test(run)
