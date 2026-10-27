"""Tests for Knowledge Items, Financial Worksheet, and Copilot Routing / Proposal Preview.

Verifies:
1. Knowledge Model: CRUD operations on ProjectKnowledgeItem and KnowledgeLink endpoints.
2. Financial Calculator: Deterministic math for startup costs, monthly burn, contribution margin, break-even units & revenue, runway.
3. Financial Worksheet API: GET default worksheet, PUT worksheet updates with calculated metrics.
4. Copilot 4-Route Classifier:
   - clearly_relevant
   - supporting_concept
   - ambiguous (returns short clarification)
   - unrelated_or_unauthorized (returns polite redirect)
   - context-aware security questions (e.g. login security) allowed
5. Copilot /propose Endpoint: Non-destructive preview proposal without modifying saved module content.
"""

import secrets
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, Session as DBSession, gen_id
)
from app.core.config import settings
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.services.financial_calculator import FinancialCalculator
from app.ai.gemini_service import ai_service


@pytest.fixture
def test_setup():
    uid = secrets.token_hex(4)
    with SessionLocal() as db:
        user = User(
            id=gen_id("usr_"),
            username=f"kc_user_{uid}",
            email=f"kc_{uid}@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_suspended=False
        )
        db.add(user)

        project = Project(
            id=gen_id("proj_"),
            name="Campus Bike Repair",
            user_id=user.id,
            stage="Idea",
            industry="Local Services",
            description="On-demand campus bicycle repair and tune-up service.",
            target_customers="College students and university commuters.",
            budget=2000.0,
            goals="Validate student willingness to pay and launch 2-week pilot."
        )
        db.add(project)

        # Add initial module and active version for propose testing
        module = ModuleContent(
            id=gen_id("mod_"),
            project_id=project.id,
            module_type="bmc",
            framework_type="standard_bmc"
        )
        db.add(module)
        ver = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=module.id,
            version_number=1,
            version_name="BMC V1",
            framework_type="standard_bmc",
            data={
                "value_propositions": ["Convenient on-campus repairs", "Quick turnaround"],
                "customer_segments": ["Students", "Faculty"],
                "revenue_streams": ["Flat fee per repair ($25)"],
                "cost_structure": ["Tools", "Replacement tubes"],
                "key_activities": ["Repair dispatch", "Tool maintenance"],
                "key_resources": ["Mobile repair kit"],
                "key_partners": ["Campus bike shop"],
                "channels": ["Flyers", "Campus group chats"],
                "customer_relationships": ["Direct service"]
            },
            is_active=True
        )
        db.add(ver)
        module.active_version_id = ver.id

        db.commit()

        # Create session
        token = generate_session_token()
        csrf = generate_csrf_token(token)
        session_rec = DBSession(
            id=gen_id("ses_"),
            user_id=user.id,
            session_token=token,
            expires_at=datetime.now(timezone.utc).replace(year=2030)
        )
        db.add(session_rec)
        db.commit()

        return {
            "user_id": user.id,
            "project_id": project.id,
            "session_token": token,
            "csrf_token": csrf
        }


def test_financial_calculator_pure_math():
    startup = [
        {"category": "equipment", "item": "Tool kit", "amount": 500.0, "is_confirmed": True},
        {"category": "marketing", "item": "Flyers", "amount": 100.0, "is_confirmed": False},
    ]
    fixed = [
        {"category": "software", "item": "Phone plan", "monthly_amount": 50.0},
        {"category": "storage", "item": "Locker rental", "monthly_amount": 150.0},
    ]
    variable = [
        {"item": "Replacement tube", "cost_per_unit": 5.0},
        {"item": "Brake pad set", "cost_per_unit": 3.0},
    ]
    rev_model = {
        "revenue_type": "per_unit",
        "selling_price_per_unit": 28.0,
        "estimated_monthly_units": 20.0
    }

    metrics = FinancialCalculator.calculate(
        startup_costs=startup,
        fixed_costs=fixed,
        variable_costs=variable,
        revenue_model=rev_model,
        cash_available=1500.0
    )

    assert metrics["total_startup_costs"] == 600.0
    assert metrics["monthly_fixed_costs"] == 200.0
    assert metrics["variable_cost_per_unit"] == 8.0
    # Unit contribution margin = 28 - 8 = 20
    assert metrics["unit_contribution_margin"] == 20.0
    # Margin ratio percentage = (20 / 28) * 100 ≈ 71.43
    assert abs(metrics["contribution_margin_ratio"] - 71.43) < 0.1
    # Break-even units = 200 / 20 = 10 units
    assert metrics["break_even_units_per_month"] == 10
    # Break-even revenue = 10 * 28 = 280
    assert metrics["break_even_revenue_per_month"] == 280.0
    assert metrics["monthly_net_burn"] == 200.0
    assert metrics["runway_months"] == 7.5


def test_financial_calculator_negative_cashflow_runway():
    metrics = FinancialCalculator.calculate(
        startup_costs=[],
        fixed_costs=[{"category": "rent", "item": "Space", "monthly_amount": 500.0}],
        variable_costs=[{"item": "Part", "cost_per_unit": 10.0}],
        revenue_model={"selling_price_per_unit": 20.0, "estimated_monthly_units": 10.0},
        cash_available=2000.0
    )
    assert metrics["monthly_fixed_costs"] == 500.0
    assert metrics["unit_contribution_margin"] == 10.0
    # Break even units = 500 / 10 = 50
    assert metrics["break_even_units_per_month"] == 50
    # Runway = 2000 / 500 = 4.0 months
    assert metrics["runway_months"] == 4.0


def test_financial_worksheet_api(test_setup):
    client = TestClient(app, cookies={settings.COOKIE_NAME: test_setup["session_token"]}, headers={"X-CSRF-Token": test_setup["csrf_token"]})
    p_id = test_setup["project_id"]

    # 1. Get initial worksheet
    res = client.get(f"/api/projects/{p_id}/financials")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == p_id
    assert "metrics" in data

    # 2. Update worksheet
    update_payload = {
        "currency": "USD",
        "startup_costs": [
            {"category": "equipment", "item": "Repair stand", "amount": 250.0, "is_confirmed": True}
        ],
        "fixed_costs": [
            {"category": "insurance", "item": "Liability insurance", "monthly_amount": 75.0}
        ],
        "variable_costs": [
            {"item": "Chain lube and cleaner", "unit_cost": 2.5}
        ],
        "revenue_model": {
            "model_type": "per_unit",
            "price_per_unit": 30.0,
            "expected_volume_monthly": 15.0
        },
        "cash_available": 1000.0
    }
    put_res = client.put(f"/api/projects/{p_id}/financials", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["metrics"]["total_startup_cost"] == 250.0
    assert updated["metrics"]["monthly_fixed_cost"] == 75.0
    assert updated["metrics"]["unit_variable_cost"] == 2.5
    assert updated["metrics"]["unit_contribution_margin"] == 27.5


def test_knowledge_model_api(test_setup):
    client = TestClient(app, cookies={settings.COOKIE_NAME: test_setup["session_token"]}, headers={"X-CSRF-Token": test_setup["csrf_token"]})
    p_id = test_setup["project_id"]

    # 1. Create Fact
    fact_res = client.post(
        f"/api/projects/{p_id}/knowledge",
        json={
            "item_type": "fact",
            "title": "Campus has 12,000 enrolled students",
            "content": "Official university demographic reports indicate 12k undergraduates.",
            "epistemic_status": "evidence_supported",
            "source_reference": "University Registrar 2025"
        }
    )
    assert fact_res.status_code == 201
    fact_id = fact_res.json()["id"]

    # 2. Create Assumption
    asmp_res = client.post(
        f"/api/projects/{p_id}/knowledge",
        json={
            "item_type": "assumption",
            "title": "Students will pay $25 per on-site repair",
            "content": "Convenience fee outweighs walking to off-campus bike shop.",
            "epistemic_status": "hypothesis"
        }
    )
    assert asmp_res.status_code == 201
    asmp_id = asmp_res.json()["id"]

    # 3. Create Link between Fact and Assumption
    link_res = client.post(
        f"/api/projects/{p_id}/knowledge/links",
        json={
            "source_id": fact_id,
            "target_id": asmp_id,
            "relationship": "supports"
        }
    )
    assert link_res.status_code == 201
    link_data = link_res.json()
    assert link_data["source_id"] == fact_id
    assert link_data["target_id"] == asmp_id

    # 4. List knowledge items
    list_res = client.get(f"/api/projects/{p_id}/knowledge")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 2
    item_map = {it["id"]: it for it in items}
    assert len(item_map[fact_id]["outgoing_links"]) == 1
    assert len(item_map[asmp_id]["incoming_links"]) == 1


def test_copilot_routing_decisions(test_setup):
    proj_info = {
        "name": "Campus Bike Repair",
        "industry": "Local Services",
        "description": "On-demand campus bicycle repair."
    }

    # 1. Clearly relevant
    dec1 = ai_service._scope_decision(proj_info, "How should we price our tune-up services for students?")
    assert dec1.allowed is True
    assert dec1.route == "clearly_relevant"

    # 2. Supporting concept
    dec2 = ai_service._scope_decision(proj_info, "What does gross margin mean?")
    assert dec2.allowed is True
    assert dec2.route == "supporting_concept"

    # 3. Ambiguous short fragment
    dec3 = ai_service._scope_decision(proj_info, "Why?")
    assert dec3.allowed is True
    assert dec3.route == "ambiguous"
    assert dec3.clarification_question is not None

    # 4. Clearly unrelated
    dec4 = ai_service._scope_decision(proj_info, "Tell me celebrity gossip and Hollywood drama.")
    assert dec4.allowed is False
    assert dec4.route == "unrelated_or_unauthorized"

    # 5. Security question about login (legitimate project inquiry)
    dec5 = ai_service._scope_decision(proj_info, "What security risks affect our login flow and credentials handling?")
    assert dec5.allowed is True
    assert dec5.route in ("clearly_relevant", "supporting_concept")

    # 6. chat_copilot returns polite redirect on unrelated
    reply = ai_service.chat_copilot(proj_info, [], "Give me a recipe for chocolate cake.")
    assert "I can help with this project's customers, business model, tools, research, and execution plan." in reply
    assert "Would you like help identifying your next project task?" in reply


def test_copilot_proposal_endpoint(test_setup):
    client = TestClient(app, cookies={settings.COOKIE_NAME: test_setup["session_token"]}, headers={"X-CSRF-Token": test_setup["csrf_token"]})
    p_id = test_setup["project_id"]

    # Propose change to BMC
    res = client.post(
        f"/api/projects/{p_id}/copilot/propose",
        json={
            "target_module": "bmc",
            "instruction": "Add a semester-long subscription model ($49/term) for student bike tune-ups."
        }
    )
    assert res.status_code == 200
    proposal = res.json()
    assert proposal["target_module"] == "bmc"
    assert "summary" in proposal
    assert "proposed_diff" in proposal
    assert proposal["requires_confirmation"] is True
    assert "proposed_content" in proposal

    # Verify that the actual module in DB was NOT modified by the proposal preview!
    with SessionLocal() as db:
        module = db.query(ModuleContent).filter(
            ModuleContent.project_id == p_id,
            ModuleContent.module_type == "bmc"
        ).first()
        ver = db.query(ModuleVersion).filter(
            ModuleVersion.module_content_id == module.id,
            ModuleVersion.is_active.is_(True)
        ).first()
        # Original content retained
        assert "Flat fee per repair ($25)" in ver.data["revenue_streams"]
        assert "$49/term" not in str(ver.data["revenue_streams"])
