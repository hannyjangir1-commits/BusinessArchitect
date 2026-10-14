import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_register_and_login_flow():
    uid = uuid.uuid4().hex[:8]
    # 1. Register User A
    user_data = {
        "username": f"alice_{uid}",
        "email": f"alice_{uid}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    }
    resp = client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["username"] == f"alice_{uid}"
    assert "csrf_token" in body
    csrf_token = body["csrf_token"]

    # Verify session cookie was set
    assert "aba_session" in client.cookies

    # 2. Duplicate registration should fail
    dup_resp = client.post("/api/auth/register", json=user_data)
    assert dup_resp.status_code == 400

    # 3. Create a project
    proj_data = {
        "name": "CloudScale AI",
        "stage": "Growth",
        "industry": "Enterprise Software",
        "description": "Autonomous cloud cost optimization platform",
        "target_customers": "DevOps Leads and VP of Infrastructure",
        "goals": "Scale to $1M ARR",
        "existing_stack": {
            "Frontend": ["React"],
            "Backend": ["FastAPI"],
            "Database": ["PostgreSQL"]
        }
    }
    headers = {"X-CSRF-Token": csrf_token}
    proj_resp = client.post("/api/projects", json=proj_data, headers=headers)
    assert proj_resp.status_code == 201, proj_resp.text
    created_proj = proj_resp.json()
    assert created_proj["name"] == "CloudScale AI"
    assert created_proj["stage"] == "Growth"
    project_id = created_proj["id"]

    # 4. Fetch the project
    get_resp = client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id

    # 5. Test Navigation Memory persistence
    nav_resp = client.patch(
        f"/api/projects/{project_id}/active-module",
        json={"active_module": "tech_stack"},
        headers=headers
    )
    assert nav_resp.status_code == 200
    assert nav_resp.json()["active_module"] == "tech_stack"

    # Re-fetch project to confirm navigation memory is saved in DB
    refetch = client.get(f"/api/projects/{project_id}").json()
    assert refetch["active_module"] == "tech_stack"

def test_cross_user_isolation():
    uid_b = uuid.uuid4().hex[:8]
    # Register User B
    client_b = TestClient(app)
    user_b = {
        "username": f"bob_{uid_b}",
        "email": f"bob_{uid_b}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    }
    resp_b = client_b.post("/api/auth/register", json=user_b)
    assert resp_b.status_code == 201

    # Try to access User A's projects from User B's session
    # List projects should be empty for User B
    b_projs = client_b.get("/api/projects").json()
    assert len(b_projs) == 0

    # Attempt direct unauthorized access to User A's project
    alice_projs = client.get("/api/projects").json()
    if alice_projs:
        alice_project_id = alice_projs[0]["id"]
        unauth_resp = client_b.get(f"/api/projects/{alice_project_id}")
        assert unauth_resp.status_code == 403, "Cross-user access must be strictly forbidden"
