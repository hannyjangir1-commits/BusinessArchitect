from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.all_models import User, SystemSetting, Session as DBSession
from app.api.deps import require_admin, verify_csrf
from app.core.telemetry import record_audit_log

router = APIRouter(prefix="/maintenance", tags=["Admin Maintenance Center"])

class MaintenanceToggleRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = "Scheduled maintenance"

@router.get("/status")
def get_maintenance_status(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == "maintenance_mode").first()
    is_enabled = setting.value.lower() == "true" if setting else False

    now = datetime.now(timezone.utc)
    expired_sessions = db.query(func.count(DBSession.id)).filter(DBSession.expires_at < now).scalar() or 0

    return {
        "maintenance_mode_active": is_enabled,
        "last_updated": setting.updated_at.isoformat() if setting else None,
        "expired_sessions_pending_cleanup": expired_sessions
    }

@router.post("/toggle")
def toggle_maintenance_mode(
    req: MaintenanceToggleRequest,
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == "maintenance_mode").first()
    if not setting:
        setting = SystemSetting(
            key="maintenance_mode",
            value="false",
            value_type="boolean",
            category="maintenance",
            updated_at=datetime.now(timezone.utc)
        )
        db.add(setting)

    setting.value = "true" if req.enabled else "false"
    setting.updated_by = current_admin.id
    setting.updated_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="maintenance_toggle",
        target_type="system_setting",
        target_id="maintenance_mode",
        outcome="success",
        reason=req.reason or "Maintenance mode state toggled",
        details={"enabled": req.enabled}
    )

    return {
        "message": f"Maintenance mode has been {'enabled' if req.enabled else 'disabled'}.",
        "maintenance_mode_active": req.enabled
    }

@router.post("/prune-sessions")
def prune_expired_sessions(
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    pruned = db.query(DBSession).filter(DBSession.expires_at < now).delete()
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="maintenance_prune_sessions",
        target_type="session",
        target_id="expired",
        outcome="success",
        reason=f"Administrator manually pruned {pruned} expired sessions",
        details={"pruned_count": pruned}
    )

    return {"message": f"Pruned {pruned} expired session(s).", "pruned_count": pruned}
