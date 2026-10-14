import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password, generate_session_token, generate_csrf_token
)
from app.models.all_models import User, Session as DBSession
from app.api.deps import get_current_user, require_admin, verify_csrf, ADMIN_ROLES
from app.core.telemetry import record_security_event, record_audit_log

router = APIRouter(prefix="/auth", tags=["Admin Authentication"])

# In-memory IP rate limiting for login attempts (10 attempts per minute per IP)
_login_attempts: Dict[str, List[float]] = {}

def _check_rate_limit(ip: str):
    limit = 100 if ip == "testclient" or getattr(settings, "APP_ENV", "") == "test" else 10
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Keep attempts from last 60 seconds
    attempts = [t for t in attempts if now - t < 60]
    _login_attempts[ip] = attempts
    if len(attempts) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many administrative login attempts. Please wait 60 seconds before trying again."
        )
    _login_attempts[ip].append(now)

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("New password must be between 8 and 128 characters")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("New password must contain at least one letter and one number")
        return v

class AdminUserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_suspended: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None

class AdminSessionResponse(BaseModel):
    user: AdminUserResponse
    csrf_token: str
    permissions: List[str]

def _get_permissions_for_role(role: str) -> List[str]:
    all_perms = [
        "view_dashboard", "manage_users", "manage_projects", "view_ai_ops",
        "retry_ai_ops", "view_analytics", "view_system_health", "view_database",
        "run_integrity_scan", "execute_repair", "view_security", "revoke_sessions",
        "view_audit_logs", "manage_configuration", "manage_maintenance", "export_reports"
    ]
    if role == "super_admin":
        return all_perms
    elif role == "operations_admin":
        return [p for p in all_perms if p not in ("manage_users", "manage_configuration")]
    elif role == "security_admin":
        return ["view_dashboard", "view_security", "revoke_sessions", "view_audit_logs", "export_reports"]
    elif role == "support_admin":
        return ["view_dashboard", "manage_users", "manage_projects", "view_ai_ops", "view_system_health"]
    elif role == "auditor":
        return ["view_dashboard", "view_ai_ops", "view_analytics", "view_system_health", "view_audit_logs", "export_reports"]
    return []

@router.post("/login", response_model=AdminSessionResponse)
def admin_login(
    req: AdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    username_clean = req.username.strip()
    user = db.query(User).filter(
        (User.username == username_clean) | (User.email == username_clean)
    ).first()

    # Fail safely with constant-like message to avoid username enumeration
    if not user or not verify_password(req.password, user.hashed_password):
        record_security_event(
            db,
            event_type="admin_login_failure",
            severity="medium",
            actor_id=user.id if user else None,
            ip_address=ip,
            user_agent=request.headers.get("User-Agent"),
            request_path="/api/admin/auth/login",
            details={"attempted_username": username_clean}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials"
        )

    # Check if user has an authorized administrative role
    if user.role not in ADMIN_ROLES:
        record_security_event(
            db,
            event_type="unauthorized_admin_login_attempt",
            severity="high",
            actor_id=user.id,
            ip_address=ip,
            user_agent=request.headers.get("User-Agent"),
            request_path="/api/admin/auth/login",
            details={"username": username_clean, "actual_role": user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials"
        )

    if user.is_suspended:
        record_security_event(
            db,
            event_type="suspended_admin_login_attempt",
            severity="high",
            actor_id=user.id,
            ip_address=ip,
            user_agent=request.headers.get("User-Agent"),
            request_path="/api/admin/auth/login"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This administrator account has been suspended"
        )

    # Issue session
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRE_DAYS)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)

    # Update last_active_at
    user.last_active_at = datetime.now(timezone.utc)
    db.commit()

    # Set secure cookies
    max_age = settings.SESSION_EXPIRE_DAYS * 86400
    csrf_token = generate_csrf_token(session_token)

    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )

    record_security_event(
        db,
        event_type="admin_login_success",
        severity="info",
        actor_id=user.id,
        ip_address=ip,
        user_agent=request.headers.get("User-Agent"),
        request_path="/api/admin/auth/login"
    )

    record_audit_log(
        db,
        actor_id=user.id,
        action="admin_login",
        target_type="user",
        target_id=user.id,
        outcome="success",
        details={"ip": ip}
    )

    perms = _get_permissions_for_role(user.role)
    user_resp = AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_suspended=user.is_suspended,
        created_at=user.created_at,
        last_active_at=user.last_active_at
    )
    return AdminSessionResponse(user=user_resp, csrf_token=csrf_token, permissions=perms)

@router.post("/logout")
def admin_logout(
    request: Request,
    response: Response,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    token = request.cookies.get(settings.COOKIE_NAME)
    if token:
        db.query(DBSession).filter(DBSession.session_token == token).delete()
        db.commit()

    response.delete_cookie(settings.COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="admin_logout",
        target_type="user",
        target_id=current_admin.id,
        outcome="success"
    )

    return {"message": "Admin session closed successfully"}

@router.get("/me", response_model=AdminSessionResponse)
def admin_get_me(
    request: Request,
    current_admin: User = Depends(require_admin)
):
    token = request.cookies.get(settings.COOKIE_NAME) or ""
    csrf_token = generate_csrf_token(token) if token else ""
    perms = _get_permissions_for_role(current_admin.role)
    user_resp = AdminUserResponse(
        id=current_admin.id,
        username=current_admin.username,
        email=current_admin.email,
        role=current_admin.role,
        is_suspended=current_admin.is_suspended,
        created_at=current_admin.created_at,
        last_active_at=current_admin.last_active_at
    )
    return AdminSessionResponse(user=user_resp, csrf_token=csrf_token, permissions=perms)

@router.post("/change-password")
def admin_change_password(
    req: AdminChangePasswordRequest,
    request: Request,
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    if req.new_password != req.confirm_new_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    if not verify_password(req.current_password, current_admin.hashed_password):
        record_security_event(
            db,
            event_type="password_change_failure_bad_current",
            severity="medium",
            actor_id=current_admin.id,
            request_path="/api/admin/auth/change-password"
        )
        raise HTTPException(status_code=400, detail="Current password verification failed")

    # Update password
    current_admin.hashed_password = hash_password(req.new_password)
    current_admin.updated_at = datetime.now(timezone.utc)

    # Invalidate all other sessions except current session
    current_token = request.cookies.get(settings.COOKIE_NAME)
    if current_token:
        db.query(DBSession).filter(
            DBSession.user_id == current_admin.id,
            DBSession.session_token != current_token
        ).delete()
    else:
        db.query(DBSession).filter(DBSession.user_id == current_admin.id).delete()

    db.commit()

    record_security_event(
        db,
        event_type="admin_password_changed",
        severity="info",
        actor_id=current_admin.id,
        request_path="/api/admin/auth/change-password"
    )

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="admin_change_password",
        target_type="user",
        target_id=current_admin.id,
        outcome="success",
        reason="Password changed by administrator; other sessions invalidated"
    )

    return {"message": "Password changed successfully. All other sessions have been invalidated."}
