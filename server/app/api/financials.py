from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, FinancialWorksheet
from app.schemas.financials import (
    FinancialWorksheetUpdate, FinancialWorksheetResponse,
    StartupCostItem, FixedCostItem, VariableCostItem, RevenueModelConfig
)
from app.services.financial_calculator import calculate_financial_metrics
from app.api.deps import get_user_project, verify_csrf

router = APIRouter(prefix="/projects/{project_id}/financials", tags=["Financial Worksheet"])

def _get_or_create_worksheet(project: Project, db: Session) -> FinancialWorksheet:
    ws = db.query(FinancialWorksheet).filter(FinancialWorksheet.project_id == project.id).first()
    if not ws:
        ws = FinancialWorksheet(
            project_id=project.id,
            currency="USD",
            startup_costs=[],
            fixed_costs=[],
            variable_costs=[],
            revenue_model={"model_type": "per_unit", "price_per_unit": 0.0},
            cash_available=0.0
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
    return ws

def _format_response(ws: FinancialWorksheet) -> FinancialWorksheetResponse:
    metrics = calculate_financial_metrics(
        startup_costs=ws.startup_costs or [],
        fixed_costs=ws.fixed_costs or [],
        variable_costs=ws.variable_costs or [],
        revenue_model=ws.revenue_model or {},
        cash_available=ws.cash_available or 0.0
    )
    return FinancialWorksheetResponse(
        id=ws.id,
        project_id=ws.project_id,
        currency=ws.currency,
        startup_costs=[StartupCostItem.model_validate(c) for c in (ws.startup_costs or [])],
        fixed_costs=[FixedCostItem.model_validate(c) for c in (ws.fixed_costs or [])],
        variable_costs=[VariableCostItem.model_validate(c) for c in (ws.variable_costs or [])],
        revenue_model=RevenueModelConfig.model_validate(ws.revenue_model or {}),
        cash_available=ws.cash_available,
        metrics=metrics,
        created_at=ws.created_at,
        updated_at=ws.updated_at
    )

@router.get("", response_model=FinancialWorksheetResponse)
def get_financial_worksheet(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    ws = _get_or_create_worksheet(project, db)
    return _format_response(ws)

@router.put("", response_model=FinancialWorksheetResponse, dependencies=[Depends(verify_csrf)])
def update_financial_worksheet(
    req: FinancialWorksheetUpdate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    ws = _get_or_create_worksheet(project, db)
    if req.currency is not None:
        ws.currency = req.currency
    if req.startup_costs is not None:
        ws.startup_costs = [c.model_dump() for c in req.startup_costs]
    if req.fixed_costs is not None:
        ws.fixed_costs = [c.model_dump() for c in req.fixed_costs]
    if req.variable_costs is not None:
        ws.variable_costs = [c.model_dump() for c in req.variable_costs]
    if req.revenue_model is not None:
        ws.revenue_model = req.revenue_model.model_dump()
    if req.cash_available is not None:
        ws.cash_available = req.cash_available

    ws.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ws)
    return _format_response(ws)
