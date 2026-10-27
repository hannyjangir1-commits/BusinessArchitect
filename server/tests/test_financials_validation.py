import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import FinancialWorksheet
from app.services.financial_calculator import FinancialCalculator, calculate_financial_metrics

client = TestClient(app)

def create_user_and_project():
    uid = uuid.uuid4().hex[:8]
    user_data = {
        "username": f"fin_user_{uid}",
        "email": f"fin_{uid}@example.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    }
    resp = client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201, resp.text
    csrf = resp.json()["csrf_token"]

    proj_data = {
        "name": f"FinTech Proj {uid}",
        "stage": "MVP",
        "industry": "FinTech",
        "description": "Deterministic unit economics planner",
        "target_customers": "Startup CFOs",
        "goals": "Scale runway modeling"
    }
    proj_resp = client.post("/api/projects", json=proj_data, headers={"X-CSRF-Token": csrf})
    assert proj_resp.status_code == 201, proj_resp.text
    return proj_resp.json()["id"], csrf


def test_get_financials_is_strictly_non_mutating():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    # Verify no worksheet exists in DB
    with SessionLocal() as db:
        initial_ws = db.query(FinancialWorksheet).filter(FinancialWorksheet.project_id == project_id).first()
        assert initial_ws is None

    # Call GET /financials
    get_resp = client.get(f"/api/projects/{project_id}/financials", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    body = get_resp.json()
    assert body["project_id"] == project_id
    assert "metrics" in body
    assert body["currency"] == "USD"

    # Assert that GET did NOT write any record to the database!
    with SessionLocal() as db:
        after_get_ws = db.query(FinancialWorksheet).filter(FinancialWorksheet.project_id == project_id).first()
        assert after_get_ws is None


def test_put_financials_atomic_upsert_and_metrics():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    update_payload = {
        "currency": "EUR",
        "startup_costs": [
            {"category": "equipment", "item": "Cloud server cluster", "amount": 1200.0, "is_confirmed": True},
            {"category": "legal", "item": "Corporate incorporation", "amount": 800.0, "is_confirmed": True}
        ],
        "fixed_costs": [
            {"category": "rent", "item": "Co-working space", "monthly_amount": 500.0, "frequency": "monthly"},
            {"category": "software", "item": "Security audit suite", "monthly_amount": 1200.0, "frequency": "annual"}
        ],
        "variable_costs": [
            {"item": "API compute inference fee", "unit_cost": 5.0},
            {"item": "Data ingress egress bandwidth", "unit_cost": 3.0}
        ],
        "revenue_model": {
            "model_type": "per_unit",
            "price_per_unit": 20.0,
            "expected_volume_monthly": 100.0
        },
        "cash_available": 10000.0
    }

    put_resp = client.put(f"/api/projects/{project_id}/financials", json=update_payload, headers=headers)
    assert put_resp.status_code == 200, put_resp.text
    res = put_resp.json()

    # Total startup = 1200 + 800 = 2000
    assert res["metrics"]["total_startup_cost"] == 2000.0

    # Monthly fixed = 500 (monthly) + 1200/12 (annual) = 600.0
    assert res["metrics"]["monthly_fixed_cost"] == 600.0
    assert res["metrics"]["fixed_cost_burn"] == 600.0

    # Unit variable = 5 + 3 = 8.0
    assert res["metrics"]["unit_variable_cost"] == 8.0

    # Unit contribution margin = 20 - 8 = 12.0
    assert res["metrics"]["unit_contribution_margin"] == 12.0
    # Margin ratio = (12 / 20) * 100 = 60.0%
    assert res["metrics"]["contribution_margin_ratio"] == 60.0

    # Break-even units = ceil(600 / 12) = 50 units
    assert res["metrics"]["breakeven_units_monthly"] == 50
    # Break-even revenue = 50 * 20 = 1000.0
    assert res["metrics"]["breakeven_revenue_monthly"] == 1000.0

    # Operational calculations:
    # monthly_operating_revenue = 20.0 * 100.0 = 2000.0
    assert res["metrics"]["monthly_operating_revenue"] == 2000.0
    # total_operating_variable = 8.0 * 100.0 = 800.0
    # monthly_operating_result = 2000 - 800 - 600 = 600.0 (profitable!)
    assert res["metrics"]["monthly_operating_result"] == 600.0
    # monthly_net_burn = max(0, -600) = 0.0
    assert res["metrics"]["monthly_net_burn"] == 0.0
    # sales_coverage_runway_months is None because operation is profitable
    assert res["metrics"]["sales_coverage_runway_months"] is None

    # Verify persisted in database
    with SessionLocal() as db:
        ws = db.query(FinancialWorksheet).filter(FinancialWorksheet.project_id == project_id).first()
        assert ws is not None
        assert ws.currency == "EUR"
        assert len(ws.startup_costs) == 2


def test_financials_negative_cashflow_burn_and_runway():
    # Unit margin is positive (price $15, unit cost $10 -> margin $5)
    # Fixed costs = $1,000
    # Expected volume = 100 units -> operating revenue $1,500, variable $1,000
    # Operating result = 1500 - 1000 - 1000 = -$500/mo (net burn = $500/mo)
    # Cash available = $3,000 -> sales coverage runway = 3000 / 500 = 6.0 months
    # Fixed burn runway = 3000 / 1000 = 3.0 months
    metrics = calculate_financial_metrics(
        startup_costs=[],
        fixed_costs=[{"category": "rent", "item": "Office", "monthly_amount": 1000.0, "frequency": "monthly"}],
        variable_costs=[{"item": "Raw materials", "unit_cost": 10.0}],
        revenue_model={"price_per_unit": 15.0, "expected_volume_monthly": 100.0},
        cash_available=3000.0
    )
    assert metrics.monthly_fixed_cost == 1000.0
    assert metrics.monthly_operating_revenue == 1500.0
    assert metrics.monthly_operating_result == -500.0
    assert metrics.monthly_net_burn == 500.0
    assert metrics.fixed_cost_burn == 1000.0
    assert metrics.sales_coverage_runway_months == 6.0
    assert metrics.runway_months == 3.0


def test_financials_validation_rejects_nan_inf_negative():
    project_id, csrf = create_user_and_project()
    headers = {"X-CSRF-Token": csrf}

    # 1. Negative amount
    resp = client.put(
        f"/api/projects/{project_id}/financials",
        json={"startup_costs": [{"category": "other", "item": "Tool", "amount": -100.0}]},
        headers=headers
    )
    assert resp.status_code == 422

    # 2. NaN amount
    resp_nan = client.put(
        f"/api/projects/{project_id}/financials",
        json={"cash_available": "NaN"},
        headers=headers
    )
    assert resp_nan.status_code == 422

    # 3. Infinity amount
    resp_inf = client.put(
        f"/api/projects/{project_id}/financials",
        json={"cash_available": "Infinity"},
        headers=headers
    )
    assert resp_inf.status_code == 422

    # 4. Empty string item name
    resp_empty = client.put(
        f"/api/projects/{project_id}/financials",
        json={"startup_costs": [{"category": "other", "item": "", "amount": 50.0}]},
        headers=headers
    )
    assert resp_empty.status_code == 422
