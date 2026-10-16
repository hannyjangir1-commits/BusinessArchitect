import os
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

@pytest.fixture(scope="module")
def primary_user():
    """Register and log in primary user in an isolated TestClient."""
    cli = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"user_{uid}@enterprise.io"
    password = "StrongPassword123!"

    reg_resp = cli.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password,
        "terms_accepted": True,
        "privacy_accepted": True
    })
    assert reg_resp.status_code == 201
    csrf_token = reg_resp.json()["csrf_token"]
    user_id = reg_resp.json()["user"]["id"]

    return {
        "client": cli,
        "username": username,
        "email": email,
        "password": password,
        "csrf_token": csrf_token,
        "user_id": user_id
    }

@pytest.fixture(scope="module")
def secondary_user():
    """Register second user for cross-user security isolation tests in a separate TestClient."""
    cli = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    username = f"attacker_{uid}"
    email = f"attacker_{uid}@evilcorp.io"
    password = "AttackerPassword123!"

    reg_resp = cli.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password,
        "terms_accepted": True,
        "privacy_accepted": True
    })
    assert reg_resp.status_code == 201
    return {
        "client": cli,
        "username": username,
        "email": email,
        "password": password,
        "csrf_token": reg_resp.json()["csrf_token"],
        "user_id": reg_resp.json()["user"]["id"]
    }

def test_workflow_01_registration_and_login(primary_user):
    """Scenario 1: Register, login, check current user session."""
    cli = primary_user["client"]
    me_resp = cli.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == primary_user["email"]

def test_workflow_02_create_and_reopen_project(primary_user):
    """Scenario 2 & 3: Create project with stage-aware fields, save and reopen."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    proj_data = {
        "name": "CloudScale Mesh",
        "stage": "Growth",
        "industry": "Cloud Infrastructure",
        "description": "Zero-trust service mesh with AI-driven traffic optimization",
        "target_customers": "Enterprise DevOps and Site Reliability Engineers",
        "goals": "Expand customer base to 100 enterprise accounts",
        "existing_stack": {
            "Frontend": ["React", "TypeScript"],
            "Backend": ["FastAPI", "Go"],
            "Database": ["PostgreSQL", "Redis"],
            "Cloud/Hosting": ["AWS", "Render"]
        }
    }
    create_resp = cli.post("/api/projects", json=proj_data, headers=headers)
    assert create_resp.status_code == 201
    project = create_resp.json()
    assert project["name"] == "CloudScale Mesh"
    assert project["stage"] == "Growth"
    assert "FastAPI" in project["existing_stack"].get("Backend", [])
    project_id = project["id"]

    # Reopen project
    get_resp = cli.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id

@pytest.mark.skipif(not settings.GEMINI_API_KEY, reason="GEMINI_API_KEY required for live AI generation")
def test_workflow_04_gemini_bmc_generation_nine_blocks(primary_user):
    """Scenario 4: Generate BMC via Gemini and verify all 9 Alexander Osterwalder blocks."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    
    # Create project for BMC
    p_resp = cli.post("/api/projects", json={
        "name": "Veloce Motors",
        "stage": "Idea / MVP",
        "industry": "Automotive AI",
        "description": "Subscription EV fleet management platform for delivery logistics",
        "target_customers": "Fleet managers and last-mile delivery operators"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    gen_resp = cli.post(f"/api/projects/{project_id}/modules/bmc/generate", headers=headers)
    assert gen_resp.status_code == 200
    data = gen_resp.json()["data"]

    # Verify all 9 blocks exist with non-empty content
    required_blocks = [
        "customer_segments", "value_propositions", "channels",
        "customer_relationships", "revenue_streams", "key_resources",
        "key_activities", "key_partnerships", "cost_structure"
    ]
    for block in required_blocks:
        assert block in data, f"Missing BMC block: {block}"
        assert len(data[block]) >= 1, f"Empty BMC block: {block}"
    assert data.get("tagline"), "Missing BMC tagline"

@pytest.mark.skipif(not settings.GEMINI_API_KEY, reason="GEMINI_API_KEY required")
def test_workflow_05_gemini_tech_stack_generation(primary_user):
    """Scenario 5: Generate Tech Stack recommendations and infographic payload."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "PayFlow Global",
        "stage": "Growth",
        "industry": "FinTech",
        "description": "Cross-border B2B instant settlement engine",
        "existing_stack": {"Backend": ["FastAPI"], "Database": ["PostgreSQL"]}
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    gen_resp = cli.post(f"/api/projects/{project_id}/modules/tech_stack/generate", headers=headers)
    assert gen_resp.status_code == 200
    data = gen_resp.json()["data"]
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 1

def test_workflow_06_and_07_roadmap_tasks_and_dependencies(primary_user):
    """Scenario 6 & 7: Add, edit, delete tasks, test dependency protection."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Roadmap Project",
        "stage": "Idea / MVP",
        "description": "Roadmap task execution"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Create Task 1
    t1_resp = cli.post(f"/api/projects/{project_id}/tasks", json={
        "task_code": "TSK-01",
        "phase": "Planning & Research",
        "title": "Market Feasibility Study",
        "timeline": "30-day",
        "start_date": "2026-10-01",
        "end_date": "2026-10-15",
        "priority": "Critical",
        "status": "In Progress"
    }, headers=headers)
    assert t1_resp.status_code == 201
    t1_id = t1_resp.json()["id"]

    # Create Task 2 dependent on Task 1
    t2_resp = cli.post(f"/api/projects/{project_id}/tasks", json={
        "task_code": "TSK-02",
        "phase": "System Design",
        "title": "System Architecture Specification",
        "timeline": "30-day",
        "start_date": "2026-10-16",
        "end_date": "2026-10-31",
        "priority": "High",
        "status": "Pending",
        "dependencies": ["TSK-01"]
    }, headers=headers)
    assert t2_resp.status_code == 201
    t2_id = t2_resp.json()["id"]

    # Attempting to delete Task 1 while Task 2 depends on it MUST be rejected!
    del_fail = cli.delete(f"/api/projects/{project_id}/tasks/{t1_id}", headers=headers)
    assert del_fail.status_code == 400
    assert "depend" in del_fail.json()["detail"].lower()

    # Now delete Task 2 first, then Task 1
    del_t2 = cli.delete(f"/api/projects/{project_id}/tasks/{t2_id}", headers=headers)
    assert del_t2.status_code in (200, 204)

    del_t1 = cli.delete(f"/api/projects/{project_id}/tasks/{t1_id}", headers=headers)
    assert del_t1.status_code in (200, 204)

def test_workflow_08_and_09_ai_section_chat_and_version_creation(primary_user):
    """Scenario 8 & 9: Section-specific AI modification creates a new version V2."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Biotech Labs",
        "stage": "Growth",
        "description": "Genomic sequence data analysis platform"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Seed V1 manually
    from app.db.session import SessionLocal
    from app.services.version_service import VersionService
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "bmc")
        VersionService.save_new_version(db, mod, {
            "tagline": "AI Genomics",
            "customer_segments": ["Research Institutes"],
            "value_propositions": ["Fast alignment"],
            "channels": ["Direct"],
            "customer_relationships": ["Self-serve"],
            "revenue_streams": ["Subscription"],
            "key_resources": ["Cluster"],
            "key_activities": ["Pipelines"],
            "key_partnerships": ["Illumina"],
            "cost_structure": ["AWS Cloud"]
        }, change_summary="V1 initial")
    finally:
        db.close()

    # Modify via section chat
    mod_resp = cli.post(f"/api/projects/{project_id}/modules/bmc/modify", json={
        "instruction": "Add Pharmaceutical Companies to customer segments and describe a custom enterprise SLA revenue model."
    }, headers=headers)
    assert mod_resp.status_code == 200
    assert mod_resp.json()["active_version_number"] == 2
    assert len(mod_resp.json()["versions"]) == 2

def test_workflow_10_version_limit_max_five(primary_user):
    """Scenario 10: Enforce strict 5-version limit with 409 Conflict."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Version Sandbox",
        "stage": "Idea / MVP"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    from app.db.session import SessionLocal
    from app.services.version_service import VersionService
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "tech_stack")
        for i in range(1, 6):
            VersionService.save_new_version(db, mod, {"tier": i}, change_summary=f"v{i}")
        
        # 6th version attempt must be rejected
        with pytest.raises(Exception) as exc_info:
            VersionService.save_new_version(db, mod, {"tier": 6}, change_summary="v6")
        assert "VERSION_LIMIT_EXCEEDED" in str(exc_info.value.detail)
    finally:
        db.close()

def test_workflow_11_version_rename_delete_restore(primary_user):
    """Scenario 11: Rename, delete, and restore versions."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Version Lifecycle",
        "stage": "Idea / MVP"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Setup versions
    from app.db.session import SessionLocal
    from app.services.version_service import VersionService
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "bmc")
        v1 = VersionService.save_new_version(db, mod, {"v": 1}, change_summary="initial")
        v2 = VersionService.save_new_version(db, mod, {"v": 2}, change_summary="second")
        v1_id = v1.id
        v2_id = v2.id
    finally:
        db.close()

    # Rename V1
    ren_resp = cli.patch(
        f"/api/projects/{project_id}/modules/bmc/versions/{v1_id}/rename",
        json={"version_name": "Strategic Baseline V1"},
        headers=headers
    )
    assert ren_resp.status_code == 200
    assert ren_resp.json()["version_name"] == "Strategic Baseline V1"

    # Restore V1
    rest_resp = cli.post(
        f"/api/projects/{project_id}/modules/bmc/versions/{v1_id}/restore",
        headers=headers
    )
    assert rest_resp.status_code == 200
    # Requirement A1: Restoring V1 restores V1 without creating a new version 3
    assert rest_resp.json()["active_version_number"] == 1

    # Delete V2
    del_resp = cli.delete(
        f"/api/projects/{project_id}/modules/bmc/versions/{v2_id}",
        headers=headers
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Version successfully deleted"

def test_workflow_12_per_project_navigation_memory(primary_user):
    """Scenario 12: Active module is persisted per project and restored."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Nav Test Project",
        "stage": "Idea / MVP"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Switch active module to technology stack
    patch_resp = cli.patch(
        f"/api/projects/{project_id}/active-module",
        json={"active_module": "tech_stack"},
        headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["active_module"] == "tech_stack"

    # Fetch project again: active module must be tech_stack
    get_resp = cli.get(f"/api/projects/{project_id}")
    assert get_resp.json()["active_module"] == "tech_stack"

def test_workflow_13_14_15_pdf_exports_and_exclusions(primary_user):
    """Scenario 13, 14, 15: Module export, Full Project PDF export, strict exclusions."""
    cli = primary_user["client"]
    headers = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli.post("/api/projects", json={
        "name": "Exportable Enterprise Venture",
        "stage": "Growth",
        "industry": "CleanTech",
        "description": "Grid-scale battery optimization algorithms"
    }, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Add dummy copilot message (which MUST be excluded from PDF)
    cli.post(f"/api/projects/{project_id}/copilot/chat", json={
        "message": "Hello Copilot, this is confidential conversation."
    }, headers=headers)

    # 1. Module-specific PDF
    mod_pdf = cli.get(f"/api/projects/{project_id}/modules/overview/export/pdf")
    assert mod_pdf.status_code == 200
    assert mod_pdf.content.startswith(b"%PDF")
    assert len(mod_pdf.content) > 500

    # 2. Consolidated Full-Project PDF
    full_pdf = cli.get(f"/api/projects/{project_id}/export/pdf")
    assert full_pdf.status_code == 200
    assert full_pdf.content.startswith(b"%PDF")
    assert len(full_pdf.content) > 1000

    # Ensure confidential copilot text is NOT leaked in PDF raw text stream
    assert b"confidential conversation" not in full_pdf.content

def test_workflow_16_cross_user_security_isolation(primary_user, secondary_user):
    """Scenario 16: Verify User B cannot access or mutate User A's project."""
    cli_a = primary_user["client"]
    headers_a = {"X-CSRF-Token": primary_user["csrf_token"]}
    p_resp = cli_a.post("/api/projects", json={
        "name": "User A Proprietary IP",
        "stage": "Growth"
    }, headers=headers_a)
    assert p_resp.status_code == 201
    project_a_id = p_resp.json()["id"]

    # Attacker tries to read User A's project using secondary user's isolated client
    cli_b = secondary_user["client"]
    attacker_headers = {"X-CSRF-Token": secondary_user["csrf_token"]}

    # Attempt GET project
    unauth_get = cli_b.get(f"/api/projects/{project_a_id}")
    assert unauth_get.status_code in (403, 404), "Security failure: Attacker accessed another user's project!"

    # Attempt DELETE project
    unauth_del = cli_b.delete(f"/api/projects/{project_a_id}", headers=attacker_headers)
    assert unauth_del.status_code in (403, 404), "Security failure: Attacker deleted another user's project!"

    # Attempt GET PDF export
    unauth_pdf = cli_b.get(f"/api/projects/{project_a_id}/export/pdf")
    assert unauth_pdf.status_code in (403, 404), "Security failure: Attacker exported another user's project PDF!"

def test_workflow_17_disallowed_ai_chat_on_validator_and_market_research():
    """Scenario 17: Section AI modification MUST be rejected on Idea Validator and Market Research."""
    cli = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    reg_resp = cli.post("/api/auth/register", json={
        "username": f"user_ai_{uid}",
        "email": f"user_ai_{uid}@enterprise.io",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True,
        "privacy_accepted": True
    })
    assert reg_resp.status_code == 201
    headers = {"X-CSRF-Token": reg_resp.json()["csrf_token"]}

    p_resp = cli.post("/api/projects", json={"name": "Rule 21 Check", "stage": "Idea / MVP"}, headers=headers)
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # Test Idea Validator modification attempt
    r_val = cli.post(f"/api/projects/{project_id}/modules/idea_validator/modify", json={
        "instruction": "Change problem clarity"
    }, headers=headers)
    assert r_val.status_code == 400
    assert "disabled" in r_val.json()["detail"].lower()

    # Test Market Research modification attempt
    r_mkt = cli.post(f"/api/projects/{project_id}/modules/market_research/modify", json={
        "instruction": "Change competitor profile"
    }, headers=headers)
    assert r_mkt.status_code == 400
    assert "disabled" in r_mkt.json()["detail"].lower()
