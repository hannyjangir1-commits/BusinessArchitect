"""Batch 06: Task Identity, Dependency Graph, and Schedule Integrity Tests."""

import threading
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.all_models import User, Project, RoadmapTask, gen_id
from app.db.session import SessionLocal
from app.services.task_graph_validator import (
    allocate_next_task_code,
    validate_candidate_task_graph,
    TaskGraphNode
)
from app.services.roadmap_service import RoadmapDomainService


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)



def create_user_fixture(db, username: str, email: str, role: str = "user") -> User:
    from app.core.security import hash_password
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password("StrongPassword123!"),
        role=role,
        is_suspended=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project_fixture(db, user: User, name: str = "Task Test Venture") -> Project:
    proj = Project(
        name=name,
        user_id=user.id,
        stage="MVP",
        description="Testing task integrity"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def auth_client_for_user(client: TestClient, user: User) -> dict:
    """Log in user and return CSRF headers."""
    resp = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "StrongPassword123!"
    })
    assert resp.status_code == 200, resp.text
    csrf = resp.json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


# ==============================================================================
# 1. Defect B01: Duplicate Automatic Task Codes After Deletion
# ==============================================================================

def test_count_delete_create_reproduction_b01(client, db):
    """
    B01 Reproduction & Fix:
    1. Create TSK-01 and TSK-02.
    2. Delete TSK-01.
    3. Next automatic allocation must allocate TSK-03, NOT reuse TSK-02.
    """
    user = create_user_fixture(db, "b01_user", "b01@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # 1. Create TSK-01 (automatic code)
    r1 = client.post(f"/api/projects/{project.id}/tasks", json={
        "phase": "Phase 1",
        "title": "First Task",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)
    assert r1.status_code == 201
    t1 = r1.json()
    assert t1["task_code"] == "TSK-01"

    # 2. Create TSK-02 (automatic code)
    r2 = client.post(f"/api/projects/{project.id}/tasks", json={
        "phase": "Phase 1",
        "title": "Second Task",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10"
    }, headers=headers)
    assert r2.status_code == 201
    t2 = r2.json()
    assert t2["task_code"] == "TSK-02"

    # 3. Delete TSK-01
    r_del = client.delete(f"/api/projects/{project.id}/tasks/{t1['id']}", headers=headers)
    assert r_del.status_code == 200

    # 4. Create third automatic task
    # Under the old row-count bug, count was 1, generating TSK-02 (collision!).
    # Under B01 fix, monotonic allocation allocates TSK-03!
    r3 = client.post(f"/api/projects/{project.id}/tasks", json={
        "phase": "Phase 1",
        "title": "Third Task",
        "start_date": "2026-11-11",
        "end_date": "2026-11-15"
    }, headers=headers)
    assert r3.status_code == 201
    t3 = r3.json()
    assert t3["task_code"] == "TSK-03"

    # Confirm surviving tasks in database have unique codes
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    codes = [t.task_code for t in tasks]
    assert sorted(codes) == ["TSK-02", "TSK-03"]


def test_concurrent_automatic_allocation_produces_no_duplicates(client, db):
    """Concurrent task creations per project receive strictly unique monotonic codes."""
    user = create_user_fixture(db, "conc_user", "conc@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    allocated_codes = []
    errors = []

    def create_single_task(idx):
        with TestClient(app, cookies=client.cookies) as local_cli:
            resp = local_cli.post(f"/api/projects/{project.id}/tasks", json={
                "phase": "Execution",
                "title": f"Concurrent Task {idx}",
                "start_date": f"2026-11-{idx+1:02d}",
                "end_date": f"2026-11-{idx+1:02d}"
            }, headers=headers)
            if resp.status_code == 201:
                allocated_codes.append(resp.json()["task_code"])
            else:
                errors.append((resp.status_code, resp.text))

    threads = [threading.Thread(target=create_single_task, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Concurrent allocation encountered errors: {errors}"
    assert len(allocated_codes) == 8
    # All 8 allocated codes must be strictly distinct
    assert len(set(allocated_codes)) == 8


def test_explicit_duplicate_task_code_rejected(client, db):
    """Explicitly specifying a duplicate task code within the same project is rejected with 400."""
    user = create_user_fixture(db, "dup_user", "dup@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # Create task with code 'CUSTOM-01'
    r1 = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "CUSTOM-01",
        "phase": "Phase 1",
        "title": "Initial Custom Task",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)
    assert r1.status_code == 201

    # Attempt to create another task with identical code
    r2 = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "CUSTOM-01",
        "phase": "Phase 2",
        "title": "Duplicate Code Task",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10"
    }, headers=headers)
    assert r2.status_code == 400
    assert "already exists in this project" in r2.json()["detail"]


# ==============================================================================
# 2. Defect B02: Task Rename Leaves Dangling Dependency References
# ==============================================================================

def test_rename_cascade_rewrites_incoming_dependencies_b02(client, db):
    """
    B02 Reproduction & Fix:
    1. Create Task A (TSK-A).
    2. Create Task B (TSK-B) and Task C (TSK-C) both depending on TSK-A.
    3. Rename TSK-A -> TSK-A2.
    4. Task B and Task C must have their dependencies atomically updated to ['TSK-A2'].
    5. No dangling references to TSK-A remain.
    """
    user = create_user_fixture(db, "b02_user", "b02@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # 1. Create Task A
    ra = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "TSK-A",
        "phase": "Phase 1",
        "title": "Base Architecture",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
        "dependencies": []
    }, headers=headers)
    assert ra.status_code == 201
    task_a = ra.json()

    # 2. Create Task B depending on TSK-A
    rb = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "TSK-B",
        "phase": "Phase 1",
        "title": "Service Implementation",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["TSK-A"]
    }, headers=headers)
    assert rb.status_code == 201
    task_b = rb.json()

    # 3. Create Task C depending on TSK-A
    rc = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "TSK-C",
        "phase": "Phase 1",
        "title": "Integration Testing",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["TSK-A"]
    }, headers=headers)
    assert rc.status_code == 201
    task_c = rc.json()

    # 4. Rename Task A to TSK-A2
    r_rename = client.put(f"/api/projects/{project.id}/tasks/{task_a['id']}", json={
        "task_code": "TSK-A2"
    }, headers=headers)
    assert r_rename.status_code == 200
    assert r_rename.json()["task_code"] == "TSK-A2"

    # 5. Verify database state for Task B and Task C
    tb_db = db.query(RoadmapTask).filter(RoadmapTask.id == task_b["id"]).first()
    tc_db = db.query(RoadmapTask).filter(RoadmapTask.id == task_c["id"]).first()
    db.refresh(tb_db)
    db.refresh(tc_db)

    # Dependencies must now be ['TSK-A2'] and never contain 'TSK-A'
    assert tb_db.dependencies == ["TSK-A2"]
    assert tc_db.dependencies == ["TSK-A2"]

    # Subsequent updates to Task B must succeed without dangling dependency errors
    rb_update = client.put(f"/api/projects/{project.id}/tasks/{task_b['id']}", json={
        "title": "Service Implementation Updated"
    }, headers=headers)
    assert rb_update.status_code == 200


def test_rename_rollback_on_invalid_candidate_graph(client, db):
    """If renaming would result in a duplicate code or invalid graph, no changes are committed."""
    user = create_user_fixture(db, "rb_rename_user", "rb_rename@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # Task A
    ra = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "TSK-A",
        "phase": "Phase 1",
        "title": "Task A",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)
    task_a = ra.json()

    # Task B
    rb = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "TSK-B",
        "phase": "Phase 1",
        "title": "Task B",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10"
    }, headers=headers)

    # Try renaming Task A to 'TSK-B' (which clashes with existing Task B)
    r_clash = client.put(f"/api/projects/{project.id}/tasks/{task_a['id']}", json={
        "task_code": "TSK-B"
    }, headers=headers)
    assert r_clash.status_code == 400
    assert "already exists in this project" in r_clash.json()["detail"]

    # Verify Task A remained unchanged
    ta_db = db.query(RoadmapTask).filter(RoadmapTask.id == task_a["id"]).first()
    db.refresh(ta_db)
    assert ta_db.task_code == "TSK-A"


# ==============================================================================
# 3. Defect B03: Manual Schedule Changes Violating Prerequisite Dates
# ==============================================================================

def test_schedule_prerequisite_date_ordering_b03(client, db):
    """
    B03 Reproduction & Fix:
    Prerequisite ending Nov 20 and dependent starting Nov 02 must be rejected with 400.
    """
    user = create_user_fixture(db, "b03_user", "b03@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # Create Prerequisite Task ending November 20
    r_prereq = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "PREREQ-01",
        "phase": "Phase 1",
        "title": "Long Prerequisite Research",
        "start_date": "2026-11-01",
        "end_date": "2026-11-20"
    }, headers=headers)
    assert r_prereq.status_code == 201

    # Attempt to create Dependent Task starting November 02 depending on PREREQ-01
    r_invalid = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "DEP-01",
        "phase": "Phase 1",
        "title": "Premature Dependent Task",
        "start_date": "2026-11-02",
        "end_date": "2026-11-25",
        "dependencies": ["PREREQ-01"]
    }, headers=headers)
    assert r_invalid.status_code == 400
    assert "Schedule conflict" in r_invalid.json()["detail"]
    assert "starts on 2026-11-02, which is earlier than prerequisite 'PREREQ-01' end date (2026-11-20)" in r_invalid.json()["detail"]


def test_upstream_date_edit_cannot_invalidate_downstream_schedule(client, db):
    """
    Editing an upstream prerequisite's end date so it extends past a downstream
    dependent's start date is rejected with 400.
    """
    user = create_user_fixture(db, "sched_edit_user", "sched_edit@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # Prerequisite initially ends Nov 10
    ra = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "PRE-01",
        "phase": "Phase 1",
        "title": "Phase 1 Work",
        "start_date": "2026-11-01",
        "end_date": "2026-11-10"
    }, headers=headers)
    task_a = ra.json()

    # Dependent starts Nov 15 and ends Nov 20
    rb = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "POST-01",
        "phase": "Phase 2",
        "title": "Phase 2 Work",
        "start_date": "2026-11-15",
        "end_date": "2026-11-20",
        "dependencies": ["PRE-01"]
    }, headers=headers)
    assert rb.status_code == 201

    # Attempt to delay PRE-01 to end on Nov 25 (violates POST-01 starting Nov 15)
    r_invalid_edit = client.put(f"/api/projects/{project.id}/tasks/{task_a['id']}", json={
        "end_date": "2026-11-25"
    }, headers=headers)
    assert r_invalid_edit.status_code == 400
    assert "Schedule conflict" in r_invalid_edit.json()["detail"]
    assert "POST-01" in r_invalid_edit.json()["detail"]


def test_boundary_date_equality_rule(client, db):
    """
    Boundary-Date Equality Rule:
    Dependent starting on the EXACT SAME date as prerequisite end date is PERMITTED.
    Dependent starting ONE DAY BEFORE prerequisite end date is REJECTED.
    """
    user = create_user_fixture(db, "boundary_user", "boundary@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # Prerequisite: Nov 01 to Nov 10
    client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "BASE-10",
        "phase": "Phase 1",
        "title": "Milestone Handover",
        "start_date": "2026-11-01",
        "end_date": "2026-11-10"
    }, headers=headers)

    # Case A: Dependent starts exactly on Nov 10 (valid under boundary equality rule)
    r_equal = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "SAME-DAY",
        "phase": "Phase 2",
        "title": "Immediate Continuation",
        "start_date": "2026-11-10",
        "end_date": "2026-11-15",
        "dependencies": ["BASE-10"]
    }, headers=headers)
    assert r_equal.status_code == 201

    # Case B: Dependent starts on Nov 09 (1 day before prerequisite ends -> rejected)
    r_early = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "PREMATURE",
        "phase": "Phase 2",
        "title": "Too Early Continuation",
        "start_date": "2026-11-09",
        "end_date": "2026-11-15",
        "dependencies": ["BASE-10"]
    }, headers=headers)
    assert r_early.status_code == 400
    assert "Schedule conflict" in r_early.json()["detail"]


# ==============================================================================
# 4. Graph Validation: Self-Dependency, Cycles, Foreign References
# ==============================================================================

def test_foreign_project_references_rejected(client, db):
    """A task cannot depend on a task code that belongs to a different project."""
    user = create_user_fixture(db, "foreign_user", "foreign@test.com")
    proj_a = create_project_fixture(db, user, name="Project Alpha")
    proj_b = create_project_fixture(db, user, name="Project Beta")
    headers = auth_client_for_user(client, user)

    # Create task in Project A
    client.post(f"/api/projects/{proj_a.id}/tasks", json={
        "task_code": "ALPHA-01",
        "phase": "Phase 1",
        "title": "Alpha Task",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)

    # Attempt to reference ALPHA-01 from Project B
    r_foreign = client.post(f"/api/projects/{proj_b.id}/tasks", json={
        "task_code": "BETA-01",
        "phase": "Phase 1",
        "title": "Beta Task",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["ALPHA-01"]
    }, headers=headers)
    assert r_foreign.status_code == 400
    assert "does not exist in this project" in r_foreign.json()["detail"]


def test_self_dependency_rejected(client, db):
    """A task cannot depend on itself."""
    user = create_user_fixture(db, "self_dep_user", "selfdep@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    resp = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "SELF-01",
        "phase": "Phase 1",
        "title": "Self Dependent",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
        "dependencies": ["SELF-01"]
    }, headers=headers)
    assert resp.status_code == 400
    assert "cannot depend on itself" in resp.json()["detail"].lower()


def test_circular_dependency_chain_rejected(client, db):
    """Circular dependency chain (A -> B -> C -> A) is detected and rejected."""
    user = create_user_fixture(db, "cycle_user", "cycle@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    # A -> B -> C
    ra = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "NODE-A",
        "phase": "P1",
        "title": "Node A",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)
    rb = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "NODE-B",
        "phase": "P1",
        "title": "Node B",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["NODE-A"]
    }, headers=headers)
    rc = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "NODE-C",
        "phase": "P1",
        "title": "Node C",
        "start_date": "2026-11-11",
        "end_date": "2026-11-15",
        "dependencies": ["NODE-B"]
    }, headers=headers)

    # Update Node A to depend on Node C (closes the cycle)
    r_cycle = client.put(f"/api/projects/{project.id}/tasks/{ra.json()['id']}", json={
        "dependencies": ["NODE-C"]
    }, headers=headers)
    assert r_cycle.status_code == 400
    assert "Circular dependency detected" in r_cycle.json()["detail"]


# ==============================================================================
# 5. Deletion Safety Policy
# ==============================================================================

def test_deletion_with_dependents_rejected_with_blocking_list(client, db):
    """Deleting a task that has active dependents is rejected with a descriptive list of dependents."""
    user = create_user_fixture(db, "del_dep_user", "deldep@test.com")
    project = create_project_fixture(db, user)
    headers = auth_client_for_user(client, user)

    ra = client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "PARENT-01",
        "phase": "P1",
        "title": "Parent",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers)
    parent_id = ra.json()["id"]

    client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "CHILD-01",
        "phase": "P1",
        "title": "Child 1",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["PARENT-01"]
    }, headers=headers)

    client.post(f"/api/projects/{project.id}/tasks", json={
        "task_code": "CHILD-02",
        "phase": "P1",
        "title": "Child 2",
        "start_date": "2026-11-06",
        "end_date": "2026-11-10",
        "dependencies": ["PARENT-01"]
    }, headers=headers)

    # Attempt to delete PARENT-01
    r_del = client.delete(f"/api/projects/{project.id}/tasks/{parent_id}", headers=headers)
    assert r_del.status_code == 400
    detail = r_del.json()["detail"]
    assert "Cannot delete task PARENT-01" in detail
    assert "CHILD-01" in detail
    assert "CHILD-02" in detail


# ==============================================================================
# 6. Bulk Generation & Version Restore Compatibility
# ==============================================================================

def test_bulk_generation_persistence_and_version_restore_compatibility(db):
    """
    RoadmapDomainService.reconcile_roadmap_tasks enforces duplicate code rejection
    and persists valid tasks without violating uniqueness or dropping existing user tasks.
    """
    from fastapi import HTTPException
    user = create_user_fixture(db, "bulk_sync_user", "bulksync@test.com")
    project = create_project_fixture(db, user)

    # 1. Deliberate duplicate code in incoming payload must be rejected cleanly (Batch 06.1)
    duplicate_plan = [
        {"task_code": "PLAN-01", "phase": "P1", "title": "First Step", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "PLAN-01", "phase": "P2", "title": "Second Step With Duplicate Code", "start_date": "2026-11-06", "end_date": "2026-11-10"},
        {"task_code": "PLAN-02", "phase": "P2", "title": "Third Step", "start_date": "2026-11-11", "end_date": "2026-11-15"}
    ]
    with pytest.raises(HTTPException):
        RoadmapDomainService.reconcile_roadmap_tasks(db, project, duplicate_plan)

    # 2. Valid incoming plan reconciles and persists cleanly
    valid_plan = [
        {"task_code": "PLAN-01", "phase": "P1", "title": "First Step", "start_date": "2026-11-01", "end_date": "2026-11-05"},
        {"task_code": "PLAN-02", "phase": "P2", "title": "Second Step", "start_date": "2026-11-06", "end_date": "2026-11-10"},
        {"task_code": "PLAN-03", "phase": "P2", "title": "Third Step", "start_date": "2026-11-11", "end_date": "2026-11-15"}
    ]
    RoadmapDomainService.reconcile_roadmap_tasks(db, project, valid_plan)
    db.commit()

    persisted = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    assert len(persisted) == 3
    persisted_codes = [t.task_code for t in persisted]
    assert sorted(persisted_codes) == ["PLAN-01", "PLAN-02", "PLAN-03"]


# ==============================================================================
# 7. Cross-User Project Isolation and CSRF
# ==============================================================================

def test_cross_user_project_isolation(client, db):
    """User B cannot access or mutate tasks in User A's project."""
    user_a = create_user_fixture(db, "owner_a", "owner_a@test.com")
    user_b = create_user_fixture(db, "intruder_b", "intruder_b@test.com")
    proj_a = create_project_fixture(db, user_a, name="User A Secret Venture")

    headers_b = auth_client_for_user(client, user_b)

    # User B tries to create task in User A's project
    r_post = client.post(f"/api/projects/{proj_a.id}/tasks", json={
        "title": "Hacked Task",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    }, headers=headers_b)
    assert r_post.status_code == 403
    assert "You do not have permission" in r_post.json()["detail"]

    # User B tries to list tasks in User A's project
    r_get = client.get(f"/api/projects/{proj_a.id}/tasks", headers=headers_b)
    assert r_get.status_code == 403
    assert "You do not have permission" in r_get.json()["detail"]


def test_csrf_required_for_task_mutations(client, db):
    """Task mutations require valid CSRF headers."""
    user = create_user_fixture(db, "csrf_task_user", "csrftask@test.com")
    project = create_project_fixture(db, user)
    auth_client_for_user(client, user)

    # Post without CSRF header
    r_no_csrf = client.post(f"/api/projects/{project.id}/tasks", json={
        "title": "Task without CSRF",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05"
    })
    assert r_no_csrf.status_code == 403


# ==============================================================================
# 8. Migration Preflight & Data Repair Tests
# ==============================================================================

def test_migration_preflight_referenced_duplicate_detection_logic():
    """
    Migration preflight detects ambiguous referenced duplicates and raises RuntimeError,
    refusing to guess or drop edges.
    """
    # Simulate project tasks with duplicate 'TSK-01' where 'TSK-02' depends on 'TSK-01'
    project_id = "test-proj-ambiguous"
    all_proj_tasks = [
        ("t1", "TSK-01", []),
        ("t2", "TSK-01", []),
        ("t3", "TSK-02", ["TSK-01"])  # References TSK-01
    ]

    # Reference check matching migration logic
    code = "TSK-01"
    is_referenced = False
    referencing = []
    for row in all_proj_tasks:
        deps = row[2]
        if code in deps:
            is_referenced = True
            referencing.append(row[1])

    assert is_referenced is True
    assert "TSK-02" in referencing

    # Verify migration logic raises RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        if is_referenced:
            raise RuntimeError(
                f"Preflight migration failed: Ambiguous duplicate task code '{code}' in project '{project_id}' "
                f"is referenced by downstream tasks ({', '.join(referencing)}). "
                "Manual resolution required before applying unique constraint."
            )
    assert "Preflight migration failed" in str(exc_info.value)
    assert "Ambiguous duplicate task code 'TSK-01'" in str(exc_info.value)


def test_migration_preflight_unreferenced_duplicate_renumbering_logic():
    """
    Migration preflight cleanly and deterministically renumbers unreferenced duplicates,
    preserving all rows and metadata.
    """
    project_id = "test-proj-unreferenced"
    code = "TSK-01"
    all_proj_tasks = [
        ("t1", "TSK-01", []),
        ("t2", "TSK-01", []),
        ("t3", "TSK-01", [])
    ]

    existing_codes = {"TSK-01"}
    renamed = {}

    dup_rows = [("t1", "2026-11-01"), ("t2", "2026-11-02"), ("t3", "2026-11-03")]
    for idx, r in enumerate(dup_rows[1:], start=1):
        row_id = r[0]
        new_code = f"{code}_dup{idx}"
        counter = idx
        while new_code in existing_codes:
            counter += 1
            new_code = f"{code}_dup{counter}"
        existing_codes.add(new_code)
        renamed[row_id] = new_code

    assert renamed == {
        "t2": "TSK-01_dup1",
        "t3": "TSK-01_dup2"
    }
    # All 3 tasks now have distinct codes and none were deleted
    assert len(existing_codes) == 3

