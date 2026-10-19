from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password, generate_session_token, generate_csrf_token
from app.models.all_models import User, Session as DBSession, SecurityEvent
from app.schemas.auth import (
    UserRegisterRequest, UserLoginRequest, UserResponse, SessionResponse,
    UserProfileUpdateRequest, UserChangePasswordRequest
)
from app.api.deps import get_current_user, get_request_session_token, verify_csrf
from app.core.telemetry import record_analytics_event, record_security_event
from app.services.system_setting_service import get_setting_bool, get_setting_int

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _set_auth_cookies(response: Response, session_token: str, expiry_days: int = 7):
    max_age = expiry_days * 86400
    csrf_token = generate_csrf_token(session_token)

    # HTTP-only session cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    # Readable CSRF cookie for client header injection
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    return csrf_token

def _check_user_login_rate_limit(db: Session, ip: str, window_minutes: int = 15, max_attempts: int = 5):
    """Abuse protection for public user login using shared database events."""
    if not ip or ip == "unknown" or ip == "testclient" or getattr(settings, "APP_ENV", "") == "test":
        return
    window_start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    failed_attempts = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.event_type == "login_failure",
        SecurityEvent.ip_address == ip,
        SecurityEvent.created_at >= window_start
    ).scalar() or 0

    if failed_attempts >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later."
        )

@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, response: Response, db: Session = Depends(get_db)):
    # Check if public registration is enabled
    if not get_setting_bool(db, "public_registration_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public user registration is currently disabled by administrator."
        )

    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if not req.terms_accepted:
        raise HTTPException(status_code=400, detail="Terms and Conditions must be accepted")

    # Check for existing email or username
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username is already taken")

    # Create user with Argon2id hash
    hashed = hash_password(req.password)
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hashed,
        terms_accepted=True
    )
    db.add(user)
    db.flush()

    # Create session with dynamic expiry days setting
    expiry_days = get_setting_int(db, "session_expiry_days", settings.SESSION_EXPIRE_DAYS)
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)
    db.commit()
    db.refresh(user)

    record_analytics_event(db, user_id=user.id, event_name="registration_completed")

    csrf_token = _set_auth_cookies(response, session_token, expiry_days=expiry_days)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)

@router.post("/login", response_model=SessionResponse)
def login(req: UserLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

    # Enforce database-backed abuse protection for user logins
    _check_user_login_rate_limit(db, ip)

    # Support login with either email or username
    user = db.query(User).filter(
        (User.email == req.email_or_username) | (User.username == req.email_or_username)
    ).first()

    if not user or not verify_password(req.password, user.hashed_password):
        record_security_event(
            db,
            event_type="login_failure",
            severity="low",
            ip_address=ip,
            request_path="/api/auth/login",
            details={"attempted": req.email_or_username}
        )
        raise HTTPException(status_code=401, detail="Invalid email/username or password")

    if getattr(user, "is_suspended", False):
        record_security_event(
            db,
            event_type="suspended_user_login_attempt",
            severity="medium",
            actor_id=user.id,
            ip_address=ip,
            request_path="/api/auth/login"
        )
        raise HTTPException(status_code=403, detail="Account has been suspended. Please contact administrative support.")

    expiry_days = get_setting_int(db, "session_expiry_days", settings.SESSION_EXPIRE_DAYS)
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)
    db.commit()

    record_analytics_event(db, user_id=user.id, event_name="login_completed")

    csrf_token = _set_auth_cookies(response, session_token, expiry_days=expiry_days)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)

@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = get_request_session_token(request)
    if token:
        db.query(DBSession).filter(DBSession.session_token == token).delete()
        db.commit()

    response.delete_cookie(settings.COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=SessionResponse)
def get_me(request: Request, response: Response, current_user: User = Depends(get_current_user)):
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
    return SessionResponse(user=UserResponse.model_validate(current_user), csrf_token=csrf_token)

@router.post("/refresh", response_model=SessionResponse, dependencies=[Depends(verify_csrf)])
def refresh_session(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refreshes the active session token and CSRF cookie."""
    token = get_request_session_token(request)
    expiry_days = get_setting_int(db, "session_expiry_days", settings.SESSION_EXPIRE_DAYS)
    new_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

    if token:
        db.query(DBSession).filter(DBSession.session_token == token).delete()

    sess = DBSession(session_token=new_token, user_id=current_user.id, expires_at=expires_at)
    db.add(sess)
    db.commit()

    csrf_token = _set_auth_cookies(response, new_token, expiry_days=expiry_days)
    return SessionResponse(user=UserResponse.model_validate(current_user), csrf_token=csrf_token)

@router.put("/profile", response_model=UserResponse, dependencies=[Depends(verify_csrf)])
def update_profile(
    req: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the authenticated user's profile (username and/or email).
    Validates uniqueness and case-normalization against existing accounts.
    """
    if req.username is not None and req.username != current_user.username:
        # Check uniqueness
        existing = db.query(User).filter(
            User.username == req.username,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username is already taken")
        current_user.username = req.username

    if req.email is not None and req.email != current_user.email:
        # Check uniqueness
        existing_email = db.query(User).filter(
            User.email == req.email,
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email is already in use by another account")
        current_user.email = req.email

    if "display_name" in req.model_fields_set:
        current_user.display_name = req.display_name
    if req.preferences is not None:
        current_user.preferences = req.preferences.model_dump()

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)

    record_analytics_event(db, user_id=current_user.id, event_name="profile_updated")
    return UserResponse.model_validate(current_user)

@router.post("/change-password", dependencies=[Depends(verify_csrf)])
def change_password(
    req: UserChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows the authenticated user to change their password securely.
    Verifies current password via Argon2id, updates the hash, and invalidates other sessions.
    """
    if req.new_password != req.confirm_new_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    if not verify_password(req.current_password, current_user.hashed_password):
        record_security_event(
            db,
            event_type="password_change_bad_current",
            severity="medium",
            actor_id=current_user.id,
            request_path="/api/auth/change-password"
        )
        raise HTTPException(status_code=400, detail="Current password verification failed")

    # Update password
    current_user.hashed_password = hash_password(req.new_password)
    current_user.updated_at = datetime.now(timezone.utc)

    # Invalidate all other active sessions for security except current token
    current_token = get_request_session_token(request)
    if current_token:
        db.query(DBSession).filter(
            DBSession.user_id == current_user.id,
            DBSession.session_token != current_token
        ).delete()
    else:
        db.query(DBSession).filter(DBSession.user_id == current_user.id).delete()

    db.commit()

    record_security_event(
        db,
        event_type="password_changed",
        severity="info",
        actor_id=current_user.id,
        request_path="/api/auth/change-password"
    )

    return {"message": "Password changed successfully. All other sessions have been invalidated."}
