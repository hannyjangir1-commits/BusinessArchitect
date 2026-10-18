"""Offline unit coverage for grounded research and citation handling."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.ai.gemini_service import GeminiAIService
from app.schemas.modules import GenerationBrief, MarketResearchData, ResearchSource


def _market_payload():
    return {
        "provenance_note": "Grounded research result.",
        "target_market_size": "Not verified from this source set.",
        "customer_needs": ["PCB teams need collaborative design review."],
        "competitor_profiles": [{
            "name": "Example EDA Vendor",
            "strengths": ["Established design tooling"],
            "weaknesses": ["The source does not establish a weakness"],
            "pricing_model": "See cited vendor pricing page",
            "market_share_estimate": "Not verified",
            "sources": ["https://example.com/vendor"],
            "as_of_date": "2026-10-18",
            "is_direct_competitor": True,
        }],
        "competitive_positioning": "A positioning hypothesis to validate with buyers.",
        "differentiation_factors": ["Test import compatibility with customer files."],
        "late_entry_differentiation": "Start with one underserved workflow.",
        "budget_fit_analysis": "No cost benchmarks were returned.",
        "opportunities": ["Validate demand among electronics teams."],
        "threats": ["Established tools may already meet the need."],
        "research_gaps": [],
    }


def _brief():
    return GenerationBrief(venture_summary="Collaborative PCB design", technical_depth="deep_technical")


def test_grounded_executor_requests_search_and_extracts_url_citations():
    service = GeminiAIService()
    service.api_key = "test-key"
    citation = SimpleNamespace(type="url_citation", url="https://example.com/market", title="Market Source")
    content = SimpleNamespace(annotations=[citation])
    step = SimpleNamespace(type="model_output", content=[content])
    interaction = SimpleNamespace(output_text='{"ok": true}', steps=[step])
    create = Mock(return_value=interaction)
    fake_client = SimpleNamespace(interactions=SimpleNamespace(create=create))

    with patch.object(service, "_get_client", return_value=fake_client):
        parsed, sources = service._execute_grounded_json_prompt(
            "system", "research this", MarketResearchData
        )

    assert parsed == {"ok": True}
    assert sources == [ResearchSource(title="Market Source", url="https://example.com/market")]
    kwargs = create.call_args.kwargs
    assert kwargs["tools"] == [{"type": "google_search"}]
    assert kwargs["store"] is False
    assert kwargs["response_format"]["mime_type"] == "application/json"


def test_market_research_keeps_only_cited_competitor_source_urls():
    service = GeminiAIService()
    service.api_key = "test-key"
    payload = _market_payload()
    payload["competitor_profiles"][0]["sources"] = [
        "https://example.com/vendor",
        "Invented source title",
        "https://unrelated.example/fake",
    ]
    source = ResearchSource(title="Vendor documentation", url="https://example.com/vendor")

    with patch.object(service, "_execute_grounded_json_prompt", return_value=(payload, [source])):
        result = service.generate_market_research(
            {"name": "CircuitCraft", "industry": "EDA", "stage": "Idea"},
            brief=_brief(),
        )

    assert result.source_references == [source]
    assert result.competitor_profiles[0].sources == ["https://example.com/vendor"]


def test_market_research_discards_claims_when_search_returns_no_citations():
    service = GeminiAIService()
    service.api_key = "test-key"
    payload = _market_payload()
    payload["target_market_size"] = "A $900 billion market growing at 24% CAGR."
    payload["competitor_profiles"][0]["name"] = "Unverified Competitor"

    with patch.object(service, "_execute_grounded_json_prompt", return_value=(payload, [])):
        result = service.generate_market_research(
            {"name": "CircuitCraft", "industry": "EDA", "stage": "Idea"},
            brief=_brief(),
        )

    assert result.competitor_profiles == []
    assert "not verified" in result.target_market_size.lower()
    assert "$900 billion" not in result.target_market_size
    assert "removed" in result.provenance_note.lower()
    assert any("no source citations" in gap.lower() for gap in result.research_gaps)


def test_offline_validator_score_responds_to_input_quality_and_labels_evidence_limits():
    service = GeminiAIService()
    sparse = service.generate_idea_validator({"name": "Project", "stage": "Idea"})
    detailed = service.generate_idea_validator({
        "name": "CircuitCraft",
        "stage": "Idea",
        "description": "Collaborative PCB design software for electronics teams that reduces repeated review cycles.",
        "target_customers": "Electronics students and PCB design companies",
        "goals": "Test customer demand through design partner interviews",
    })

    assert 0 <= sparse.score <= 100
    assert detailed.score > sparse.score
    assert detailed.score_factors["problem_clarity"] > sparse.score_factors["problem_clarity"]
    assert "no live market" in detailed.evidence_note.lower()
    assert detailed.source_references == []


def test_offline_tech_review_preserves_supplied_stack_without_claiming_compatibility():
    service = GeminiAIService()
    result = service.generate_tech_stack({
        "name": "CircuitCraft",
        "industry": "EDA Software",
        "stage": "Idea",
        "existing_stack": {"frontend": ["React"], "backend": ["FastAPI"]},
    })

    evaluation = result.existing_stack_evaluation
    assert evaluation["evaluation_status"] == "not_verified_offline"
    assert evaluation["existing_components"] == ["frontend: React", "backend: FastAPI"]
    assert evaluation["compatible_elements"] == []
    assert evaluation["incompatible_or_redundant"] == []
    assert "cannot verify" in evaluation["migration_trade_offs"].lower()
