import math
from typing import Dict, Any, List, Optional
from app.schemas.financials import FinancialMetrics

def calculate_financial_metrics(
    startup_costs: List[Dict[str, Any]],
    fixed_costs: List[Dict[str, Any]],
    variable_costs: List[Dict[str, Any]],
    revenue_model: Dict[str, Any],
    cash_available: float = 0.0
) -> FinancialMetrics:
    """Deterministic financial formula calculations in application code (never generated arithmetic)."""
    # 1. Total Startup Costs
    total_startup = sum(float(item.get("amount", 0.0) or 0.0) for item in startup_costs)

    # 2. Monthly Fixed Costs
    monthly_fixed = 0.0
    for item in fixed_costs:
        amount = float(item.get("monthly_amount", 0.0) or 0.0)
        freq = str(item.get("frequency", "monthly")).lower()
        if freq == "annual" or freq == "yearly":
            monthly_fixed += amount / 12.0
        elif freq == "quarterly":
            monthly_fixed += amount / 3.0
        elif freq == "weekly":
            monthly_fixed += amount * 4.333
        else:
            monthly_fixed += amount

    # 3. Unit Variable Cost
    unit_variable = sum(float(item.get("unit_cost", 0.0) or 0.0) for item in variable_costs)

    # 4. Price per unit & Contribution Margin
    price = float(revenue_model.get("price_per_unit", 0.0) or 0.0)
    unit_margin = round(price - unit_variable, 2)
    margin_ratio = round((unit_margin / price) * 100.0, 2) if price > 0 else 0.0

    # 5. Break-Even Calculations
    breakeven_units: Optional[int] = None
    breakeven_revenue: Optional[float] = None
    if unit_margin > 0.0 and monthly_fixed > 0.0:
        breakeven_units = math.ceil(monthly_fixed / unit_margin)
        breakeven_revenue = round(breakeven_units * price, 2)

    # 6. Authoritative Unit Economics & Operating Calculations
    # revenue = price * expected_volume_monthly
    # variable_cost = unit_cost * expected_volume_monthly
    # operating_result = revenue - variable - fixed
    # net_burn = max(0, -operating_result)
    # fixed_burn = fixed_costs
    expected_vol = float(revenue_model.get("expected_volume_monthly") or 0.0)
    monthly_operating_revenue = round(price * expected_vol, 2)
    total_operating_variable = round(unit_variable * expected_vol, 2)
    monthly_operating_result = round(monthly_operating_revenue - total_operating_variable - monthly_fixed, 2)
    monthly_net_burn = round(max(0.0, -monthly_operating_result), 2)
    fixed_cost_burn = round(monthly_fixed, 2)

    # 7. Burn Rate & Runway
    monthly_burn = round(monthly_fixed, 2)
    runway_months: Optional[float] = None
    if monthly_burn > 0.0 and cash_available > 0.0:
        runway_months = round(cash_available / monthly_burn, 1)

    sales_coverage_runway_months: Optional[float] = None
    if cash_available > 0.0:
        if monthly_net_burn > 0.0:
            sales_coverage_runway_months = round(cash_available / monthly_net_burn, 1)
        elif monthly_operating_result >= 0.0 and expected_vol > 0.0:
            sales_coverage_runway_months = None

    return FinancialMetrics(
        total_startup_cost=round(total_startup, 2),
        monthly_fixed_cost=round(monthly_fixed, 2),
        unit_variable_cost=round(unit_variable, 2),
        price_per_unit=round(price, 2),
        unit_contribution_margin=unit_margin,
        contribution_margin_ratio=margin_ratio,
        breakeven_units_monthly=breakeven_units,
        breakeven_revenue_monthly=breakeven_revenue,
        monthly_burn_rate=monthly_burn,
        runway_months=runway_months,
        monthly_net_burn=monthly_net_burn,
        monthly_operating_revenue=monthly_operating_revenue,
        monthly_operating_result=monthly_operating_result,
        fixed_cost_burn=fixed_cost_burn,
        sales_coverage_runway_months=sales_coverage_runway_months
    )


class FinancialCalculator:
    @staticmethod
    def calculate(
        startup_costs: Optional[List[Dict[str, Any]]] = None,
        fixed_costs: Optional[List[Dict[str, Any]]] = None,
        variable_costs: Optional[List[Dict[str, Any]]] = None,
        revenue_model: Optional[Dict[str, Any]] = None,
        cash_available: float = 0.0
    ) -> Dict[str, Any]:
        s_costs = startup_costs or []
        f_costs = fixed_costs or []
        v_costs = []
        for vc in (variable_costs or []):
            item = dict(vc)
            if "cost_per_unit" in item and "unit_cost" not in item:
                item["unit_cost"] = item["cost_per_unit"]
            v_costs.append(item)
        r_model = dict(revenue_model or {})
        if "selling_price_per_unit" in r_model and "price_per_unit" not in r_model:
            r_model["price_per_unit"] = r_model["selling_price_per_unit"]

        metrics = calculate_financial_metrics(s_costs, f_costs, v_costs, r_model, cash_available)
        res = metrics.model_dump()
        # Add aliases for test and template convenience
        res["total_startup_costs"] = res["total_startup_cost"]
        res["monthly_fixed_costs"] = res["monthly_fixed_cost"]
        res["variable_cost_per_unit"] = res["unit_variable_cost"]
        res["break_even_units_per_month"] = res["breakeven_units_monthly"]
        res["break_even_revenue_per_month"] = res["breakeven_revenue_monthly"]
        res["monthly_net_burn"] = res["monthly_burn_rate"]
        return res
