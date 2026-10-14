from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.security import verify_csrf_token
from app.models.all_models import User, Session as DBSession, Project

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate the authenticated user from the HTTP-only session cookie or Bearer header."""
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        # Fallback to Authorization: Bearer token for programmatic API access
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    db_session = db.query(DBSession).filter(DBSession.session_token == token).first()
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    # Check expiration (ensure timezone-naive comparison is safe)
    now = datetime.now(timezone.utc)
    sess_exp = db_session.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)

    if sess_exp < now:
        db.delete(db_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again."
        )

    user = db.query(User).filter(User.id == db_session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user

def verify_csrf(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Verify CSRF token for state-changing requests using cookie sessions.
    Safe methods (GET, HEAD, OPTIONS) bypass CSRF checks.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Check for custom CSRF header
    csrf_header = request.headers.get("X-CSRF-Token")
    session_token = request.cookies.get(settings.COOKIE_NAME)

    # If request is authenticated via Authorization Bearer header, browser CSRF is not applicable
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return

    if not session_token or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: missing CSRF token"
        )

    if not verify_csrf_token(csrf_header, session_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: invalid CSRF token"
        )

def get_user_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Project:
    """Enforce project ownership strictly. Returns 404 or 403 if project does not belong to user."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this project"
        )

    return project
