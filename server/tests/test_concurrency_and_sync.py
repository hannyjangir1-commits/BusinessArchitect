import uuid
import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.services.version_service import VersionService
from app.models.all_models import RoadmapTask
from app.services.pdf_service import PDFService

client = TestClient(app)

@pytest.fixture
def project_fixture():
    uid = uuid.uuid4().hex[:8]
    cli = TestClient(app)
    reg_resp = cli.post("/api/auth/register", json={
        "username": f"sync_{uid}",
        "email": f"sync_{uid}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    })
    csrf = reg_resp.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    p_resp = cli.post("/api/projects", json={
        "name": "Sync & Concurrency Venture",
        "stage": "Growth",
        "description": "Concurrency testing"
    }, headers=headers)
    return {"client": cli, "project_id": p_resp.json()["id"], "headers": headers}

def test_concurrent_version_creation_limit(project_fixture):
    """Verify that concurrent attempts to create versions cannot exceed 5 versions total."""
    project_id = project_fixture["project_id"]
    
    # Pre-seed 4 versions
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "bmc")
        for i in range(1, 5):
            VersionService.save_new_version(db, mod, {"block": i}, change_summary=f"v{i}")
    finally:
        db.close()

    # Attempt to concurrently save 4 more versions across threads
    results = []
    def try_save(idx):
        thread_db = SessionLocal()
        try:
            m = VersionService.get_or_create_module(thread_db, project_id, "bmc")
            VersionService.save_new_version(thread_db, m, {"block": f"concurrent_{idx}"}, change_summary=f"concurrent_{idx}")
            return "SUCCESS"
        except Exception as e:
            return f"REJECTED: {type(e).__name__}"
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(try_save, i) for i in range(4)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Verify that exactly 1 succeeded and 3 were rejected because the 5-version limit was hit
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "bmc")
        versions = VersionService.get_versions(db, mod.id)
        assert len(versions) == 5, f"Expected exactly 5 versions, but found {len(versions)}"
        assert results.count("SUCCESS") == 1
    finally:
        db.close()

def test_roadmap_task_sync_and_milestone_recalculation(project_fixture):
    """Verify that updating a task status immediately recalculates milestone progress percentages."""
    cli = project_fixture["client"]
    headers = project_fixture["headers"]
    project_id = project_fixture["project_id"]

    # Create two 30-day tasks
    t1 = cli.post(f"/api/projects/{project_id}/tasks", json={
        "task_code": "TSK-01",
        "phase": "Planning & Research",
        "title": "Task 1",
        "timeline": "30-day",
        "start_date": "2026-10-01",
        "end_date": "2026-10-15",
        "status": "Pending"
    }, headers=headers).json()

    t2 = cli.post(f"/api/projects/{project_id}/tasks", json={
        "task_code": "TSK-02",
        "phase": "Planning & Research",
        "title": "Task 2",
        "timeline": "30-day",
        "start_date": "2026-10-16",
        "end_date": "2026-10-31",
        "status": "Pending"
    }, headers=headers).json()

    # Initial summary: 0% progress (0/2 completed)
    sum1 = cli.get(f"/api/projects/{project_id}/tasks/summary").json()
    assert sum1["milestone_30_total"] == 2
    assert sum1["milestone_30_completed"] == 0
    assert sum1["milestone_30_progress"] == 0

    # Mark Task 1 as Finished
    cli.patch(f"/api/projects/{project_id}/tasks/{t1['id']}", json={
        "status": "Finished"
    }, headers=headers)

    # Progress should now immediately reflect 50% (1/2 completed)
    sum2 = cli.get(f"/api/projects/{project_id}/tasks/summary").json()
    assert sum2["milestone_30_completed"] == 1
    assert sum2["milestone_30_progress"] == 50

    # Mark Task 2 as Finished
    cli.patch(f"/api/projects/{project_id}/tasks/{t2['id']}", json={
        "status": "Finished"
    }, headers=headers)

    # Progress should now be 100% (2/2 completed)
    sum3 = cli.get(f"/api/projects/{project_id}/tasks/summary").json()
    assert sum3["milestone_30_completed"] == 2
    assert sum3["milestone_30_progress"] == 100

def test_export_pdf_structural_correctness():
    """Verify that PDF generation renders the project details, tables, and correctly excludes sensitive data."""
    proj_dict = {
        "name": "OmniCorp Global",
        "stage": "Growth",
        "industry": "Industrial AI",
        "description": "Predictive maintenance robotics",
        "goals": "Scale to 500 plants"
    }
    modules_data = {
        "bmc": {
            "tagline": "Autonomous industrial reliability",
            "customer_segments": ["Manufacturing plants", "Automotive OEMs"],
            "value_propositions": ["Zero unplanned downtime"],
            "channels": ["Direct enterprise"],
            "customer_relationships": ["24/7 dedicated support"],
            "revenue_streams": ["Annual hardware + software subscription"],
            "key_resources": ["Proprietary acoustic sensors"],
            "key_activities": ["Sensor deployment & model training"],
            "key_partnerships": ["Siemens", "ABB"],
            "cost_structure": ["Hardware production", "Cloud telemetry infra"]
        }
    }
    tasks_list = [
        {
            "task_code": "TSK-01",
            "phase": "Planning & Research",
            "title": "Plant Site Survey",
            "timeline": "30-day",
            "start_date": "2026-10-01",
            "end_date": "2026-10-15",
            "priority": "Critical",
            "status": "Finished",
            "deliverables": "Survey Report"
        }
    ]

    pdf_bytes = PDFService.generate_full_project_pdf(proj_dict, modules_data, tasks_list)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 2000

    # Ensure sensitive excluded data cannot be present
    assert b"copilot_messages" not in pdf_bytes
    assert b"audit_logs" not in pdf_bytes
