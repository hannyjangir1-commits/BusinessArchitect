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
    # The test patches the provider client; enable that path without a real key.
    service.api_key = "test-key"
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
    # The test patches the provider client; enable that path without a real key.
    service.api_key = "test-key"
    with patch.object(service, '_get_client') as mock_client:
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = Exception("503 Model is currently experiencing high demand")
        mock_client.return_value.models = mock_models

        with pytest.raises(RuntimeError) as exc_info:
            service.generate_bmc({"name": "Test Venture"})
        
        assert "All Gemini generation attempts failed" in str(exc_info.value)


class ProviderQuotaError(Exception):
    code = 429


def test_quota_failure_stops_model_fallback_and_returns_actionable_error():
    service = GeminiAIService()
    service.api_key = "test-key"
    with patch.object(service, "_get_client") as mock_client, patch.object(
        service, "_get_candidate_models", return_value=["configured-model", "fallback-model"]
    ):
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")
        mock_client.return_value.models = mock_models

        with pytest.raises(RuntimeError, match="quota is exhausted"):
            service._execute_json_prompt("system", "user")

        assert mock_models.generate_content.call_count == 1


def test_brief_quota_failure_is_not_hidden_by_deterministic_fallback():
    service = GeminiAIService()
    service.api_key = "test-key"
    with patch.object(service, "_execute_json_prompt", side_effect=ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")) as generate:
        with pytest.raises(RuntimeError, match="quota is exhausted"):
            service.build_generation_brief({"name": "Test venture", "stage": "Idea"}, "bmc")

        generate.assert_called_once()


def test_grounded_quota_failure_does_not_try_another_model():
    service = GeminiAIService()
    service.api_key = "test-key"
    with patch.object(service, "_get_client") as mock_client, patch.object(
        service, "_get_candidate_models", return_value=["configured-model", "fallback-model"]
    ):
        mock_interactions = MagicMock()
        mock_interactions.create.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")
        mock_client.return_value.interactions = mock_interactions

        with pytest.raises(RuntimeError, match="quota is exhausted"):
            service._execute_grounded_json_prompt("system", "user", BMCData)

        assert mock_interactions.create.call_count == 1


def test_copilot_quota_failure_is_not_hidden_by_offline_fallback():
    service = GeminiAIService()
    service.api_key = "test-key"
    with patch.object(service, "_get_client") as mock_client, patch.object(
        service, "_get_candidate_models", return_value=["configured-model", "fallback-model"]
    ):
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = ProviderQuotaError("RESOURCE_EXHAUSTED: quota exceeded")
        mock_client.return_value.models = mock_models

        with pytest.raises(RuntimeError, match="quota is exhausted"):
            service.chat_copilot({"name": "Test", "stage": "Idea"}, [], "How should I launch?")

        assert mock_models.generate_content.call_count == 1


def test_quota_generation_failure_is_not_marked_immediately_retryable():
    import uuid
    from app.db.session import SessionLocal
    from app.models.all_models import AIOperation

    cli = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    reg_resp = cli.post("/api/auth/register", json={
        "username": f"quota_{uid}",
        "email": f"quota_{uid}@venture.io",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True,
    })
    assert reg_resp.status_code == 201
    headers = {"X-CSRF-Token": reg_resp.json()["csrf_token"]}
    project_resp = cli.post("/api/projects", json={
        "name": "Quota Test Venture",
        "description": "A realistic project description for an early business planning workspace.",
        "industry": "Business Software",
        "target_customers": "Small operations teams",
        "goals": "Validate the first customer workflow",
        "stage": "Idea",
    }, headers=headers)
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    provider_failure = RuntimeError(
        "The configured generation provider is rate-limited or its quota is exhausted. "
        "Check the provider account's usage and billing limits, then retry after the limit resets."
    )
    with patch("app.api.modules.ai_service.generate_bmc", side_effect=provider_failure):
        response = cli.post(f"/api/projects/{project_id}/modules/bmc/generate", headers=headers)

    assert response.status_code == 500
    assert "quota is exhausted" in response.json()["detail"]
    db = SessionLocal()
    try:
        operation = db.query(AIOperation).filter(AIOperation.project_id == project_id).order_by(AIOperation.created_at.desc()).first()
        assert operation is not None
        assert operation.error_category == "provider_error"
        assert operation.is_retryable is False
        assert "usage and billing limits" in operation.error_message
    finally:
        db.close()

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
        
        # Must fail cleanly with 500 without exposing a fabricated replacement
        assert mod_resp.status_code == 500
        assert "Module update failed" in mod_resp.json()["detail"]

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
