from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.session import get_db
from app.models.all_models import User, AuditLog
from app.api.deps import require_admin

router = APIRouter(prefix="/audit-logs", tags=["Admin Audit Trail"])

@router.get("")
def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    outcome: Optional[str] = Query(None, pattern="^(all|success|failed|denied)$"),
    search: Optional[str] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)

    if action and action != "all":
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))

    if target_type and target_type != "all":
        query = query.filter(AuditLog.target_type == target_type)

    if outcome and outcome != "all":
        query = query.filter(AuditLog.outcome == outcome)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter((AuditLog.action.ilike(s)) | (AuditLog.reason.ilike(s)) | (AuditLog.target_id.ilike(s)))

    total = query.count()
    logs = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * limit).limit(limit).all()

    # Pre-fetch actor usernames
    actor_ids = [l.actor_id for l in logs if l.actor_id]
    actor_map = dict(
        db.query(User.id, User.username).filter(User.id.in_(actor_ids)).all()
    ) if actor_ids else {}

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": [
            {
                "id": l.id,
                "timestamp": l.created_at.isoformat(),
                "actor_id": l.actor_id,
                "actor_username": actor_map.get(l.actor_id, "System / Automated"),
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "outcome": l.outcome,
                "reason": l.reason,
                "details": l.details
            }
            for l in logs
        ]
    }
