from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password, generate_session_token, generate_csrf_token
from app.models.all_models import User, Session as DBSession
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, UserResponse, SessionResponse
from app.api.deps import get_current_user
from app.core.telemetry import record_analytics_event, record_security_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _set_auth_cookies(response: Response, session_token: str):
    max_age = settings.SESSION_EXPIRE_DAYS * 86400
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

@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, response: Response, db: Session = Depends(get_db)):
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

    # Create session
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRE_DAYS)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)
    db.commit()
    db.refresh(user)

    record_analytics_event(db, user_id=user.id, event_name="registration_completed")

    csrf_token = _set_auth_cookies(response, session_token)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)

@router.post("/login", response_model=SessionResponse)
def login(req: UserLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    # Support login with either email or username
    user = db.query(User).filter(
        (User.email == req.email_or_username) | (User.username == req.email_or_username)
    ).first()

    ip = request.client.host if request.client else "unknown"

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

    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRE_DAYS)
    sess = DBSession(session_token=session_token, user_id=user.id, expires_at=expires_at)
    db.add(sess)
    db.commit()

    record_analytics_event(db, user_id=user.id, event_name="login_completed")

    csrf_token = _set_auth_cookies(response, session_token)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.COOKIE_NAME)
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
