"""Correction Batch 06.4 - Mixed Local-Pending and Remote-Committed State Regression Suite.

Deterministic regression suite covering:
1. Pending assignment + remote Completed + omission (survives omission, merges attributes).
2. Pending assignment + remote dependency change.
3. Pending dependency + remote status change.
4. Pending status + remote assignment change.
5. Same-field conflict according to the chosen policy (local-intent-wins within active transaction).
6. Externally deleted row explicitly handled (expunged, not resurrected).
7. Pending new/deleted tasks correctly integrated.
8. No helper commits during freshness, canonicalization, or reconciliation.
9. Caller rollback restores original persisted state.
10. Final results inspected through fresh, independent sessions.
"""
import copy
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask
from app.services.roadmap_service import RoadmapDomainService
from app.services.task_graph_validator import get_authoritative_project_tasks
from app.core.security import hash_password


def create_user_and_project(db: Session, prefix: str = "b06_4"):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"{prefix}_{uid}",
        email=f"{prefix}_{uid}@test.com",
        hashed_password=hash_password("StrongPassword123!"),
        role="user",
        is_suspended=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    proj = Project(
        name=f"Venture_{prefix}_{uid}",
        user_id=user.id,
        stage="MVP",
        description="Mixed State and Isolation Verification"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return user, proj


def test_mixed_state_pending_assignment_remote_completed_omission():
    """
    Independent reproduction & fix:
    - Commit AI task A with status Pending.
    - Session A loads A and retains the object.
    - Session A changes assigned_to to 'Local assignment' without committing.
    - Session B changes A.status to Completed and commits.
    - Session A reconciles an empty incoming plan and commits.

    Expected: Task A is NOT deleted.
    It preserves 'Completed' status (from Session B) AND 'Local assignment' (from Session A).
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_omit")
        task_a = RoadmapTask(
            project_id=proj.id,
            task_code="AI-01",
            phase="Phase 1",
            title="AI Task",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Dev1",
            dependencies=[],
            is_ai_generated=True
        )
        init_s.add(task_a)
        init_s.commit()
        proj_id = proj.id
        task_id = task_a.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        # Session A loads A and retains the object
        proj_a = session_a.query(Project).filter(Project.id == proj_id).first()
        t_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
        assert t_a.status == "Pending"
        assert t_a.assigned_to == "Dev1"

        # Session A changes assigned_to without committing
        t_a.assigned_to = "Local assignment"
        assert session_a.is_modified(t_a) is True

        # Session B changes A.status to Completed and commits
        t_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
        t_b.status = "Completed"
        session_b.commit()

        # Session A reconciles an empty incoming plan
        reconciled = RoadmapDomainService.reconcile_roadmap_tasks(session_a, proj_a, tasks_data=[])
        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    # Final inspection from independent fresh session
    verify_s = SessionLocal()
    try:
        remaining = verify_s.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
        assert remaining is not None, "Task A must survive omission because Session B committed Completed"
        assert remaining.status == "Completed", "Remote Completed status must be authoritatively observed"
        assert remaining.assigned_to == "Local assignment", "Caller-owned pending assignment must be preserved"
    finally:
        verify_s.close()


def test_mixed_state_pending_assignment_remote_dependency_change():
    """
    - Session A changes assigned_to on T1 without committing.
    - Session B updates T1 dependencies to ['T2'] and commits.
    - Session A calls get_authoritative_project_tasks / reconciles.
    - Verify both local assigned_to and remote dependencies survive.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_dep")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-06",
            end_date="2026-11-10",
            status="Pending",
            assigned_to="Original Dev",
            dependencies=[],
            is_ai_generated=True
        )
        t2 = RoadmapTask(
            project_id=proj.id,
            task_code="T2",
            phase="Phase 1",
            title="Task 2",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        init_s.add_all([t1, t2])
        init_s.commit()
        proj_id = proj.id
        t1_id = t1.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        t1_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_a.assigned_to = "Local Dev A"

        t1_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_b.dependencies = ["T2"]
        session_b.commit()

        proj_a = session_a.query(Project).filter(Project.id == proj_id).first()
        incoming = [
            {"task_code": "T2", "phase": "P1", "title": "Task 2", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
            {"task_code": "T1", "phase": "P1", "title": "Task 1", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["T2"]}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, proj_a, tasks_data=incoming)
        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    verify_s = SessionLocal()
    try:
        final_t1 = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        assert final_t1 is not None
        assert final_t1.assigned_to == "Local Dev A", "Local assignment must be preserved"
        assert final_t1.dependencies == ["T2"], "Remote dependency change must be merged"
    finally:
        verify_s.close()


def test_mixed_state_pending_dependency_remote_status_change():
    """
    - Session A updates T2 dependencies to ['T1'] without committing.
    - Session B updates T2 status to 'In Progress' and commits.
    - Session A calls get_authoritative_project_tasks / reconciles.
    - Verify both local dependencies and remote status survive.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_stat")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        t2 = RoadmapTask(
            project_id=proj.id,
            task_code="T2",
            phase="Phase 1",
            title="Task 2",
            start_date="2026-11-06",
            end_date="2026-11-10",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        init_s.add_all([t1, t2])
        init_s.commit()
        proj_id = proj.id
        t2_id = t2.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        t2_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == t2_id).first()
        t2_a.dependencies = ["T1"]

        t2_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t2_id).first()
        t2_b.status = "In Progress"
        session_b.commit()

        proj_a = session_a.query(Project).filter(Project.id == proj_id).first()
        incoming = [
            {"task_code": "T1", "phase": "P1", "title": "Task 1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
            {"task_code": "T2", "phase": "P1", "title": "Task 2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["T1"]}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, proj_a, tasks_data=incoming)
        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    verify_s = SessionLocal()
    try:
        final_t2 = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t2_id).first()
        assert final_t2.dependencies == ["T1"], "Local dependency edit must be preserved"
        assert final_t2.status == "In Progress", "Remote status update must be observed"
    finally:
        verify_s.close()


def test_mixed_state_pending_status_remote_assignment_change():
    """
    - Session A updates T1 status to 'Ongoing' without committing.
    - Session B updates T1 assigned_to to 'Engineer Eve' and commits.
    - Session A calls get_authoritative_project_tasks / reconciles.
    - Verify both local status and remote assignment survive.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_stat_assign")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Dev Old",
            dependencies=[],
            is_ai_generated=True
        )
        init_s.add(t1)
        init_s.commit()
        proj_id = proj.id
        t1_id = t1.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        t1_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_a.status = "In Progress"

        t1_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_b.assigned_to = "Engineer Eve"
        session_b.commit()

        proj_a = session_a.query(Project).filter(Project.id == proj_id).first()
        incoming = [
            {"task_code": "T1", "phase": "P1", "title": "Task 1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, proj_a, tasks_data=incoming)
        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    verify_s = SessionLocal()
    try:
        final_t1 = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        assert final_t1.status == "In Progress", "Local status modification must be preserved"
        assert final_t1.assigned_to == "Engineer Eve", "Remote assignment modification must be observed"
    finally:
        verify_s.close()


def test_mixed_state_same_field_conflict_local_intent_wins():
    """
    Same-field conflict policy:
    - Session A changes assigned_to to 'Dev Local' (uncommitted).
    - Session B concurrently commits assigned_to = 'Dev Remote'.
    - Under the documented local-intent-wins policy, the caller's active modification within
      the current transaction takes precedence.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_conflict")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Dev Initial",
            dependencies=[],
            is_ai_generated=False
        )
        init_s.add(t1)
        init_s.commit()
        proj_id = proj.id
        t1_id = t1.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        t1_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_a.assigned_to = "Dev Local"

        t1_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t1_b.assigned_to = "Dev Remote"
        session_b.commit()

        # Session A reads authoritative state
        tasks = get_authoritative_project_tasks(session_a, proj_id)
        task_in_a = next(t for t in tasks if t.id == t1_id)
        assert task_in_a.assigned_to == "Dev Local", "Local intent must win same-field conflict"

        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    verify_s = SessionLocal()
    try:
        final_t1 = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        assert final_t1.assigned_to == "Dev Local"
    finally:
        verify_s.close()


def test_mixed_state_externally_deleted_row_not_resurrected():
    """
    - Session A loads task A and sets a local modification.
    - Session B deletes task A from the database and commits.
    - Session A calls get_authoritative_project_tasks.
    - Task A must be expunged and NOT resurrected.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_ext_del")
        task_a = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=False
        )
        init_s.add(task_a)
        init_s.commit()
        proj_id = proj.id
        task_id = task_a.id
    finally:
        init_s.close()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        t_a = session_a.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
        t_a.assigned_to = "Will not resurrect"

        t_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
        session_b.delete(t_b)
        session_b.commit()

        tasks = get_authoritative_project_tasks(session_a, proj_id)
        assert len(tasks) == 0, "Externally deleted row must not be resurrected"
    finally:
        session_a.close()
        session_b.close()


def test_mixed_state_pending_new_and_deleted_tasks():
    """
    - Pending new task in db.new is incorporated in authoritative query.
    - Pending deleted task in db.deleted is excluded.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_new_del")
        t_old = RoadmapTask(
            project_id=proj.id,
            task_code="T_OLD",
            phase="Phase 1",
            title="Old",
            start_date="2026-11-01",
            end_date="2026-11-05",
            dependencies=[],
            is_ai_generated=False
        )
        init_s.add(t_old)
        init_s.commit()
        proj_id = proj.id
    finally:
        init_s.close()

    s = SessionLocal()
    try:
        old = s.query(RoadmapTask).filter(RoadmapTask.project_id == proj_id, RoadmapTask.task_code == "T_OLD").first()
        s.delete(old)

        new_t = RoadmapTask(
            project_id=proj_id,
            task_code="T_NEW",
            phase="Phase 1",
            title="New",
            start_date="2026-11-06",
            end_date="2026-11-10",
            dependencies=[],
            is_ai_generated=False
        )
        s.add(new_t)

        tasks = get_authoritative_project_tasks(s, proj_id)
        codes = {t.task_code for t in tasks}
        assert "T_OLD" not in codes
        assert "T_NEW" in codes
    finally:
        s.close()


def test_mixed_state_no_helper_commit():
    """
    get_authoritative_project_tasks must never commit or flush unrelated session objects.
    """
    db = SessionLocal()
    try:
        user, proj = create_user_and_project(db, "mix_no_commit")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=False
        )
        db.add(t1)
        db.commit()

        # Uncommitted edit
        t1.title = "Uncommitted Edit"
        assert db.is_modified(t1) is True

        tasks = get_authoritative_project_tasks(db, proj.id)
        assert len(tasks) == 1

        # Check in a fresh session: uncommitted edit must NOT be committed to database
        verify_s = SessionLocal()
        try:
            persisted_t1 = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t1.id).first()
            assert persisted_t1.title == "Task 1", "Helper must not commit uncommitted caller edits"
        finally:
            verify_s.close()
    finally:
        db.close()


def test_mixed_state_caller_rollback_restores_persisted_state():
    """
    Caller rollback cleanly restores original persisted state after mixed-state reconciliation.
    """
    init_s = SessionLocal()
    try:
        user, proj = create_user_and_project(init_s, "mix_rollback")
        t1 = RoadmapTask(
            project_id=proj.id,
            task_code="T1",
            phase="Phase 1",
            title="Original Title",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Original Assignee",
            dependencies=[],
            is_ai_generated=True
        )
        init_s.add(t1)
        init_s.commit()
        proj_id = proj.id
        t1_id = t1.id
    finally:
        init_s.close()

    caller_s = SessionLocal()
    try:
        proj = caller_s.query(Project).filter(Project.id == proj_id).first()
        t = caller_s.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        t.assigned_to = "Caller Mod"

        incoming = [
            {"task_code": "T1", "phase": "Phase 1", "title": "Updated Title", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(caller_s, proj, incoming)

        # Caller aborts
        caller_s.rollback()
    finally:
        caller_s.close()

    verify_s = SessionLocal()
    try:
        final_t = verify_s.query(RoadmapTask).filter(RoadmapTask.id == t1_id).first()
        assert final_t.title == "Original Title"
        assert final_t.assigned_to == "Original Assignee"
    finally:
        verify_s.close()
