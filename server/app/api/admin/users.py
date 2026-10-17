from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from app.db.session import get_db
from app.models.all_models import (
    User, Project, Session as DBSession, SecurityEvent, AuditLog, AIOperation, gen_id
)
from app.api.deps import require_admin, require_permission, verify_csrf, ADMIN_ROLES
from app.core.security import hash_password
from app.core.telemetry import record_security_event, record_audit_log
from app.core.business_stage import normalize_business_stage

router = APIRouter(prefix="/users", tags=["Admin User Management"])

class SuspendUserRequest(BaseModel):
    reason: str

class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 3 or len(cleaned) > 32:
            raise ValueError("Username must be between 3 and 32 characters")
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
            raise ValueError("Username may only contain letters, numbers, periods, dashes, and underscores")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        return v

class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_suspended: Optional[bool] = None
    suspension_reason: Optional[str] = None

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
        if role in ("admin", "admins"):
            query = query.filter(User.role.in_(ADMIN_ROLES))
        else:
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

@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """Create a new user or administrator account. Creating an administrator requires Super Admin privileges."""
    target_role = req.role.strip()
    valid_roles = {"user", "super_admin", "operations_admin", "security_admin", "support_admin", "auditor"}
    if target_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role '{target_role}'. Must be one of: {', '.join(sorted(valid_roles))}")

    if target_role in ADMIN_ROLES and current_admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can create administrator accounts.")

    # Check username / email collisions
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username is already taken")
    if db.query(User).filter(User.email == str(req.email).strip().lower()).first():
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = User(
        id=gen_id("usr_"),
        username=req.username,
        email=str(req.email).strip().lower(),
        hashed_password=hash_password(req.password),
        role=target_role,
        is_suspended=False,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user_create",
        target_type="user",
        target_id=new_user.id,
        outcome="success",
        reason=f"Admin {current_admin.username} created account '{new_user.username}' with role '{new_user.role}'",
        details={"username": new_user.username, "email": new_user.email, "role": new_user.role}
    )

    return {
        "message": f"Account '{new_user.username}' created successfully.",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role,
            "is_suspended": new_user.is_suspended,
            "created_at": new_user.created_at.isoformat()
        }
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
                "stage": normalize_business_stage(p.stage),
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

@router.put("/{user_id}")
def update_user(
    user_id: str,
    req: UpdateUserRequest,
    current_admin: User = Depends(require_permission("manage_users")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """Update user or administrator details, including role changes with last super-admin protection."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If modifying role
    if req.role is not None:
        target_role = req.role.strip()
        valid_roles = {"user", "super_admin", "operations_admin", "security_admin", "support_admin", "auditor"}
        if target_role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role '{target_role}'. Must be one of: {', '.join(sorted(valid_roles))}")

        if (target_role in ADMIN_ROLES or user.role in ADMIN_ROLES) and current_admin.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a Super Admin can alter administrator roles.")

        # Prevent demoting the last active super_admin
        if user.role == "super_admin" and target_role != "super_admin":
            active_super_admins = db.query(User).filter(
                User.role == "super_admin",
                User.is_suspended == False
            ).count()
            if active_super_admins <= 1:
                raise HTTPException(status_code=400, detail="Cannot alter the role of the last active Super Admin account")

        user.role = target_role

    if req.email is not None:
        email_clean = str(req.email).strip().lower()
        collision = db.query(User).filter(User.email == email_clean, User.id != user_id).first()
        if collision:
            raise HTTPException(status_code=400, detail="Email is already in use by another account")
        user.email = email_clean

    if req.is_suspended is not None:
        if req.is_suspended:
            if user.id == current_admin.id:
                raise HTTPException(status_code=400, detail="Administrators cannot suspend their own account")
            if user.role == "super_admin":
                active_super_admins = db.query(User).filter(
                    User.role == "super_admin",
                    User.is_suspended == False
                ).count()
                if active_super_admins <= 1:
                    raise HTTPException(status_code=400, detail="Cannot suspend the last active Super Admin account")
            user.is_suspended = True
            user.suspended_at = datetime.now(timezone.utc)
            user.suspension_reason = req.suspension_reason or "Administrative suspension"
            db.query(DBSession).filter(DBSession.user_id == user_id).delete()
        else:
            user.is_suspended = False
            user.suspended_at = None
            user.suspension_reason = None

    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="user_update",
        target_type="user",
        target_id=user.id,
        outcome="success",
        details={"username": user.username, "updated_role": user.role, "is_suspended": user.is_suspended}
    )

    return {
        "message": f"Account '{user.username}' updated successfully.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_suspended": user.is_suspended,
            "updated_at": user.updated_at.isoformat()
        }
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

    if user.role == "super_admin":
        if current_admin.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a Super Admin can suspend another Super Admin")
        active_super_admins = db.query(User).filter(
            User.role == "super_admin",
            User.is_suspended == False
        ).count()
        if active_super_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot suspend the last active Super Admin account")

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

    if user.role == "super_admin":
        if current_admin.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a Super Admin can delete a Super Admin account")
        total_super_admins = db.query(User).filter(User.role == "super_admin").count()
        if total_super_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last Super Admin account")

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
