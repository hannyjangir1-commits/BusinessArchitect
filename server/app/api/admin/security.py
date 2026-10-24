from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db.session import get_db
from app.models.all_models import (
    User, Session as DBSession, SecurityEvent, AuditLog
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.config import settings
from app.core.telemetry import record_security_event, record_audit_log
from app.services.admin_authorization_service import validate_session_revocation_target

router = APIRouter(prefix="/security", tags=["Admin Security Center"])

@router.get("/events")
def list_security_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None, pattern="^(all|info|low|medium|high|critical)$"),
    event_type: Optional[str] = None,
    current_admin: User = Depends(require_permission("view_security")),
    db: Session = Depends(get_db)
):
    query = db.query(SecurityEvent)

    if severity and severity != "all":
        query = query.filter(SecurityEvent.severity == severity)

    if event_type and event_type != "all":
        query = query.filter(SecurityEvent.event_type.ilike(f"%{event_type.strip()}%"))

    total = query.count()
    events = query.order_by(desc(SecurityEvent.created_at)).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": [
            {
                "id": s.id,
                "event_type": s.event_type,
                "severity": s.severity,
                "actor_id": s.actor_id,
                "target_user_id": s.target_user_id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "request_path": s.request_path,
                "details": s.details,
                "created_at": s.created_at.isoformat()
            }
            for s in events
        ]
    }

@router.get("/sessions")
def list_active_sessions(
    request: Request,
    current_admin: User = Depends(require_permission("view_security")),
    db: Session = Depends(get_db)
):
    current_token = request.cookies.get(settings.COOKIE_NAME)
    now = datetime.now(timezone.utc)

    # Active sessions not yet expired
    sessions = (
        db.query(DBSession)
        .join(User, DBSession.user_id == User.id)
        .filter(DBSession.expires_at > now)
        .order_by(desc(DBSession.created_at))
        .limit(100)
        .all()
    )

    return {
        "total_active": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "username": s.user.username if s.user else "Unknown",
                "email": s.user.email if s.user else "Unknown",
                "role": s.user.role if s.user else "user",
                "is_current": s.session_token == current_token,
                "created_at": s.created_at.isoformat(),
                "expires_at": s.expires_at.isoformat()
            }
            for s in sessions
        ]
    }

@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: str,
    request: Request,
    current_admin: User = Depends(require_permission("revoke_sessions")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    target_user = sess.user or db.query(User).filter(User.id == sess.user_id).first()
    if target_user:
        validate_session_revocation_target(current_admin, target_user)

    target_user_id = sess.user_id
    db.delete(sess)
    db.commit()

    record_security_event(
        db,
        event_type="session_revoked_by_admin",
        severity="medium",
        actor_id=current_admin.id,
        target_user_id=target_user_id,
        details={"revoked_session_id": session_id}
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="session_revocation",
        target_type="session",
        target_id=session_id,
        outcome="success",
        reason=f"Administrator revoked session ID {session_id}"
    )

    return {"message": f"Session {session_id} has been revoked."}

@router.post("/sessions/revoke-all")
def revoke_all_sessions(
    request: Request,
    current_admin: User = Depends(require_permission("revoke_sessions")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """
    Emergency global session kill-switch.
    Explicitly authorized only for administrators with 'revoke_sessions' permission
    (super_admin and security_admin). Revokes all active sessions system-wide, preserving
    only the invoking administrator's current active session. This global action cannot
    be used as a selective or targeted bypass against an individual administrator.
    """
    current_token = request.cookies.get(settings.COOKIE_NAME)
    query = db.query(DBSession)
    if current_token:
        query = query.filter(DBSession.session_token != current_token)

    count = query.delete(synchronize_session=False)
    db.commit()

    record_security_event(
        db,
        event_type="all_sessions_revoked_by_admin",
        severity="high",
        actor_id=current_admin.id,
        details={"revoked_count": count}
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="revoke_all_sessions",
        target_type="session",
        target_id="all",
        outcome="success",
        reason=f"Administrator revoked all {count} active sessions (except own session)"
    )

    return {"message": f"Successfully revoked {count} active session(s)."}
