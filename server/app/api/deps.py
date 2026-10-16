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

    # Enforce account suspension strictly across all endpoints
    if getattr(user, "is_suspended", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact administrative support."
        )

    # Update last_active_at timestamp safely
    try:
        user.last_active_at = now
        db.commit()
    except Exception:
        db.rollback()

    return user

ADMIN_ROLES = {"super_admin", "operations_admin", "support_admin", "security_admin", "auditor"}

def require_admin(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Ensure the authenticated user has an authorized administrative role."""
    if not user.role or user.role not in ADMIN_ROLES:
        # Record unauthorized access security incident
        try:
            from app.models.all_models import SecurityEvent, gen_id
            ip = request.client.host if request.client else "unknown"
            sec_event = SecurityEvent(
                id=gen_id("sec_"),
                event_type="unauthorized_admin_access",
                severity="high",
                actor_id=user.id,
                target_user_id=None,
                ip_address=ip,
                user_agent=request.headers.get("User-Agent", "")[:255],
                request_path=str(request.url.path)[:255],
                details={"attempted_role": user.role, "required_roles": list(ADMIN_ROLES)},
                created_at=datetime.now(timezone.utc)
            )
            db.add(sec_event)
            db.commit()
        except Exception:
            db.rollback()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: administrative privileges required."
        )
    return user

def _get_permissions_for_role(role: str) -> List[str]:
    """Return granted granular permissions for each administrative role."""
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

def require_roles(*allowed_roles: str):
    """Factory dependency to enforce specific administrative roles."""
    def role_checker(user: User = Depends(require_admin)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: requires one of the following roles: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker

def require_permission(permission: str):
    """Factory dependency enforcing specific granular administrative permissions."""
    def permission_checker(
        request: Request,
        user: User = Depends(require_admin),
        db: Session = Depends(get_db)
    ) -> User:
        user_perms = _get_permissions_for_role(user.role)
        if permission not in user_perms:
            try:
                from app.models.all_models import SecurityEvent, gen_id
                ip = request.client.host if request.client else "unknown"
                sec_event = SecurityEvent(
                    id=gen_id("sec_"),
                    event_type="forbidden_permission_access",
                    severity="medium",
                    actor_id=user.id,
                    target_user_id=None,
                    ip_address=ip,
                    user_agent=request.headers.get("User-Agent", "")[:255],
                    request_path=str(request.url.path)[:255],
                    details={"role": user.role, "required_permission": permission, "user_permissions": user_perms},
                    created_at=datetime.now(timezone.utc)
                )
                db.add(sec_event)
                db.commit()
            except Exception:
                db.rollback()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: permission '{permission}' required for this action."
            )
        return user
    return permission_checker

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
