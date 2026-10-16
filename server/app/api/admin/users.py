from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from app.db.session import get_db
from app.models.all_models import (
    User, Project, Session as DBSession, SecurityEvent, AuditLog, AIOperation
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.telemetry import record_security_event, record_audit_log

router = APIRouter(prefix="/users", tags=["Admin User Management"])

class SuspendUserRequest(BaseModel):
    reason: str

@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(all|active|suspended)$"),
    role: Optional[str] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|username|last_active_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_admin: User = Depends(require_permission("manage_users")),
    db: Session = Depends(get_db)
):
    query = db.query(User)

    if search:
        search_clean = f"%{search.strip()}%"
        query = query.filter((User.username.ilike(search_clean)) | (User.email.ilike(search_clean)))

    if status == "active":
        query = query.filter(User.is_suspended == False)
    elif status == "suspended":
        query = query.filter(User.is_suspended == True)

    if role and role != "all":
        query = query.filter(User.role == role)

    total = query.count()

    order_col = getattr(User, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(asc(order_col))

    offset = (page - 1) * limit
    users = query.offset(offset).limit(limit).all()

    # Get project counts
    user_ids = [u.id for u in users]
    proj_counts = dict(
        db.query(Project.user_id, func.count(Project.id))
        .filter(Project.user_id.in_(user_ids))
        .group_by(Project.user_id)
        .all()
    ) if user_ids else {}

    results = []
    for u in users:
        results.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_suspended": u.is_suspended,
            "suspended_at": u.suspended_at.isoformat() if u.suspended_at else None,
            "suspension_reason": u.suspension_reason,
            "created_at": u.created_at.isoformat(),
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
            "projects_count": proj_counts.get(u.id, 0)
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": results
    }

@router.get("/{user_id}")
def get_user_detail(
    user_id: str,
    current_admin: User = Depends(require_permission("manage_users")),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    projects = db.query(Project).filter(Project.user_id == user_id).order_by(desc(Project.created_at)).all()
    sessions_count = db.query(func.count(DBSession.id)).filter(DBSession.user_id == user_id).scalar() or 0
    ai_ops_count = db.query(func.count(AIOperation.id)).filter(AIOperation.user_id == user_id).scalar() or 0

    recent_sec_events = db.query(SecurityEvent).filter(
        (SecurityEvent.actor_id == user_id) | (SecurityEvent.target_user_id == user_id)
    ).order_by(desc(SecurityEvent.created_at)).limit(10).all()

    recent_audit_logs = db.query(AuditLog).filter(
        (AuditLog.target_id == user_id) | (AuditLog.actor_id == user_id)
    ).order_by(desc(AuditLog.created_at)).limit(10).all()

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_suspended": user.is_suspended,
            "suspended_at": user.suspended_at.isoformat() if user.suspended_at else None,
            "suspension_reason": user.suspension_reason,
            "terms_accepted": user.terms_accepted,
            "created_at": user.created_at.isoformat(),
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
            "sessions_count": sessions_count,
            "ai_ops_count": ai_ops_count
        },
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "stage": p.stage,
                "active_module": p.active_module,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat()
            }
            for p in projects
        ],
        "security_events": [
            {
                "id": s.id,
                "event_type": s.event_type,
                "severity": s.severity,
                "created_at": s.created_at.isoformat(),
                "ip_address": s.ip_address,
                "details": s.details
            }
            for s in recent_sec_events
        ],
        "audit_logs": [
            {
                "id": a.id,
                "action": a.action,
                "outcome": a.outcome,
                "reason": a.reason,
                "created_at": a.created_at.isoformat(),
                "actor_id": a.actor_id
            }
            for a in recent_audit_logs
        ]
    }

@router.post("/{user_id}/suspend")
def suspend_user(
    user_id: str,
    req: SuspendUserRequest,
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Administrators cannot suspend their own account")

    if user.role == "super_admin" and current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can suspend another Super Admin")

    reason = req.reason.strip() or "Administrative suspension"
    now = datetime.now(timezone.utc)

    user.is_suspended = True
    user.suspended_at = now
    user.suspension_reason = reason

    # Terminate all active sessions immediately
    deleted_sessions = db.query(DBSession).filter(DBSession.user_id == user_id).delete()
    db.commit()

    record_security_event(
        db,
        event_type="account_suspension",
        severity="high",
        actor_id=current_admin.id,
        target_user_id=user.id,
        details={"reason": reason, "revoked_sessions": deleted_sessions}
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user_suspend",
        target_type="user",
        target_id=user.id,
        outcome="success",
        reason=reason,
        details={"username": user.username, "revoked_sessions": deleted_sessions}
    )

    return {
        "message": f"User '{user.username}' has been suspended and {deleted_sessions} session(s) revoked.",
        "user_id": user.id,
        "is_suspended": True
    }

@router.post("/{user_id}/reactivate")
def reactivate_user(
    user_id: str,
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_suspended = False
    user.suspended_at = None
    user.suspension_reason = None
    db.commit()

    record_security_event(
        db,
        event_type="account_reactivation",
        severity="info",
        actor_id=current_admin.id,
        target_user_id=user.id
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user_reactivate",
        target_type="user",
        target_id=user.id,
        outcome="success",
        reason="Administrative reactivation",
        details={"username": user.username}
    )

    return {
        "message": f"User '{user.username}' has been reactivated.",
        "user_id": user.id,
        "is_suspended": False
    }

@router.post("/{user_id}/revoke-sessions")
def revoke_user_sessions(
    user_id: str,
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted_sessions = db.query(DBSession).filter(DBSession.user_id == user_id).delete()
    db.commit()

    record_security_event(
        db,
        event_type="sessions_revoked_by_admin",
        severity="medium",
        actor_id=current_admin.id,
        target_user_id=user.id,
        details={"count": deleted_sessions}
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="session_revoked",
        target_type="user",
        target_id=user.id,
        outcome="success",
        reason=f"Administrator revoked all {deleted_sessions} active sessions",
        details={"count": deleted_sessions}
    )

    return {"message": f"Revoked {deleted_sessions} session(s) for user '{user.username}'."}

@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    confirm_username: str = Query(..., description="Must match target username exactly"),
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Administrators cannot delete their own account")

    if confirm_username.strip() != user.username:
        raise HTTPException(status_code=400, detail="Confirmation username does not match target user")

    username = user.username
    email = user.email

    try:
        # Delete user cascades to projects and sessions cleanly per SQLAlchemy model relationships
        db.delete(user)
        db.commit()

        record_audit_log(
            db,
            actor_id=current_admin.id,
            action="user_delete",
            target_type="user",
            target_id=user_id,
            outcome="success",
            reason=f"Permanently deleted account '{username}' ({email}) by administrator",
            details={"deleted_username": username, "deleted_email": email}
        )

        return {"message": f"Account '{username}' and associated resources have been permanently deleted."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
