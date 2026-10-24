import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password, generate_session_token, generate_csrf_token, DUMMY_PASSWORD_HASH
)
from app.models.all_models import User, Session as DBSession
from app.api.deps import get_current_user, get_request_session_token, require_admin, verify_csrf, ADMIN_ROLES, _get_permissions_for_role
from app.core.telemetry import record_security_event, record_audit_log
from app.core.client_identity import extract_client_ip
from app.core.auth_limiter import (
    normalize_account_identifier,
    check_login_rate_limits,
    record_login_failure,
    record_login_success,
)

router = APIRouter(prefix="/auth", tags=["Admin Authentication"])



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

@router.post("/login", response_model=AdminSessionResponse)
def admin_login(
    req: AdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    client_ip = extract_client_ip(request, settings.TRUSTED_PROXIES)
    username_clean = req.username.strip()
    normalized_account = normalize_account_identifier(username_clean)

    # Enforce shared database-backed dual-bucket abuse protection (IP + account) for admin logins
    check_login_rate_limits(db, client_ip, normalized_account, is_admin=True)

    user = db.query(User).filter(
        (User.username == username_clean) | (User.email == username_clean)
    ).first()

    # Mitigate account enumeration timing shortcut using constant-like Argon2 verification
    valid_password = False
    if user and user.role in ADMIN_ROLES:
        valid_password = verify_password(req.password, user.hashed_password)
    else:
        verify_password(req.password, DUMMY_PASSWORD_HASH)

    if not user or not valid_password:
        record_login_failure(client_ip, normalized_account, is_admin=True)
        record_security_event(
            event_type="admin_login_failure",
            severity="medium",
            actor_id=user.id if user else None,
            ip_address=client_ip,
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
        record_login_failure(client_ip, normalized_account, is_admin=True)
        record_security_event(
            event_type="unauthorized_admin_login_attempt",
            severity="high",
            actor_id=user.id,
            ip_address=client_ip,
            user_agent=request.headers.get("User-Agent"),
            request_path="/api/admin/auth/login",
            details={"username": username_clean, "actual_role": user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator credentials"
        )

    # Clear failed attempts for this account upon verified credentials
    record_login_success(client_ip, normalized_account, is_admin=True)

    if user.is_suspended:
        record_security_event(
            db,
            event_type="suspended_admin_login_attempt",
            severity="high",
            actor_id=user.id,
            ip_address=client_ip,
            user_agent=request.headers.get("User-Agent"),
            request_path="/api/admin/auth/login"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This administrator account has been suspended"
        )

    # Issue session with dynamic expiry days setting
    from app.services.system_setting_service import get_setting_int
    expiry_days = get_setting_int(db, "session_expiry_days", settings.SESSION_EXPIRE_DAYS)
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)

    # Update last_active_at
    user.last_active_at = datetime.now(timezone.utc)
    db.commit()

    # Set secure cookies
    max_age = expiry_days * 86400
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
        ip_address=client_ip,
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
        details={"ip": client_ip}
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

@router.post("/logout", dependencies=[Depends(verify_csrf)])
def admin_logout(
    request: Request,
    response: Response,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    token = get_request_session_token(request)
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
    response: Response,
    current_admin: User = Depends(require_admin)
):
    token = request.cookies.get(settings.COOKIE_NAME) or ""
    csrf_token = generate_csrf_token(token) if token else ""
    if token and csrf_token:
        max_age = settings.SESSION_EXPIRE_DAYS * 86400
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=max_age,
            httponly=False,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path="/"
        )
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
    current_token = get_request_session_token(request)
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

@router.get("/sessions")
def list_my_sessions(
    request: Request,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List active sessions for the currently authenticated administrator."""
    current_token = get_request_session_token(request)
    now = datetime.now(timezone.utc)

    sessions = (
        db.query(DBSession)
        .filter(
            DBSession.user_id == current_admin.id,
            DBSession.expires_at > now
        )
        .order_by(DBSession.created_at.desc())
        .all()
    )

    return {
        "total_active": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "is_current": s.session_token == current_token,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None
            }
            for s in sessions
        ]
    }

@router.post("/sessions/{session_id}/revoke")
def revoke_my_session(
    session_id: str,
    request: Request,
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """Revoke a specific session belonging to the current administrator."""
    sess = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_admin.id
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or does not belong to you")

    current_token = get_request_session_token(request)
    is_current = sess.session_token == current_token

    db.delete(sess)
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="admin_revoke_own_session",
        target_type="session",
        target_id=session_id,
        outcome="success",
        details={"was_current": is_current}
    )

    return {"message": "Session revoked successfully", "revoked_id": session_id, "was_current": is_current}

@router.post("/sessions/revoke-others")
def revoke_my_other_sessions(
    request: Request,
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """Revoke all active sessions for current admin except the current active session."""
    current_token = get_request_session_token(request)
    if not current_token:
        raise HTTPException(status_code=400, detail="No active session token found")

    deleted_count = db.query(DBSession).filter(
        DBSession.user_id == current_admin.id,
        DBSession.session_token != current_token
    ).delete()
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="admin_revoke_other_sessions",
        target_type="user",
        target_id=current_admin.id,
        outcome="success",
        details={"revoked_count": deleted_count}
    )

    return {"message": f"Successfully revoked {deleted_count} other active session(s).", "revoked_count": deleted_count}

