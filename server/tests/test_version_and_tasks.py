import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_user_and_project():
    uid = uuid.uuid4().hex[:8]
    user_data = {
        "username": f"ver_tester_{uid}",
        "email": f"ver_test_{uid}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    }
    resp = client.post("/api/auth/register", json=user_data)
    csrf_token = resp.json()["csrf_token"]

    proj_data = {
        "name": "Version Test Venture",
        "stage": "Idea / MVP",
        "description": "Testing max 5 version control engine"
    }
    proj_resp = client.post("/api/projects", json=proj_data, headers={"X-CSRF-Token": csrf_token})
    project_id = proj_resp.json()["id"]

    return {"csrf_token": csrf_token, "project_id": project_id}

def test_max_five_versions_enforcement(setup_user_and_project):
    headers = {"X-CSRF-Token": setup_user_and_project["csrf_token"]}
    project_id = setup_user_and_project["project_id"]

    # We manually add versions using the modules endpoint or modify endpoint
    # First, let's create 5 versions in BMC
    from app.db.session import SessionLocal
    from app.models.all_models import ModuleContent, ModuleVersion
    from app.services.version_service import VersionService, MAX_VERSIONS_LIMIT

    db = SessionLocal()
    try:
        module = VersionService.get_or_create_module(db, project_id, "bmc")
        dummy_data = {
            "tagline": "Test Tagline",
            "customer_segments": ["Segment 1"],
            "value_propositions": ["Value 1"],
            "channels": ["Direct"],
            "customer_relationships": ["Automated"],
            "revenue_streams": ["SaaS"],
            "key_resources": ["IP"],
            "key_activities": ["Dev"],
            "key_partnerships": ["Cloud"],
            "cost_structure": ["Hosting"]
        }

        # Save 5 versions
        for i in range(1, 6):
            VersionService.save_new_version(
                db=db,
                module=module,
                data=dummy_data,
                change_summary=f"Version {i} summary"
            )

        versions = VersionService.get_versions(db, module.id)
        assert len(versions) == 5

        # Attempting to save a 6th version MUST raise 409 Conflict as per Part 26.2!
        with pytest.raises(Exception) as exc_info:
            VersionService.save_new_version(
                db=db,
                module=module,
                data=dummy_data,
                change_summary="Version 6 attempt"
            )
        assert "VERSION_LIMIT_EXCEEDED" in str(exc_info.value.detail)

        # User chooses to resolve conflict by replacing Version 1
        v1_id = versions[0].id
        updated_ver = VersionService.resolve_conflict_and_replace(
            db=db,
            module=module,
            replace_version_id=v1_id,
            new_data={**dummy_data, "tagline": "Replaced Tagline"},
            new_name="Custom Replaced V1"
        )
        assert updated_ver.version_name == "Custom Replaced V1"
        assert len(VersionService.get_versions(db, module.id)) == 5
    finally:
        db.close()

def test_task_crud_and_dependency_protection(setup_user_and_project):
    headers = {"X-CSRF-Token": setup_user_and_project["csrf_token"]}
    project_id = setup_user_and_project["project_id"]

    # 1. Create Task 1
    t1_data = {
        "task_code": "TSK-01",
        "phase": "Planning & Research",
        "title": "Market Feasibility Spike",
        "timeline": "30-day",
        "start_date": "2026-10-01",
        "end_date": "2026-10-15",
        "priority": "Critical",
        "status": "In Progress"
    }
    t1_resp = client.post(f"/api/projects/{project_id}/tasks", json=t1_data, headers=headers)
    assert t1_resp.status_code == 201, t1_resp.text
    t1 = t1_resp.json()

    # 2. Create Task 2 depending on Task 1
    t2_data = {
        "task_code": "TSK-02",
        "phase": "System Design",
        "title": "Architecture Blueprint",
        "timeline": "60-day",
        "start_date": "2026-10-16",
        "end_date": "2026-10-31",
        "priority": "High",
        "status": "Pending",
        "dependencies": ["TSK-01"]
    }
    t2_resp = client.post(f"/api/projects/{project_id}/tasks", json=t2_data, headers=headers)
    assert t2_resp.status_code == 201
    t2 = t2_resp.json()

    # 3. Attempting to delete Task 1 while Task 2 depends on it must fail!
    del_resp = client.delete(f"/api/projects/{project_id}/tasks/{t1['id']}", headers=headers)
    assert del_resp.status_code == 400
    assert "depend on it" in del_resp.json()["detail"]

    # 4. Check roadmap summary calculation
    summary_resp = client.get(f"/api/projects/{project_id}/tasks/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_tasks"] == 2
    assert summary["completed_tasks"] == 0

    # 5. Mark Task 1 as Finished and check summary updates
    patch_resp = client.put(
        f"/api/projects/{project_id}/tasks/{t1['id']}",
        json={"status": "Finished"},
        headers=headers
    )
    assert patch_resp.status_code == 200

    summary_after = client.get(f"/api/projects/{project_id}/tasks/summary").json()
    assert summary_after["completed_tasks"] == 1
    assert summary_after["overall_progress"] == 50
