from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class StartupCostItem(BaseModel):
    category: str = Field(..., max_length=64)  # equipment, legal, initial_inventory, licenses, marketing, other
    item: str = Field(..., max_length=128)
    amount: float = Field(..., ge=0.0)
    is_confirmed: bool = Field(default=False)

class FixedCostItem(BaseModel):
    category: str = Field(..., max_length=64)  # rent, software, salaries, insurance, utilities, other
    item: str = Field(..., max_length=128)
    monthly_amount: float = Field(..., ge=0.0)
    frequency: str = Field(default="monthly", max_length=32)

class VariableCostItem(BaseModel):
    item: str = Field(..., max_length=128)
    unit_cost: float = Field(..., ge=0.0)
    notes: Optional[str] = None

class RevenueModelConfig(BaseModel):
    model_type: str = Field(default="per_unit", max_length=64)  # per_unit, subscription, service_fee, hourly, custom
    price_per_unit: float = Field(default=0.0, ge=0.0)
    expected_volume_monthly: Optional[float] = Field(default=None, ge=0.0)

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

class FinancialWorksheetBase(BaseModel):
    currency: str = Field(default="USD", max_length=8)
    startup_costs: List[StartupCostItem] = Field(default_factory=list)
    fixed_costs: List[FixedCostItem] = Field(default_factory=list)
    variable_costs: List[VariableCostItem] = Field(default_factory=list)
    revenue_model: RevenueModelConfig = Field(default_factory=RevenueModelConfig)
    cash_available: float = Field(default=0.0, ge=0.0)

class FinancialWorksheetUpdate(BaseModel):
    currency: Optional[str] = None
    startup_costs: Optional[List[StartupCostItem]] = None
    fixed_costs: Optional[List[FixedCostItem]] = None
    variable_costs: Optional[List[VariableCostItem]] = None
    revenue_model: Optional[RevenueModelConfig] = None
    cash_available: Optional[float] = None

class FinancialWorksheetResponse(FinancialWorksheetBase):
    id: str
    project_id: str
    metrics: FinancialMetrics
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
