import pytest
from unittest.mock import patch, MagicMock
from app.ai.gemini_service import GeminiAIService
from app.schemas.modules import BMCData
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_invalid_structured_output_recovery():
    """Verify that if Gemini output contains conversational text with embedded JSON, regex extracts it."""
    service = GeminiAIService()
    fake_response = MagicMock()
    fake_response.text = 'Certainly! Here is the business model canvas:\n{"tagline": "AI Cloud", "customer_segments": ["Devs"], "value_propositions": ["Speed"], "channels": ["Web"], "customer_relationships": ["Self-serve"], "revenue_streams": ["SaaS"], "key_resources": ["Code"], "key_activities": ["Dev"], "key_partnerships": ["AWS"], "cost_structure": ["Hosting"]}\nI hope this helps your venture!'

    with patch.object(service, '_get_client') as mock_client:
        mock_models = MagicMock()
        mock_models.generate_content.return_value = fake_response
        mock_client.return_value.models = mock_models

        parsed = service._execute_json_prompt("sys prompt", "user prompt")
        assert parsed["tagline"] == "AI Cloud"
        assert parsed["customer_segments"] == ["Devs"]

def test_total_gemini_failure_raises_clear_error_without_fabrication():
    """Verify that if all Gemini candidates fail (e.g. 503 / 429 / network failure), a clear RuntimeError is raised and NO fake data is returned."""
    service = GeminiAIService()
    with patch.object(service, '_get_client') as mock_client:
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("503 Model is currently experiencing high demand")
        mock_client.return_value.models = mock_models

        with pytest.raises(RuntimeError) as exc_info:
            service.generate_bmc({"name": "Test Venture"})
        
        assert "All Gemini generation attempts failed" in str(exc_info.value)

def test_failed_modification_preserves_existing_saved_version():
    """Verify that when section AI modification fails, previous active version is untouched."""
    # 1. Register user & project
    import uuid
    uid = uuid.uuid4().hex[:8]
    cli = TestClient(app)
    reg_resp = cli.post("/api/auth/register", json={
        "username": f"failtest_{uid}",
        "email": f"fail_{uid}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    })
    csrf = reg_resp.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    p_resp = cli.post("/api/projects", json={
        "name": "Safety Preservation Venture",
        "stage": "Idea / MVP"
    }, headers=headers)
    project_id = p_resp.json()["id"]

    # 2. Seed active version 1
    from app.db.session import SessionLocal
    from app.services.version_service import VersionService
    db = SessionLocal()
    try:
        mod = VersionService.get_or_create_module(db, project_id, "bmc")
        v1 = VersionService.save_new_version(db, mod, {
            "tagline": "Original Untouched Tagline",
            "customer_segments": ["Segment Original"],
            "value_propositions": ["Value Original"],
            "channels": ["Channel Original"],
            "customer_relationships": ["Rel Original"],
            "revenue_streams": ["Rev Original"],
            "key_resources": ["Res Original"],
            "key_activities": ["Act Original"],
            "key_partnerships": ["Part Original"],
            "cost_structure": ["Cost Original"]
        }, change_summary="Initial V1")
        v1_id = v1.id
    finally:
        db.close()

    # 3. Simulate Gemini throwing an error during AI modification
    with patch("app.api.modules.ai_service.modify_section", side_effect=RuntimeError("Gemini 503 Overloaded")):
        mod_resp = cli.post(f"/api/projects/{project_id}/modules/bmc/modify", json={
            "instruction": "Corrupt this version"
        }, headers=headers)
        
        # Must fail cleanly with 500
        assert mod_resp.status_code == 500
        assert "AI modification failed" in mod_resp.json()["detail"]

    # 4. Verify module in database STILL points to v1 and data is completely preserved
    db = SessionLocal()
    try:
        mod_after = VersionService.get_or_create_module(db, project_id, "bmc")
        assert mod_after.active_version_id == v1_id
        versions = VersionService.get_versions(db, mod_after.id)
        assert len(versions) == 1
        assert versions[0].data["tagline"] == "Original Untouched Tagline"
    finally:
        db.close()
