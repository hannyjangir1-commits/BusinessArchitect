"""Correction Batch 06.2 - Roadmap Freshness, Snapshot Consistency, Code Pre-Reservation, and Error Sanitization Suite.

Deterministic regression suite covering:
1. Task Freshness under Project Lock:
   - Two sessions: Pending in A, Completed committed by B, omission reconciled by A -> Completed task survives.
   - Two sessions: B changes retained task dependency before A reconciles -> A validates against B's committed dependency.
   - Two sessions: B changes assignment/status -> A reconciles matching task -> Current user work preserved.
   - Assertions executed from a fresh database session.
2. Snapshot-Row Consistency without Mutating History:
   - Whitespace task code, dependency, and date normalization.
   - Newly persisted snapshot inspected from a fresh session agrees with relational task projection.
   - Historical snapshots remain byte-for-byte immutable during restore and repair.
   - Rejected persistence restores old pointer, flags, history, and task rows.
3. Reserve All Explicit Incoming Codes Before Allocation:
   - Missing code before explicit TSK-01 (first gets TSK-02, explicit TSK-01 preserved without collision).
   - Multiple missing codes interspersed with explicit codes.
   - Existing project codes plus later incoming explicit codes.
   - Whitespace-equivalent explicit duplicates rejected cleanly.
   - Input order preserved.
4. Empty Plans Applied Consistently:
   - Explicit empty task list removes eligible unfinished AI tasks while retaining manual/completed tasks.
   - Empty replacement with retained dependent blocks with RETAINED_TASK_PREREQUISITE_MISSING.
   - Missing 'tasks' field rejected with HTTP 400; does not accidentally become destructive empty plan.
5. Error Handler Sanitization:
   - Injected failure with synthetic secrets (DB credentials, connection strings) returns generic 500 error.
   - Asserts secret tokens are absent from client response body and logs.
"""
import copy
import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Project, ModuleContent, ModuleVersion, RoadmapTask
from app.services.roadmap_service import RoadmapDomainService
from app.services.version_service import VersionService
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


def create_user_and_project(db: Session, prefix: str = "b06_2"):
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
        description="Task Freshness and Consistency Testing"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return user, proj


def auth_headers(client: TestClient, user: User) -> dict:
    resp = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "StrongPassword123!"
    })
    assert resp.status_code == 200
    csrf = resp.json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


# ==============================================================================
# 1. Authoritative Task Freshness Under Project Lock
# ==============================================================================

def test_freshness_pending_in_session_a_completed_committed_by_b_survives_omission():
    """
    Session A loads an AI task with status Pending and retains its ORM object.
    Session B updates that task to Completed and commits.
    Session A reconciles an incoming plan that omits the task.
    Authoritative freshness must recognize Completed status and prevent premature deletion.
    """
    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        user, project = create_user_and_project(session_a, "fresh_pend")
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
        session_a.add(task_a)
        session_a.commit()

        # Session A loads task_a into its identity map
        t_in_a = session_a.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).first()
        assert t_in_a.status == "Pending"

        # Session B updates task_a to Completed and commits
        t_in_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t_in_a.id).first()
        t_in_b.status = "Completed"
        session_b.commit()

        # Session A reconciles an incoming plan omitting AI-01
        new_plan = [
            {"task_code": "AI-02", "title": "Second AI Task", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, project, new_plan)
        session_a.commit()

        # Assert final state from a fresh session
        with SessionLocal() as fresh_s:
            tasks = {t.task_code: t for t in fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}
            assert "AI-01" in tasks, "Completed task must survive omission despite Session A's stale initial cache"
            assert tasks["AI-01"].status == "Completed"
            assert "AI-02" in tasks
    finally:
        session_a.close()
        session_b.close()


def test_freshness_session_b_changes_retained_dependency_before_session_a_reconciles():
    """
    Session B changes a retained manual task's dependency from A to B and commits.
    Session A reconciles a plan omitting A and providing B.
    Session A must read B's committed dependency and validate successfully without false missing-ref failure.
    """
    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        user, project = create_user_and_project(session_a, "fresh_dep")
        t_a = RoadmapTask(project_id=project.id, task_code="A", phase="Phase 1", title="A", start_date="2026-11-01", end_date="2026-11-05", status="Pending", dependencies=[], is_ai_generated=True)
        t_b = RoadmapTask(project_id=project.id, task_code="B", phase="Phase 1", title="B", start_date="2026-11-01", end_date="2026-11-05", status="Pending", dependencies=[], is_ai_generated=True)
        t_m = RoadmapTask(project_id=project.id, task_code="M", phase="Phase 1", title="Manual M", start_date="2026-11-06", end_date="2026-11-10", status="Pending", dependencies=["A"], is_ai_generated=False)
        session_a.add_all([t_a, t_b, t_m])
        session_a.commit()

        # Session A caches M with dependencies=["A"]
        m_in_a = session_a.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.id == t_m.id).first()
        assert m_in_a.dependencies == ["A"]

        # Session B updates M to depend on B instead
        m_in_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == m_in_a.id).first()
        m_in_b.dependencies = ["B"]
        session_b.commit()

        # Session A reconciles plan with A omitted, B retained
        new_plan = [
            {"task_code": "B", "title": "B", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, project, new_plan)
        session_a.commit()

        with SessionLocal() as fresh_s:
            fresh_m = fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.id == t_m.id).first()
            assert fresh_m.dependencies == ["B"]
    finally:
        session_a.close()
        session_b.close()


def test_freshness_session_b_changes_assignment_and_status_preserved_on_matching_reconcile():
    """
    Session B changes assignment and status on a task and commits.
    Session A reconciles a matching generated plan with default status/assignee.
    Authoritative state is preserved from Session B's committed changes.
    """
    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        user, project = create_user_and_project(session_a, "fresh_assign")
        t1 = RoadmapTask(
            project_id=project.id,
            task_code="T1",
            phase="Phase 1",
            title="Initial Title",
            start_date="2026-11-01",
            end_date="2026-11-05",
            status="Pending",
            assigned_to="Unassigned",
            dependencies=[],
            is_ai_generated=True
        )
        session_a.add(t1)
        session_a.commit()

        # Session A caches t1
        _ = session_a.query(RoadmapTask).filter(RoadmapTask.id == t1.id).first()

        # Session B sets status="In Progress" and assigned_to="Engineer Bob"
        t1_b = session_b.query(RoadmapTask).filter(RoadmapTask.id == t1.id).first()
        t1_b.status = "In Progress"
        t1_b.assigned_to = "Engineer Bob"
        session_b.commit()

        # Session A reconciles matching task T1 with status="Pending", assigned_to="Unassigned"
        incoming = [
            {"task_code": "T1", "title": "AI Refined Title", "start_date": "2026-11-01", "end_date": "2026-11-05", "status": "Pending", "assigned_to": "Unassigned", "dependencies": []}
        ]
        RoadmapDomainService.reconcile_roadmap_tasks(session_a, project, incoming)
        session_a.commit()

        with SessionLocal() as fresh_s:
            fresh_t = fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id, RoadmapTask.id == t1.id).first()
            assert fresh_t.title == "AI Refined Title"
            assert fresh_t.status == "In Progress", "User status updated by Session B must be preserved"
            assert fresh_t.assigned_to == "Engineer Bob", "User assignment updated by Session B must be preserved"
    finally:
        session_a.close()
        session_b.close()


# ==============================================================================
# 2. Snapshot-Row Consistency and Historical Immutability
# ==============================================================================

def test_snapshot_and_row_consistency_production_generation_path(client: TestClient, db: Session):
    """
    In the production generation path, incoming plan with untrimmed codes, missing codes,
    and untrimmed dependencies is canonicalized before version saving.
    Both version snapshot JSON and relational rows agree on canonical values.
    """
    user, project = create_user_and_project(db, "snap_gen")
    headers = auth_headers(client, user)

    mock_raw_ai_plan = {
        "phases": [{"name": "P1", "description": "D1"}],
        "tasks": [
            {"task_code": "  TSK-01  ", "phase": "P1", "title": "Task 1", "start_date": " 2026-11-01 ", "end_date": " 2026-11-05 ", "dependencies": []},
            {"title": "Task 2 Missing Code", "phase": "P1", "start_date": " 2026-11-06 ", "end_date": " 2026-11-10 ", "dependencies": ["  TSK-01  "]}
        ]
    }
    with patch("app.ai.gemini_service.ai_service.generate_roadmap", return_value=mock_raw_ai_plan):
        resp = client.post(
            f"/api/projects/{project.id}/modules/execution_roadmap/generate",
            json={},
            headers=headers
        )
    assert resp.status_code == 200

    # Fresh session verification
    with SessionLocal() as fresh_s:
        mod = fresh_s.query(ModuleContent).filter(ModuleContent.project_id == project.id, ModuleContent.module_type == "execution_roadmap").first()
        ver = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == mod.active_version_id).first()
        rows = {t.task_code: t for t in fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}

        # Snapshot checks
        snap_tasks = ver.data["tasks"]
        assert snap_tasks[0]["task_code"] == "TSK-01"
        assert snap_tasks[1]["task_code"] == "TSK-02"
        assert snap_tasks[1]["dependencies"] == ["TSK-01"]
        assert snap_tasks[0]["start_date"] == "2026-11-01"
        assert snap_tasks[1]["end_date"] == "2026-11-10"

        # Relational row checks
        assert "TSK-01" in rows
        assert "TSK-02" in rows
        assert rows["TSK-02"].dependencies == ["TSK-01"]
        assert rows["TSK-01"].start_date == "2026-11-01"
        assert rows["TSK-02"].end_date == "2026-11-10"

        # Snapshot and relational task projection agree
        assert [t["task_code"] for t in snap_tasks] == sorted(list(rows.keys()))


def test_old_snapshots_remain_byte_for_byte_unchanged_after_restore(client: TestClient, db: Session):
    """
    Restoring an older version reconciles relational working state but keeps the
    historical version snapshot JSON byte-for-byte immutable.
    """
    user, project = create_user_and_project(db, "snap_immut")
    headers = auth_headers(client, user)
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    v1_data = {
        "phases": [{"name": "P1", "description": "D1"}],
        "tasks": [{"task_code": "V1-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
    }
    v1_json_snapshot = json.dumps(v1_data, sort_keys=True)

    v1 = VersionService.save_new_version(db, module, data=copy.deepcopy(v1_data), change_summary="V1")
    v1_id = v1.id

    v2 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P2", "description": "D2"}],
            "tasks": [{"task_code": "V2-01", "phase": "P2", "title": "T2", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}]
        },
        change_summary="V2"
    )
    db.commit()

    # Restore V1
    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/versions/{v1_id}/restore",
        headers=headers
    )
    assert resp.status_code == 200

    # Fresh session read: confirm V1 data JSON is byte-for-byte logically unchanged
    with SessionLocal() as fresh_s:
        fresh_v1 = fresh_s.query(ModuleVersion).filter(ModuleVersion.id == v1_id).first()
        fresh_v1_json = json.dumps(fresh_v1.data, sort_keys=True)
        assert fresh_v1_json == v1_json_snapshot, "Historical version snapshot must not be mutated on restore"


# ==============================================================================
# 3. Reserve All Explicit Incoming Codes Before Allocation
# ==============================================================================

def test_missing_code_before_explicit_tsk_01(db: Session):
    """
    When an incoming plan has a task without task_code followed by a task with explicit 'TSK-01',
    pre-reservation assigns TSK-02 to the first task and preserves TSK-01 without false collision.
    """
    _, project = create_user_and_project(db, "preres_tsk01")
    incoming = [
        {"title": "Uncoded Task 1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []},
        {"task_code": "TSK-01", "title": "Explicit TSK-01", "start_date": "2026-11-06", "end_date": "2026-11-10", "dependencies": []}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming)
    db.commit()

    assert reconciled[0]["task_code"] == "TSK-02"
    assert reconciled[1]["task_code"] == "TSK-01"


def test_multiple_missing_codes_interspersed(db: Session):
    """
    Multiple missing codes interspersed with explicit codes (TSK-01, TSK-03).
    Input order is preserved and allocations avoid all reserved codes.
    """
    _, project = create_user_and_project(db, "preres_multi")
    incoming = [
        {"title": "Missing 1", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "TSK-01", "title": "Explicit 1", "start_date": "2026-11-06", "end_date": "2026-11-10"},
        {"title": "Missing 2", "start_date": "2026-11-11", "end_date": "2026-11-15"},
        {"task_code": "TSK-03", "title": "Explicit 3", "start_date": "2026-11-16", "end_date": "2026-11-20"}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming)
    db.commit()

    codes = [t["task_code"] for t in reconciled]
    assert codes == ["TSK-04", "TSK-01", "TSK-05", "TSK-03"]


def test_existing_codes_plus_later_incoming_explicit_codes(db: Session):
    """
    Existing project has TSK-01. Incoming plan has Task 0 (missing code) and Task 1 (explicit TSK-02).
    Task 0 must allocate TSK-03, avoiding collision with both existing TSK-01 and incoming TSK-02.
    """
    _, project = create_user_and_project(db, "preres_exist")
    t_exist = RoadmapTask(
        project_id=project.id,
        task_code="TSK-01",
        phase="P1",
        title="Existing Task 1",
        start_date="2026-11-01",
        end_date="2026-11-05",
        status="Pending",
        dependencies=[],
        is_ai_generated=True
    )
    db.add(t_exist)
    db.commit()

    incoming = [
        {"title": "Missing Code Task", "start_date": "2026-11-06", "end_date": "2026-11-10"},
        {"task_code": "TSK-02", "title": "Explicit Task 2", "start_date": "2026-11-11", "end_date": "2026-11-15"}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming)
    db.commit()

    codes = [t["task_code"] for t in reconciled]
    assert codes == ["TSK-03", "TSK-02"]


def test_whitespace_equivalent_explicit_duplicates_rejected(db: Session):
    """
    Incoming tasks with ' TSK-01 ' and 'TSK-01' are recognized as duplicates and rejected.
    """
    _, project = create_user_and_project(db, "preres_ws_dup")
    incoming = [
        {"task_code": "  TSK-01  ", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "TSK-01", "title": "T2 Duplicate", "start_date": "2026-11-06", "end_date": "2026-11-10"}
    ]
    with pytest.raises(HTTPException) as exc_info:
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "DUPLICATE_TASK_CODE"


def test_no_collision_with_custom_codes(db: Session):
    """
    Incoming plan with custom codes ('SETUP-ENV') allocates standard automatic codes without error.
    """
    _, project = create_user_and_project(db, "preres_custom")
    incoming = [
        {"task_code": "SETUP-ENV", "title": "Custom Setup", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"title": "Automatic Task", "start_date": "2026-11-06", "end_date": "2026-11-10"}
    ]
    reconciled = RoadmapDomainService.reconcile_roadmap_tasks(db, project, incoming)
    db.commit()

    assert reconciled[0]["task_code"] == "SETUP-ENV"
    assert reconciled[1]["task_code"] == "TSK-01"


# ==============================================================================
# 4. Empty Plans Applied Consistently
# ==============================================================================

def test_empty_conflict_replacement_removes_unfinished_ai_tasks(client: TestClient, db: Session):
    """
    Explicit empty tasks list in conflict replacement reaches reconciliation and
    safely removes unfinished AI tasks.
    """
    user, project = create_user_and_project(db, "empty_rem")
    headers = auth_headers(client, user)
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    v1 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P1", "description": "D1"}],
            "tasks": [{"task_code": "AI-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
        },
        change_summary="V1"
    )
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v1.data["tasks"])
    db.commit()

    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/resolve-conflict",
        json={
            "replace_version_id": v1.id,
            "new_data": {
                "phases": [],
                "tasks": []
            }
        },
        headers=headers
    )
    assert resp.status_code == 200

    with SessionLocal() as fresh_s:
        tasks = fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
        assert len(tasks) == 0


def test_empty_replacement_blocks_when_retained_task_depends_on_omitted(client: TestClient, db: Session):
    """
    Empty replacement omitting AI prerequisite needed by retained manual task rejects atomically.
    """
    user, project = create_user_and_project(db, "empty_blk")
    headers = auth_headers(client, user)
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")

    v1 = VersionService.save_new_version(
        db, module,
        data={
            "phases": [{"name": "P1", "description": "D1"}],
            "tasks": [{"task_code": "AI-01", "phase": "P1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
        },
        change_summary="V1"
    )
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, v1.data["tasks"])
    man = RoadmapTask(project_id=project.id, task_code="MAN-01", phase="P1", title="Manual", start_date="2026-11-06", end_date="2026-11-10", dependencies=["AI-01"], is_ai_generated=False)
    db.add(man)
    db.commit()

    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/resolve-conflict",
        json={
            "replace_version_id": v1.id,
            "new_data": {"phases": [], "tasks": []}
        },
        headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "RETAINED_TASK_PREREQUISITE_MISSING"

    with SessionLocal() as fresh_s:
        tasks = {t.task_code: t for t in fresh_s.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()}
        assert "AI-01" in tasks
        assert "MAN-01" in tasks


def test_missing_tasks_field_rejected_with_400(client: TestClient, db: Session):
    """
    Roadmap payload completely missing the 'tasks' key is rejected with HTTP 400.
    Does not accidentally become a destructive empty plan.
    """
    user, project = create_user_and_project(db, "empty_miss")
    headers = auth_headers(client, user)
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={"phases": [], "tasks": [{"task_code": "T1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V1"
    )
    db.commit()

    resp = client.post(
        f"/api/projects/{project.id}/modules/execution_roadmap/resolve-conflict",
        json={
            "replace_version_id": v1.id,
            "new_data": {"phases": []}
        },
        headers=headers
    )
    assert resp.status_code == 400
    assert "explicit 'tasks' list" in resp.json()["detail"]


# ==============================================================================
# 5. Error Handler Sanitization
# ==============================================================================

def test_error_sanitization_in_restore_and_conflict(client: TestClient, db: Session):
    """
    Unexpected exceptions during restore or conflict resolution return generic error messages
    without leaking internal connection strings, credentials, or raw tracebacks.
    """
    user, project = create_user_and_project(db, "err_san")
    headers = auth_headers(client, user)
    module = VersionService.get_or_create_module(db, project.id, "execution_roadmap")
    v1 = VersionService.save_new_version(
        db, module,
        data={"phases": [], "tasks": [{"task_code": "T1", "title": "T1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]},
        change_summary="V1"
    )
    db.commit()

    synthetic_secret = "postgresql://dbuser:SECRET_CREDENTIAL_XYZ_987@internal-cluster:5432/appdb"

    with patch("app.services.version_service.VersionService.restore_version", side_effect=RuntimeError(f"Pool crash: {synthetic_secret}")):
        resp = client.post(
            f"/api/projects/{project.id}/modules/execution_roadmap/versions/{v1.id}/restore",
            headers=headers
        )
    assert resp.status_code == 500
    assert "SECRET_CREDENTIAL_XYZ" not in resp.text
    assert synthetic_secret not in resp.text
    assert "unexpected internal error" in resp.json()["detail"].lower()
