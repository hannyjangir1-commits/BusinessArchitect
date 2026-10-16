import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, Session as DBSession,
    AIOperation, AnalyticsEvent, SecurityEvent, AuditLog
)
from app.api.deps import require_admin, require_permission
from app.core.config import settings
from app.services.system_setting_service import get_setting_float

router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])

def _parse_time_window(range_str: str, custom_start: Optional[str] = None, custom_end: Optional[str] = None):
    now = datetime.now(timezone.utc)
    if range_str == "24h":
        return now - timedelta(hours=24), now
    elif range_str == "7d":
        return now - timedelta(days=7), now
    elif range_str == "30d":
        return now - timedelta(days=30), now
    elif range_str == "90d":
        return now - timedelta(days=90), now
    elif range_str == "custom" and custom_start and custom_end:
        try:
            start = datetime.fromisoformat(custom_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(custom_end.replace("Z", "+00:00"))
            return start, end
        except Exception:
            return now - timedelta(days=30), now
    return now - timedelta(days=30), now

@router.get("/stats")
def get_dashboard_stats(
    range: str = Query("30d", pattern="^(24h|7d|30d|90d|custom)$"),
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
    stage: Optional[str] = None,
    module: Optional[str] = None,
    current_admin: User = Depends(require_permission("view_dashboard")),
    db: Session = Depends(get_db)
):
    start_dt, end_dt = _parse_time_window(range, custom_start, custom_end)

    # 1. User metrics
    total_users = db.query(func.count(User.id)).scalar() or 0
    new_users = db.query(func.count(User.id)).filter(
        User.created_at >= start_dt, User.created_at <= end_dt
    ).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(
        User.last_active_at >= start_dt
    ).scalar() or 0
    suspended_users = db.query(func.count(User.id)).filter(
        User.is_suspended == True
    ).scalar() or 0

    # Active admin sessions
    admin_user_ids = [u.id for u in db.query(User.id).filter(User.role.in_(["super_admin", "operations_admin", "support_admin", "security_admin", "auditor"])).all()]
    active_admin_sessions = db.query(func.count(DBSession.id)).filter(
        DBSession.user_id.in_(admin_user_ids)
    ).scalar() or 0

    # Failed login attempts in period
    failed_logins = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type.in_(["admin_login_failure", "login_failure"]),
        SecurityEvent.created_at >= start_dt
    ).scalar() or 0

    # 2. Project metrics
    proj_query = db.query(Project)
    if stage and stage != "all":
        proj_query = proj_query.filter(Project.stage == stage)

    total_projects = proj_query.count()
    new_projects = proj_query.filter(
        Project.created_at >= start_dt, Project.created_at <= end_dt
    ).count()

    # Stage distribution
    stage_counts_raw = db.query(Project.stage, func.count(Project.id)).group_by(Project.stage).all()
    stage_distribution = {s: c for s, c in stage_counts_raw}

    # Projects with saved module content
    projects_with_modules = db.query(func.count(func.distinct(ModuleContent.project_id))).scalar() or 0

    # 3. AI metrics
    ai_query = db.query(AIOperation).filter(
        AIOperation.created_at >= start_dt, AIOperation.created_at <= end_dt
    )
    if module and module != "all":
        ai_query = ai_query.filter(AIOperation.module_type == module)

    total_ai_ops = ai_query.count()
    successful_ai_ops = ai_query.filter(AIOperation.status == "success").count()
    failed_ai_ops = ai_query.filter(AIOperation.status.in_(["failed", "timeout"])).count()
    timeout_ai_ops = ai_query.filter(AIOperation.status == "timeout").count()
    retried_ai_ops = ai_query.filter(AIOperation.retry_count > 0).count()

    success_rate = round((successful_ai_ops / total_ai_ops * 100), 1) if total_ai_ops > 0 else 0.0
    failure_rate = round((failed_ai_ops / total_ai_ops * 100), 1) if total_ai_ops > 0 else 0.0

    # Latencies
    durations = [op.duration_ms for op in ai_query.filter(AIOperation.duration_ms != None).all()]
    if durations:
        durations.sort()
        n = len(durations)
        median_latency = durations[n // 2]
        p95_idx = int(0.95 * n)
        p95_latency = durations[min(p95_idx, n - 1)]
    else:
        median_latency = 0
        p95_latency = 0

    # Operations by module
    ops_by_mod_raw = db.query(
        AIOperation.module_type, func.count(AIOperation.id)
    ).filter(
        AIOperation.created_at >= start_dt, AIOperation.created_at <= end_dt
    ).group_by(AIOperation.module_type).all()
    operations_by_module = {m: c for m, c in ops_by_mod_raw}

    # 4. Infrastructure metrics (real measurements)
    t0 = time.time()
    db_ok = True
    try:
        db.execute(func.now())
        db_latency_ms = round((time.time() - t0) * 1000, 2)
    except Exception:
        db_ok = False
        db_latency_ms = -1

    # Recent error count
    recent_errors = db.query(func.count(AIOperation.id)).filter(
        AIOperation.status == "failed",
        AIOperation.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
    ).scalar() or 0

    # Security incidents
    active_security_alerts = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.severity.in_(["high", "critical"]),
        SecurityEvent.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).scalar() or 0

    # Read alert threshold settings
    alert_ai_failure_pct = get_setting_float(db, "alert_ai_failure_pct", 20.0)
    alert_db_latency_ms = get_setting_float(db, "alert_db_latency_ms", 200.0)

    # Dynamic Operational Alerts
    alerts = []
    if failure_rate is not None and failure_rate > alert_ai_failure_pct and total_ai_ops >= 5:
        alerts.append({
            "id": "alert_ai_failure_rate",
            "title": f"Elevated AI Generation Failure Rate: {failure_rate}%",
            "severity": "high",
            "subsystem": "Gemini AI",
            "evidence": f"{failed_ai_ops} failed out of {total_ai_ops} total operations in selected window",
            "status": "active",
            "link": "/admin/ai-operations"
        })
    if db_latency_ms > alert_db_latency_ms:
        alerts.append({
            "id": "alert_db_latency",
            "title": f"High Database Query Latency: {db_latency_ms}ms",
            "severity": "medium",
            "subsystem": "Database",
            "evidence": f"Ping execution exceeded {alert_db_latency_ms}ms threshold",
            "status": "active",
            "link": None
        })
    if suspended_users > 0:
        alerts.append({
            "id": "alert_suspended_users",
            "title": f"{suspended_users} Account(s) Currently Suspended",
            "severity": "low",
            "subsystem": "User Governance",
            "evidence": "Users restricted from platform access",
            "status": "active",
            "link": "/admin/users"
        })
    if failed_logins >= 5:
        alerts.append({
            "id": "alert_login_spike",
            "title": f"Authentication Failure Spike ({failed_logins} attempts)",
            "severity": "medium",
            "subsystem": "Security",
            "evidence": f"{failed_logins} failed login attempts recorded in selected window",
            "status": "active",
            "link": "/admin/account"
        })

    return {
        "time_window": {
            "range": range,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "timezone": "UTC"
        },
        "users": {
            "total": total_users,
            "new_in_period": new_users,
            "active_in_period": active_users,
            "suspended": suspended_users,
            "active_admin_sessions": active_admin_sessions,
            "failed_auth_attempts": failed_logins
        },
        "projects": {
            "total": total_projects,
            "new_in_period": new_projects,
            "with_saved_modules": projects_with_modules,
            "stage_distribution": stage_distribution
        },
        "ai": {
            "total_operations": total_ai_ops,
            "successful_operations": successful_ai_ops,
            "failed_operations": failed_ai_ops,
            "timeout_operations": timeout_ai_ops,
            "retried_operations": retried_ai_ops,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "operations_by_module": operations_by_module,
            "model_identifier": settings.GEMINI_MODEL
        },
        "infrastructure": {
            "backend_status": "healthy",
            "database_status": "connected" if db_ok else "unhealthy",
            "database_latency_ms": db_latency_ms,
            "recent_24h_errors": recent_errors,
            "last_check_timestamp": datetime.now(timezone.utc).isoformat()
        },
        "security": {
            "active_security_alerts": active_security_alerts,
            "failed_logins": failed_logins
        },
        "alerts": alerts
    }

@router.get("/trends")
def get_dashboard_trends(
    range: str = Query("30d", pattern="^(24h|7d|30d|90d|custom)$"),
    custom_start: Optional[str] = None,
    custom_end: Optional[str] = None,
    current_admin: User = Depends(require_permission("view_dashboard")),
    db: Session = Depends(get_db)
):
    start_dt, end_dt = _parse_time_window(range, custom_start, custom_end)

    # Determine daily grouping intervals
    # Generate days in range
    days_list = []
    curr = start_dt.date()
    end_date = end_dt.date()
    while curr <= end_date:
        days_list.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)

    # User registration trend
    user_rows = db.query(
        func.date(User.created_at).label("day"),
        func.count(User.id).label("count")
    ).filter(User.created_at >= start_dt, User.created_at <= end_dt).group_by("day").all()
    user_map = {str(r.day): r.count for r in user_rows}

    # Project creation trend
    proj_rows = db.query(
        func.date(Project.created_at).label("day"),
        func.count(Project.id).label("count")
    ).filter(Project.created_at >= start_dt, Project.created_at <= end_dt).group_by("day").all()
    proj_map = {str(r.day): r.count for r in proj_rows}

    # AI operations trend
    ai_rows = db.query(
        func.date(AIOperation.created_at).label("day"),
        func.count(AIOperation.id).label("total"),
        func.sum(case((AIOperation.status == "success", 1), else_=0)).label("success"),
        func.sum(case((AIOperation.status.in_(["failed", "timeout"]), 1), else_=0)).label("failed"),
        func.avg(AIOperation.duration_ms).label("avg_latency")
    ).filter(AIOperation.created_at >= start_dt, AIOperation.created_at <= end_dt).group_by("day").all()

    ai_map = {
        str(r.day): {
            "total": r.total or 0,
            "success": int(r.success or 0),
            "failed": int(r.failed or 0),
            "avg_latency": round(float(r.avg_latency or 0), 0)
        }
        for r in ai_rows
    }

    # Assemble series
    trend_data = []
    for d in days_list:
        ai_stat = ai_map.get(d, {"total": 0, "success": 0, "failed": 0, "avg_latency": 0})
        trend_data.append({
            "date": d,
            "users": user_map.get(d, 0),
            "projects": proj_map.get(d, 0),
            "ai_total": ai_stat["total"],
            "ai_success": ai_stat["success"],
            "ai_failed": ai_stat["failed"],
            "ai_avg_latency": ai_stat["avg_latency"]
        })

    return {
        "range": range,
        "points": trend_data
    }
