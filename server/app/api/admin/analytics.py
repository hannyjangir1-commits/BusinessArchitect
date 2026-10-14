from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, RoadmapTask, AnalyticsEvent
)
from app.api.deps import require_admin

router = APIRouter(prefix="/analytics", tags=["Admin Product Analytics"])

@router.get("/overview")
def get_analytics_overview(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_projects = db.query(func.count(Project.id)).scalar() or 0

    # Module adoption counts
    bmc_projects = db.query(func.count(func.distinct(ModuleContent.project_id))).filter(ModuleContent.module_type == "bmc").scalar() or 0
    tech_projects = db.query(func.count(func.distinct(ModuleContent.project_id))).filter(ModuleContent.module_type == "tech_stack").scalar() or 0
    validator_projects = db.query(func.count(func.distinct(ModuleContent.project_id))).filter(ModuleContent.module_type == "idea_validator").scalar() or 0
    market_projects = db.query(func.count(func.distinct(ModuleContent.project_id))).filter(ModuleContent.module_type == "market_research").scalar() or 0
    roadmap_projects = db.query(func.count(func.distinct(RoadmapTask.project_id))).scalar() or 0

    # Export events count from analytics_events
    export_count = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.event_name.in_(["export_pdf", "export_completed"])
    ).scalar() or 0

    # 6-step conversion funnel
    # 1. Total Registered
    step1_registered = total_users
    # 2. Users with at least 1 project
    step2_created_proj = db.query(func.count(func.distinct(Project.user_id))).scalar() or 0
    # 3. Users with BMC
    step3_bmc = db.query(func.count(func.distinct(Project.user_id))).join(ModuleContent, Project.id == ModuleContent.project_id).filter(ModuleContent.module_type == "bmc").scalar() or 0
    # 4. Users with Tech Stack
    step4_tech = db.query(func.count(func.distinct(Project.user_id))).join(ModuleContent, Project.id == ModuleContent.project_id).filter(ModuleContent.module_type == "tech_stack").scalar() or 0
    # 5. Users with Roadmap
    step5_roadmap = db.query(func.count(func.distinct(Project.user_id))).join(RoadmapTask, Project.id == RoadmapTask.project_id).scalar() or 0
    # 6. Users with Export
    step6_export = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name.in_(["export_pdf", "export_completed"])).scalar() or 0

    funnel = [
        {"step": 1, "name": "Registered Users", "count": step1_registered, "conversion_rate": 100.0},
        {"step": 2, "name": "Created First Project", "count": step2_created_proj, "conversion_rate": round(step2_created_proj / step1_registered * 100, 1) if step1_registered > 0 else 0.0},
        {"step": 3, "name": "Generated BMC", "count": step3_bmc, "conversion_rate": round(step3_bmc / step1_registered * 100, 1) if step1_registered > 0 else 0.0},
        {"step": 4, "name": "Generated Tech Stack", "count": step4_tech, "conversion_rate": round(step4_tech / step1_registered * 100, 1) if step1_registered > 0 else 0.0},
        {"step": 5, "name": "Built Execution Roadmap", "count": step5_roadmap, "conversion_rate": round(step5_roadmap / step1_registered * 100, 1) if step1_registered > 0 else 0.0},
        {"step": 6, "name": "Exported Blueprint Report", "count": step6_export, "conversion_rate": round(step6_export / step1_registered * 100, 1) if step1_registered > 0 else 0.0}
    ]

    module_adoption = {
        "bmc": {"count": bmc_projects, "rate": round(bmc_projects / total_projects * 100, 1) if total_projects > 0 else 0.0},
        "tech_stack": {"count": tech_projects, "rate": round(tech_projects / total_projects * 100, 1) if total_projects > 0 else 0.0},
        "idea_validator": {"count": validator_projects, "rate": round(validator_projects / total_projects * 100, 1) if total_projects > 0 else 0.0},
        "market_research": {"count": market_projects, "rate": round(market_projects / total_projects * 100, 1) if total_projects > 0 else 0.0},
        "execution_roadmap": {"count": roadmap_projects, "rate": round(roadmap_projects / total_projects * 100, 1) if total_projects > 0 else 0.0}
    }

    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "funnel": funnel,
        "module_adoption": module_adoption,
        "total_exports": export_count
    }

@router.get("/events")
def list_analytics_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    event_name: Optional[str] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = db.query(AnalyticsEvent)
    if event_name:
        query = query.filter(AnalyticsEvent.event_name == event_name)

    total = query.count()
    events = query.order_by(desc(AnalyticsEvent.created_at)).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": [
            {
                "id": e.id,
                "event_name": e.event_name,
                "event_category": e.event_category,
                "user_id": e.user_id,
                "project_id": e.project_id,
                "metadata": e.metadata_json,
                "created_at": e.created_at.isoformat()
            }
            for e in events
        ]
    }
