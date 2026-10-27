import math
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

class StartupCostItem(BaseModel):
    category: str = Field(..., max_length=64)  # equipment, legal, initial_inventory, licenses, marketing, other
    item: str = Field(..., min_length=1, max_length=128)
    amount: float = Field(..., ge=0.0, allow_inf_nan=False)
    is_confirmed: bool = Field(default=False)

    @field_validator("amount", mode="after")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError("Amount must be a non-negative finite number.")
        return v

class FixedCostItem(BaseModel):
    category: str = Field(..., max_length=64)  # rent, software, salaries, insurance, utilities, other
    item: str = Field(..., min_length=1, max_length=128)
    monthly_amount: float = Field(..., ge=0.0, allow_inf_nan=False)
    frequency: str = Field(default="monthly", max_length=32)

    @field_validator("monthly_amount", mode="after")
    @classmethod
    def validate_monthly_amount(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError("Monthly amount must be a non-negative finite number.")
        return v

class VariableCostItem(BaseModel):
    item: str = Field(..., min_length=1, max_length=128)
    unit_cost: float = Field(..., ge=0.0, allow_inf_nan=False)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("unit_cost", mode="after")
    @classmethod
    def validate_unit_cost(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError("Unit cost must be a non-negative finite number.")
        return v

class RevenueModelConfig(BaseModel):
    model_type: str = Field(default="per_unit", max_length=64)  # per_unit, subscription, service_fee, hourly, custom
    price_per_unit: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    expected_volume_monthly: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False)

    @field_validator("price_per_unit", "expected_volume_monthly", mode="after")
    @classmethod
    def validate_revenue_floats(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (not math.isfinite(v) or v < 0.0):
            raise ValueError("Revenue model numbers must be non-negative finite numbers.")
        return v

class FinancialMetrics(BaseModel):
    total_startup_cost: float
    monthly_fixed_cost: float
    unit_variable_cost: float
    price_per_unit: float
    unit_contribution_margin: float
    contribution_margin_ratio: float
    breakeven_units_monthly: Optional[int] = None
    breakeven_revenue_monthly: Optional[float] = None
    monthly_burn_rate: float
    runway_months: Optional[float] = None
    monthly_net_burn: float = 0.0
    monthly_operating_revenue: float = 0.0
    monthly_operating_result: float = 0.0
    fixed_cost_burn: float = 0.0
    sales_coverage_runway_months: Optional[float] = None

class FinancialWorksheetBase(BaseModel):
    currency: str = Field(default="USD", min_length=1, max_length=8)
    startup_costs: List[StartupCostItem] = Field(default_factory=list, max_length=200)
    fixed_costs: List[FixedCostItem] = Field(default_factory=list, max_length=200)
    variable_costs: List[VariableCostItem] = Field(default_factory=list, max_length=200)
    revenue_model: RevenueModelConfig = Field(default_factory=RevenueModelConfig)
    cash_available: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)

    @field_validator("cash_available", mode="after")
    @classmethod
    def validate_cash_available(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError("Cash available must be a non-negative finite number.")
        return v

class FinancialWorksheetUpdate(BaseModel):
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    startup_costs: Optional[List[StartupCostItem]] = Field(default=None, max_length=200)
    fixed_costs: Optional[List[FixedCostItem]] = Field(default=None, max_length=200)
    variable_costs: Optional[List[VariableCostItem]] = Field(default=None, max_length=200)
    revenue_model: Optional[RevenueModelConfig] = None
    cash_available: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False)

    @field_validator("cash_available", mode="after")
    @classmethod
    def validate_update_cash(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (not math.isfinite(v) or v < 0.0):
            raise ValueError("Cash available must be a non-negative finite number.")
        return v

class FinancialWorksheetResponse(FinancialWorksheetBase):
    id: str
    project_id: str
    metrics: FinancialMetrics
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
