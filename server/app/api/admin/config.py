from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import User, SystemSetting, gen_id
from app.api.deps import require_admin, verify_csrf
from app.core.config import settings
from app.core.telemetry import record_audit_log

router = APIRouter(prefix="/configuration", tags=["Admin Configuration Center"])

DEFAULT_SETTINGS = {
    "ai_timeout_seconds": {"value": "30", "type": "int", "category": "ai", "desc": "Max HTTP timeout for Gemini AI requests (10-120s)"},
    "ai_max_retries": {"value": "2", "type": "int", "category": "ai", "desc": "Max automated retries for transient AI generation errors (0-5)"},
    "session_expiry_days": {"value": "7", "type": "int", "category": "security", "desc": "User session duration in days before re-authentication (1-30d)"},
    "alert_ai_failure_pct": {"value": "20", "type": "int", "category": "alerts", "desc": "AI failure rate threshold percentage to trigger alerts (5-50%)"},
    "alert_db_latency_ms": {"value": "200", "type": "int", "category": "alerts", "desc": "Database query latency threshold in ms (50-1000ms)"},
    "maintenance_mode": {"value": "false", "type": "boolean", "category": "maintenance", "desc": "Global platform maintenance mode switch"},
    "public_registration_enabled": {"value": "true", "type": "boolean", "category": "security", "desc": "Allow public user registration"}
}

class UpdateSettingsRequest(BaseModel):
    settings: Dict[str, str]

@router.get("")
def get_system_configuration(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Ensure default settings exist in DB
    existing = {s.key: s for s in db.query(SystemSetting).all()}
    for key, spec in DEFAULT_SETTINGS.items():
        if key not in existing:
            new_s = SystemSetting(
                id=gen_id("set_"),
                key=key,
                value=spec["value"],
                value_type=spec["type"],
                category=spec["category"],
                description=spec["desc"],
                is_secret=False,
                updated_at=datetime.now(timezone.utc)
            )
            db.add(new_s)
    db.commit()

    runtime_settings = []
    for s in db.query(SystemSetting).filter(SystemSetting.is_secret == False).all():
        runtime_settings.append({
            "key": s.key,
            "value": s.value,
            "type": s.value_type,
            "category": s.category,
            "description": s.description,
            "updated_at": s.updated_at.isoformat()
        })

    # Deployment environment flags (never expose secret values!)
    environment_status = [
        {"name": "GEMINI_API_KEY", "configured": bool(settings.GEMINI_API_KEY), "category": "AI Services"},
        {"name": "DATABASE_URL", "configured": bool(settings.DATABASE_URL), "category": "Storage"},
        {"name": "SESSION_SECRET", "configured": bool(settings.SESSION_SECRET), "category": "Security"},
        {"name": "APP_ENV", "configured": True, "value": settings.APP_ENV, "category": "Deployment"},
        {"name": "COOKIE_SECURE", "configured": True, "value": str(settings.COOKIE_SECURE), "category": "Security"}
    ]

    return {
        "runtime_settings": runtime_settings,
        "environment_status": environment_status
    }

@router.post("")
def update_system_configuration(
    req: UpdateSettingsRequest,
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    updated = []
    for key, val in req.settings.items():
        val_str = str(val).strip()
        # Validation rules
        if key == "ai_timeout_seconds":
            ival = int(val_str)
            if ival < 10 or ival > 120:
                raise HTTPException(status_code=400, detail="ai_timeout_seconds must be between 10 and 120")
        elif key == "ai_max_retries":
            ival = int(val_str)
            if ival < 0 or ival > 5:
                raise HTTPException(status_code=400, detail="ai_max_retries must be between 0 and 5")
        elif key == "session_expiry_days":
            ival = int(val_str)
            if ival < 1 or ival > 30:
                raise HTTPException(status_code=400, detail="session_expiry_days must be between 1 and 30")
        elif key in ("maintenance_mode", "public_registration_enabled"):
            if val_str.lower() not in ("true", "false"):
                raise HTTPException(status_code=400, detail=f"{key} must be 'true' or 'false'")
            val_str = val_str.lower()

        s_obj = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if s_obj:
            s_obj.value = val_str
            s_obj.updated_by = current_admin.id
            s_obj.updated_at = datetime.now(timezone.utc)
            updated.append(key)

    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="configuration_update",
        target_type="system_setting",
        target_id="batch",
        outcome="success",
        reason=f"Administrator updated {len(updated)} configuration setting(s)",
        details={"keys": updated}
    )

    return {"message": f"Successfully updated {len(updated)} setting(s).", "updated_keys": updated}
