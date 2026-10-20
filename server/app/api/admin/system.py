import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.db.session import get_db, engine
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    CopilotMessage, Session as DBSession, AIOperation, AnalyticsEvent,
    SecurityEvent, AuditLog, SystemSetting
)
from app.api.deps import require_admin, require_permission
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["Admin System & Diagnostics"])

_STARTUP_TIME = time.time()

@router.get("/health")
def get_system_health(
    current_admin: User = Depends(require_permission("view_system_health")),
    db: Session = Depends(get_db)
):
    uptime_seconds = int(time.time() - _STARTUP_TIME)

    # Database connectivity and latency measurement
    db_ok = True
    db_latency_ms = -1
    t0 = time.time()
    try:
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - t0) * 1000, 2)
    except Exception as e:
        db_ok = False

    # Check Alembic migration status
    alembic_rev = "unknown"
    try:
        res = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        if res:
            alembic_rev = str(res)
    except Exception:
        pass

    # Overall subsystem statuses
    components = [
        {
            "name": "FastAPI Core Application",
            "status": "healthy",
            "latency_ms": 0.5,
            "details": f"Python {sys.version.split()[0]} running on {sys.platform}"
        },
        {
            "name": "Primary Database",
            "status": "healthy" if db_ok and db_latency_ms < 200 else ("degraded" if db_ok else "unhealthy"),
            "latency_ms": db_latency_ms,
            "details": f"Dialect: {engine.dialect.name}, Revision: {alembic_rev}"
        },
        {
            "name": "Content Generation Service",
            "status": "healthy" if settings.GEMINI_API_KEYS else "not_configured",
            "latency_ms": 0.0,
            "details": f"Processing configuration: {settings.GEMINI_MODEL}, Credential pool: {len(settings.GEMINI_API_KEYS)} configured"
        },
        {
            "name": "Session Store",
            "status": "healthy",
            "latency_ms": 0.0,
            "details": f"Active sessions: {db.query(func.count(DBSession.id)).scalar() or 0}"
        }
    ]

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "app_env": settings.APP_ENV,
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_connected": db_ok,
        "database_latency_ms": db_latency_ms,
        "alembic_revision": alembic_rev,
        "components": components
    }

@router.get("/database")
def get_database_diagnostics(
    current_admin: User = Depends(require_permission("view_database")),
    db: Session = Depends(get_db)
):
    table_counts = {
        "users": db.query(func.count(User.id)).scalar() or 0,
        "sessions": db.query(func.count(DBSession.id)).scalar() or 0,
        "projects": db.query(func.count(Project.id)).scalar() or 0,
        "module_contents": db.query(func.count(ModuleContent.id)).scalar() or 0,
        "module_versions": db.query(func.count(ModuleVersion.id)).scalar() or 0,
        "roadmap_tasks": db.query(func.count(RoadmapTask.id)).scalar() or 0,
        "copilot_messages": db.query(func.count(CopilotMessage.id)).scalar() or 0,
        "ai_operations": db.query(func.count(AIOperation.id)).scalar() or 0,
        "analytics_events": db.query(func.count(AnalyticsEvent.id)).scalar() or 0,
        "security_events": db.query(func.count(SecurityEvent.id)).scalar() or 0,
        "audit_logs": db.query(func.count(AuditLog.id)).scalar() or 0,
        "system_settings": db.query(func.count(SystemSetting.id)).scalar() or 0,
    }

    # Pool info
    pool = engine.pool
    pool_info = {
        "pool_class": pool.__class__.__name__,
        "size": getattr(pool, "size", lambda: 0)() if hasattr(pool, "size") else "N/A",
        "checked_in": getattr(pool, "checkedin", lambda: 0)() if hasattr(pool, "checkedin") else "N/A",
        "checked_out": getattr(pool, "checkedout", lambda: 0)() if hasattr(pool, "checkedout") else "N/A",
        "overflow": getattr(pool, "overflow", lambda: 0)() if hasattr(pool, "overflow") else "N/A",
    }

    # Alembic current revision
    current_rev = "none"
    try:
        current_rev = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar() or "none"
    except Exception:
        pass

    return {
        "engine": engine.dialect.name,
        "current_migration_revision": current_rev,
        "table_row_counts": table_counts,
        "pool_configuration": pool_info,
        "ssl_enforced": "sslmode=require" in settings.DATABASE_URL.lower() or not settings.DATABASE_URL.startswith("sqlite")
    }

@router.get("/logs")
def get_unified_log_stream(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    severity: Optional[str] = None,
    subsystem: Optional[str] = None,
    search: Optional[str] = None,
    current_admin: User = Depends(require_permission("view_audit_logs")),
    db: Session = Depends(get_db)
):
    """
    Returns a unified operational audit and security log stream
    allowing admins to investigate incidents and activities.
    """
    events = []

    # 1. Security events
    sec_q = db.query(SecurityEvent)
    if severity and severity != "all":
        sec_q = sec_q.filter(SecurityEvent.severity == severity)
    if search:
        sec_q = sec_q.filter(SecurityEvent.event_type.ilike(f"%{search}%"))

    for s in sec_q.order_by(SecurityEvent.created_at.desc()).limit(50).all():
        events.append({
            "id": s.id,
            "timestamp": s.created_at.isoformat(),
            "subsystem": "security",
            "severity": s.severity,
            "event_type": s.event_type,
            "message": f"Security event '{s.event_type}' at {s.request_path or 'unknown path'}",
            "actor_id": s.actor_id,
            "details": s.details
        })

    # 2. Audit logs
    audit_q = db.query(AuditLog)
    if search:
        audit_q = audit_q.filter(AuditLog.action.ilike(f"%{search}%"))

    for a in audit_q.order_by(AuditLog.created_at.desc()).limit(50).all():
        events.append({
            "id": a.id,
            "timestamp": a.created_at.isoformat(),
            "subsystem": "audit",
            "severity": "info" if a.outcome == "success" else "high",
            "event_type": a.action,
            "message": f"Admin action '{a.action}' on {a.target_type}:{a.target_id or 'all'}",
            "actor_id": a.actor_id,
            "details": a.details
        })

    # 3. AI failed operations
    ai_q = db.query(AIOperation).filter(AIOperation.status.in_(["failed", "timeout"]))
    for ai in ai_q.order_by(AIOperation.created_at.desc()).limit(30).all():
        events.append({
            "id": ai.id,
            "timestamp": ai.created_at.isoformat(),
            "subsystem": "ai_ops",
            "severity": "high" if ai.status == "timeout" else "medium",
            "event_type": f"ai_{ai.status}",
            "message": f"AI {ai.operation_type} failed for module {ai.module_type}: {ai.error_message or ai.error_category}",
            "actor_id": ai.user_id,
            "details": {"module": ai.module_type, "category": ai.error_category, "model": ai.model_name}
        })

    # Filter subsystem if requested
    if subsystem and subsystem != "all":
        events = [e for e in events if e["subsystem"] == subsystem]

    # Sort unified events descending
    events.sort(key=lambda x: x["timestamp"], reverse=True)

    total = len(events)
    offset = (page - 1) * limit
    paginated = events[offset : offset + limit]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": paginated
    }
