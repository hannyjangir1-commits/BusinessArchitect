"""Correction Batch 06.3 - Pending Task State Preservation and Concurrency Verification Suite.

Comprehensive regression tests covering:
A. Pending Completed status followed by omission survives deletion.
B. Pending assignment change followed by matching reconciliation preserves caller work.
C. Pending dependency change followed by graph validation detects cycles without losing pending state.
D. Pending new task in session (db.new) and deleted task (db.deleted) handled correctly.
E. Another session's committed Completed status survives omission in caller session.
F. Another session's committed assignment and dependency changes are authoritatively observed.
G. No helper commit inside canonicalization or reconciliation.
H. Caller rollback restores original persisted state.

All persisted state is inspected using independent fresh sessions.
"""
import copy
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask
from app.services.roadmap_service import RoadmapDomainService
from app.services.task_graph_validator import (
    get_authoritative_project_tasks,
    allocate_next_task_code,
    validate_candidate_task_graph,
    TaskGraphNode
)
from app.api.tasks import _build_and_validate_candidate_graph
from app.core.security import hash_password
from fastapi import HTTPException


def create_user_and_project(db: Session, prefix: str = "b06_3"):
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
        description="Pending State and Concurrency Verification"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return user, proj


# ==============================================================================
# Test A: Pending Completed status followed by omission
# ==============================================================================

def test_a_pending_completed_status_survives_omission():
    """
    Independent reproduction & fix:
    - Create and commit an AI task A with status Pending.
    - Load A into caller session.
    - Set A.status = "Completed" without committing (db.is_modified(A) is True).
    - Call reconcile_roadmap_tasks(db, project, []).
    - Commit.
    - Inspect from fresh session: Task A must NOT be deleted and must have status "Completed".
    """
    init_db = SessionLocal()
    try:
        user, project = create_user_and_project(init_db, "test_a")
        task_a = RoadmapTask(
            project_id=project.id,
            task_code="AI-01",
            phase="Phase 1",
            title="Initial AI Task",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        init_db.add(task_a)
        init_db.commit()
        project_id = project.id
    finally:
        init_db.close()

    caller_session = SessionLocal()
    try:
        proj = caller_session.query(Project).filter(Project.id == project_id).first()
        t = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "AI-01").first()
        assert t is not None
        assert t.status == "Pending"

        # Modify status in memory without committing
        t.status = "Completed"
        assert caller_session.is_modified(t) is True

        # Reconcile an incoming plan that omits AI-01
        RoadmapDomainService.reconcile_roadmap_tasks(
            db=caller_session,
            project=proj,
            tasks_data=[]
        )

        # In caller session, t must not be marked deleted
        assert t not in caller_session.deleted
        assert t.status == "Completed"

        # Caller commits the transaction
        caller_session.commit()
    finally:
        caller_session.close()

    # Verify persisted state from an independent fresh session
    verify_session = SessionLocal()
    try:
        tasks = verify_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id).all()
        assert len(tasks) == 1, "Task A must survive omission because it was marked Completed"
        assert tasks[0].task_code == "AI-01"
        assert tasks[0].status == "Completed"
    finally:
        verify_session.close()


# ==============================================================================
# Test B: Pending assignment change followed by matching reconciliation
# ==============================================================================

def test_b_pending_assignment_preserved_during_matching_reconciliation():
    """
    - Create and commit task with assigned_to = "User1".
    - Load into caller session, modify assigned_to = "User2" (uncommitted).
    - Call reconcile_roadmap_tasks with incoming task AI-01 (e.g. without assignment or different title).
    - Confirm caller-owned pending assignment "User2" is preserved and not overwritten.
    - Commit and verify from fresh session.
    """
    init_db = SessionLocal()
    try:
        user, project = create_user_and_project(init_db, "test_b")
        task_a = RoadmapTask(
            project_id=project.id,
            task_code="AI-01",
            phase="Phase 1",
            title="Title Old",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="In Progress",
            assigned_to="User1",
            dependencies=[],
            is_ai_generated=True
        )
        init_db.add(task_a)
        init_db.commit()
        project_id = project.id
    finally:
        init_db.close()

    caller_session = SessionLocal()
    try:
        proj = caller_session.query(Project).filter(Project.id == project_id).first()
        t = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "AI-01").first()
        assert t.assigned_to == "User1"

        # Uncommitted caller edit
        t.assigned_to = "User2"
        assert caller_session.is_modified(t) is True

        # Reconcile matching incoming plan
        incoming = [{
            "task_code": "AI-01",
            "phase": "Phase 1",
            "title": "Title Updated by Plan",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
            "dependencies": []
        }]
        RoadmapDomainService.reconcile_roadmap_tasks(caller_session, proj, tasks_data=incoming)

        # In caller session, t.assigned_to must still be "User2"
        assert t.assigned_to == "User2", "Caller's pending assigned_to must not be lost"
        assert t.title == "Title Updated by Plan"

        caller_session.commit()
    finally:
        caller_session.close()

    verify_session = SessionLocal()
    try:
        t_final = verify_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "AI-01").first()
        assert t_final is not None
        assert t_final.assigned_to == "User2"
        assert t_final.title == "Title Updated by Plan"
    finally:
        verify_session.close()


# ==============================================================================
# Test C: Pending dependency change followed by graph validation
# ==============================================================================

def test_c_pending_dependency_change_detected_during_graph_validation():
    """
    - Two tasks T1 and T2 exist in DB with empty dependencies.
    - Caller session modifies T1.dependencies = ["T2"] without committing.
    - Caller now attempts to validate candidate graph or update T2 to depend on T1.
    - Cycle T1 -> T2 -> T1 must be detected because T1's pending dependencies are preserved.
    - Verify that pending changes on T1 were not wiped during validation.
    """
    init_db = SessionLocal()
    try:
        user, project = create_user_and_project(init_db, "test_c")
        t1 = RoadmapTask(
            project_id=project.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            dependencies=[],
            is_ai_generated=False
        )
        t2 = RoadmapTask(
            project_id=project.id,
            task_code="T2",
            phase="Phase 1",
            title="Task 2",
            start_date="2026-11-06",
            end_date="2026-11-10",
            dependencies=[],
            is_ai_generated=False
        )
        init_db.add_all([t1, t2])
        init_db.commit()
        project_id = project.id
    finally:
        init_db.close()

    caller_session = SessionLocal()
    try:
        t1_in_mem = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T1").first()
        t2_in_mem = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T2").first()

        # Caller makes pending uncommitted modification on T1
        t1_in_mem.dependencies = ["T2"]
        assert caller_session.is_modified(t1_in_mem) is True

        # Now test get_authoritative_project_tasks
        auth_tasks = get_authoritative_project_tasks(caller_session, project_id)
        auth_by_code = {t.task_code: t for t in auth_tasks}
        assert auth_by_code["T1"].dependencies == ["T2"], "Authoritative tasks must include pending dependencies"

        # Now validate candidate graph for T2 depending on T1
        with pytest.raises(HTTPException) as exc_info:
            _build_and_validate_candidate_graph(
                db=caller_session,
                project_id=project_id,
                target_task_id=t2_in_mem.id,
                candidate_task_code="T2",
                candidate_start_date="2026-11-06",
                candidate_end_date="2026-11-10",
                candidate_dependencies=["T1"]
            )
        assert exc_info.value.status_code == 400
        assert "Circular dependency detected" in exc_info.value.detail

        # Verify t1_in_mem still retains its pending modification and was not overwritten
        assert t1_in_mem.dependencies == ["T2"]
        assert caller_session.is_modified(t1_in_mem) is True
    finally:
        caller_session.close()


# ==============================================================================
# Test D: Pending deletion / new task state handled cleanly
# ==============================================================================

def test_d_pending_new_and_deleted_tasks_in_authoritative_read():
    """
    - In caller session:
      * Add a new task T_NEW to session (uncommitted, in db.new).
      * Mark an existing task T_OLD for deletion via db.delete (uncommitted, in db.deleted).
    - Authoritative task reader must:
      * Include T_NEW.
      * Exclude T_OLD.
    - Code allocator allocate_next_task_code must recognize T_NEW's code and avoid collisions.
    """
    init_db = SessionLocal()
    try:
        user, project = create_user_and_project(init_db, "test_d")
        t_old = RoadmapTask(
            project_id=project.id,
            task_code="TSK-01",
            phase="Phase 1",
            title="Old Task",
            start_date="2026-11-01",
            end_date="2026-11-05",
            dependencies=[],
            is_ai_generated=False
        )
        init_db.add(t_old)
        init_db.commit()
        project_id = project.id
    finally:
        init_db.close()

    caller_session = SessionLocal()
    try:
        old_task = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "TSK-01").first()
        caller_session.delete(old_task)
        assert old_task in caller_session.deleted

        new_task = RoadmapTask(
            project_id=project_id,
            task_code="TSK-02",
            phase="Phase 1",
            title="New Uncommitted Task",
            start_date="2026-11-06",
            end_date="2026-11-10",
            dependencies=[],
            is_ai_generated=False
        )
        caller_session.add(new_task)
        assert new_task in caller_session.new

        auth_tasks = get_authoritative_project_tasks(caller_session, project_id)
        codes = {t.task_code for t in auth_tasks}

        assert "TSK-01" not in codes, "Deleted task must be excluded from authoritative tasks"
        assert "TSK-02" in codes, "New uncommitted task must be included in authoritative tasks"

        # Code allocation must reserve TSK-02
        next_code = allocate_next_task_code(caller_session, project_id, reserved_codes={"TSK-03"})
        # Since TSK-02 is in db.new, next available code should not collide with TSK-02
        assert next_code not in {"TSK-02", "TSK-03"}
    finally:
        caller_session.close()


# ==============================================================================
# Test E: Another session's committed Completed status survives omission
# ==============================================================================

def test_e_concurrent_session_committed_completed_status_survives():
    """
    - Session A loads AI-01 (status="Pending") into identity map.
    - Session B updates AI-01 to "Completed" and commits.
    - Session A (where AI-01 is unmodified) reconciles an incoming plan omitting AI-01.
    - Session A's authoritative refresh must expire the unmodified AI-01 instance,
      load Session B's committed "Completed" status, and retain AI-01.
    """
    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        user, project = create_user_and_project(session_a, "test_e")
        task = RoadmapTask(
            project_id=project.id,
            task_code="AI-01",
            phase="Phase 1",
            title="AI Task",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        session_a.add(task)
        session_a.commit()
        project_id = project.id

        # Session A loads task into memory
        t_a = session_a.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "AI-01").first()
        assert t_a.status == "Pending"
        assert session_a.is_modified(t_a) is False

        # Session B updates to Completed and commits
        t_b = session_b.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "AI-01").first()
        t_b.status = "Completed"
        session_b.commit()

        # Session A reconciles empty plan
        proj_a = session_a.query(Project).filter(Project.id == project_id).first()
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, proj_a, tasks_data=[])
        session_a.commit()
    finally:
        session_a.close()
        session_b.close()

    verify_session = SessionLocal()
    try:
        final_tasks = verify_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id).all()
        assert len(final_tasks) == 1
        assert final_tasks[0].task_code == "AI-01"
        assert final_tasks[0].status == "Completed"
    finally:
        verify_session.close()


# ==============================================================================
# Test F: Another session's committed assignment/dependency changes observed
# ==============================================================================

def test_f_concurrent_session_committed_assignment_and_deps_observed():
    """
    - Session A loads tasks T1 and T2 into memory.
    - Session B updates T1.assigned_to = "Dev_B" and T2.dependencies = ["T1"] and commits.
    - Session A calls get_authoritative_project_tasks.
    - Session A sees the fresh committed assignment "Dev_B" and dependency ["T1"].
    """
    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        user, project = create_user_and_project(session_a, "test_f")
        t1 = RoadmapTask(
            project_id=project.id,
            task_code="T1",
            phase="Phase 1",
            title="Task 1",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Dev_A",
            dependencies=[],
            is_ai_generated=False
        )
        t2 = RoadmapTask(
            project_id=project.id,
            task_code="T2",
            phase="Phase 1",
            title="Task 2",
            start_date="2026-11-06",
            end_date="2026-11-10",
            status="Pending",
            assigned_to=None,
            dependencies=[],
            is_ai_generated=False
        )
        session_a.add_all([t1, t2])
        session_a.commit()
        project_id = project.id

        # Session A loads both
        t1_a = session_a.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T1").first()
        t2_a = session_a.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T2").first()
        assert t1_a.assigned_to == "Dev_A"
        assert t2_a.dependencies == []

        # Session B updates and commits
        t1_b = session_b.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T1").first()
        t2_b = session_b.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T2").first()
        t1_b.assigned_to = "Dev_B"
        t2_b.dependencies = ["T1"]
        session_b.commit()

        # Session A calls authoritative query
        auth_tasks = get_authoritative_project_tasks(session_a, project_id)
        auth_map = {t.task_code: t for t in auth_tasks}

        assert auth_map["T1"].assigned_to == "Dev_B", "Session A must observe Session B's committed assignment"
        assert auth_map["T2"].dependencies == ["T1"], "Session A must observe Session B's committed dependency"
    finally:
        session_a.close()
        session_b.close()


# ==============================================================================
# Test G: No helper commit inside canonicalization or reconciliation
# ==============================================================================

def test_g_no_helper_commit_during_canonicalization_or_reconciliation():
    """
    - Calling canonicalize_incoming_tasks or reconcile_roadmap_tasks must NOT commit.
    - Transaction remains uncommitted until the caller decides to commit.
    """
    db = SessionLocal()
    try:
        user, project = create_user_and_project(db, "test_g")
        raw_plan = [
            {"task_code": "", "phase": "Phase 1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
        ]
        # Canonicalize
        canonical = RoadmapDomainService.canonicalize_incoming_tasks(db, project, raw_plan)
        assert len(canonical) == 1
        assert canonical[0]["task_code"] == "TSK-01"

        # Reconcile
        reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, canonical)
        assert len(reconciled) == 1

        # Check transaction state: not committed!
        # If we open another session, the new task must NOT be visible yet!
        other_session = SessionLocal()
        try:
            tasks_in_other = other_session.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
            assert len(tasks_in_other) == 0, "No helper commit: other session must not see uncommitted reconciled tasks"
        finally:
            other_session.close()

        # Caller commits
        db.commit()

        # Now other session sees it
        verify_session = SessionLocal()
        try:
            tasks_verified = verify_session.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
            assert len(tasks_verified) == 1
        finally:
            verify_session.close()
    finally:
        db.close()


# ==============================================================================
# Test H: Caller rollback restores original persisted state
# ==============================================================================

def test_h_caller_rollback_restores_original_persisted_state():
    """
    - Persist an initial task T1.
    - Caller modifies T1 in memory (status="Completed").
    - Caller calls reconcile_roadmap_tasks to add T2.
    - Caller encounters a problem or decides to rollback.
    - Caller rolls back session.
    - Inspect from fresh session: original persisted state is completely restored (T1 is Pending, T2 does not exist).
    """
    init_db = SessionLocal()
    try:
        user, project = create_user_and_project(init_db, "test_h")
        t1 = RoadmapTask(
            project_id=project.id,
            task_code="T1",
            phase="Phase 1",
            title="Initial Task",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            dependencies=[],
            is_ai_generated=True
        )
        init_db.add(t1)
        init_db.commit()
        project_id = project.id
    finally:
        init_db.close()

    caller_session = SessionLocal()
    try:
        proj = caller_session.query(Project).filter(Project.id == project_id).first()
        t1_in_mem = caller_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id, RoadmapTask.task_code == "T1").first()
        t1_in_mem.status = "Completed"

        incoming = [
            {"task_code": "T1", "phase": "Phase 1", "title": "Initial Task", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
            {"task_code": "T2", "phase": "Phase 1", "title": "Second Task", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": ["T1"]}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(caller_session, proj, incoming)

        # Explicit caller rollback
        caller_session.rollback()
    finally:
        caller_session.close()

    verify_session = SessionLocal()
    try:
        tasks = verify_session.query(RoadmapTask).filter(RoadmapTask.project_id == project_id).all()
        assert len(tasks) == 1, "Only initial task T1 should exist after rollback"
        assert tasks[0].task_code == "T1"
        assert tasks[0].status == "Pending", "Original status Pending must be restored after rollback"
    finally:
        verify_session.close()
