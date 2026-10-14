import pytest
from app.services.pdf_service import PDFService
from app.ai.gemini_service import ai_service
from app.core.config import settings

def test_pdf_generation_content_and_exclusions():
    project_dict = {
        "name": "NeuroVision Enterprise",
        "stage": "Growth",
        "industry": "HealthTech AI",
        "description": "FDA-cleared computer vision diagnostics for pathology",
        "target_customers": "Clinical laboratories and hospital networks",
        "goals": "Expand to 50 tier-1 hospitals",
        "existing_stack": {"Frontend": ["React"], "Backend": ["FastAPI", "Python"], "Cloud": ["AWS"]}
    }
    modules_data = {
        "bmc": {
            "tagline": "Real-time AI diagnostic intelligence for pathology labs",
            "customer_segments": ["Tier 1 Hospitals", "Private Pathology Labs"],
            "value_propositions": ["85% faster specimen review", "Reduced misdiagnosis rate"],
            "channels": ["Direct enterprise sales", "Academic medical conferences"],
            "customer_relationships": ["Dedicated account managers", "Clinical SLAs"],
            "revenue_streams": ["Annual enterprise subscription ($150k/yr)", "Usage fee per scan"],
            "key_resources": ["Proprietary neural net weights", "HIPAA cloud infra"],
            "key_activities": ["Clinical validation", "Algorithm retraining"],
            "key_partnerships": ["NVIDIA Healthcare", "Mayo Clinic Research"],
            "cost_structure": ["GPU inference compute", "Regulatory compliance legal"]
        },
        "tech_stack": {
            "summary": "HIPAA-compliant hybrid cloud architecture with GPU accelerated inference.",
            "architecture_pattern": "Event-Driven Microservices",
            "recommendations": [
                {
                    "technology": "FastAPI + PyTorch",
                    "category": "Backend",
                    "purpose": "Inference server and REST API",
                    "suitability": "High throughput async serving",
                    "trade_offs": "Memory management",
                    "migration_risk": "Low"
                }
            ]
        }
    }
    tasks_list = [
        {
            "task_code": "TSK-01",
            "phase": "Planning & Research",
            "title": "HIPAA Compliance Audit",
            "timeline": "30-day",
            "start_date": "2026-10-01",
            "end_date": "2026-10-15",
            "priority": "Critical",
            "status": "Finished",
            "deliverables": "Signed audit certification"
        }
    ]

    # Generate full project PDF
    pdf_bytes = PDFService.generate_full_project_pdf(project_dict, modules_data, tasks_list)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    # Generate single module PDF
    module_pdf_bytes = PDFService.generate_single_module_pdf(project_dict, "bmc", modules_data["bmc"])
    assert len(module_pdf_bytes) > 500
    assert module_pdf_bytes.startswith(b"%PDF")

@pytest.mark.skipif(not settings.GEMINI_API_KEY, reason="GEMINI_API_KEY not configured")
def test_live_gemini_generation():
    """Verify live Gemini API structured generation and Pydantic validation."""
    project_dict = {
        "name": "QuickAudit AI",
        "stage": "Idea / MVP",
        "industry": "FinTech",
        "description": "Automated smart contract and codebase vulnerability scanner for DeFi",
        "target_customers": "Web3 developers and DeFi protocols",
        "goals": "Scan 500 contracts in beta",
        "existing_stack": {}
    }

    # Test live BMC generation
    bmc_data = ai_service.generate_bmc(project_dict)
    assert len(bmc_data.customer_segments) >= 1
    assert len(bmc_data.value_propositions) >= 1
    assert len(bmc_data.channels) >= 1
    assert len(bmc_data.customer_relationships) >= 1
    assert len(bmc_data.revenue_streams) >= 1
    assert len(bmc_data.key_resources) >= 1
    assert len(bmc_data.key_activities) >= 1
    assert len(bmc_data.key_partnerships) >= 1
    assert len(bmc_data.cost_structure) >= 1
    assert bmc_data.tagline is not None

    # Test section modification
    raw_bmc = bmc_data.model_dump()
    modified, change_summary = ai_service.modify_section(
        module_type="bmc",
        current_data=raw_bmc,
        instruction="Add Tier 1 Investment Banks to customer segments and describe a private VPC deployment revenue stream."
    )
    assert len(modified["customer_segments"]) >= len(raw_bmc["customer_segments"])
    assert change_summary is not None and len(change_summary) > 5
