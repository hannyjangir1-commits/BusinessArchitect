import logging
import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models.all_models import User, AuditLog, gen_id

logger = logging.getLogger("admin.provisioning")

KNOWN_DEV_PASSWORDS = {"HannyAdmin", "Hanny@BusinessArchitect", "admin", "password", "12345678"}

def normalize_username(username: str) -> str:
    """Normalize and validate admin username."""
    cleaned = username.strip()
    if not cleaned or len(cleaned) < 3 or not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
        raise ValueError(f"Invalid administrator username format: '{username}'")
    return cleaned

def validate_admin_password_strength(password: str) -> bool:
    """Ensure bootstrap password meets strong complexity requirements."""
    if not password or len(password) < 12:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", password):
        return False
    return True

def validate_production_credentials_safety() -> None:
    """
    Enforces that development credentials or known weak passwords are never allowed in production.
    Raises RuntimeError to safely abort production startup if development password is used,
    or if bootstrap is enabled but password is missing or weak.
    """
    is_prod = getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "").lower() == "production" or getattr(settings, "ENVIRONMENT", "").lower() == "production"
    if not is_prod:
        return

    bootstrap_enabled = getattr(settings, "ADMIN_BOOTSTRAP_ENABLED", False)

    raw_password = (
        getattr(settings, "INITIAL_ADMIN_PASSWORD", "") or
        getattr(settings, "ADMIN_PASSWORD", "") or
        getattr(settings, "ADMIN_BOOTSTRAP_PASSWORD", "")
    )

    if bootstrap_enabled and not raw_password:
        logger.critical(
            "PRODUCTION STARTUP ABORTED: Admin bootstrap is enabled (ADMIN_BOOTSTRAP_ENABLED=true), "
            "but no strong production password was provided via INITIAL_ADMIN_PASSWORD (or ADMIN_BOOTSTRAP_PASSWORD)."
        )
        raise RuntimeError("Production admin bootstrap requires a strong INITIAL_ADMIN_PASSWORD; none was provided.")

    if raw_password and (raw_password in KNOWN_DEV_PASSWORDS or raw_password.lower() == "hannyadmin"):
        logger.critical(
            "PRODUCTION STARTUP ABORTED: Insecure local development credentials ('HannyAdmin') "
            "configured in production environment. A strong, unique secret password must be configured."
        )
        raise RuntimeError("Insecure development credentials rejected in production mode.")

    if raw_password and not validate_admin_password_strength(raw_password):
        raise RuntimeError("Production admin password must be at least 12 characters with uppercase, lowercase, numbers, and special characters.")

def seed_development_admin(db: Session) -> bool:
    """
    Deterministically and idempotently seeds the local development super admin account ('HannyAdmin' / 'HannyAdmin').
    Strictly isolated to non-production environments.
    """
    is_prod = getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "").lower() == "production" or getattr(settings, "ENVIRONMENT", "").lower() == "production"
    if is_prod:
        logger.warning("Development admin seeding is strictly prohibited in production mode. Skipping.")
        return False

    # Check if HannyAdmin already exists
    existing = db.query(User).filter(User.username == "HannyAdmin").first()
    if existing:
        from app.core.security import verify_password
        if not verify_password("HannyAdmin", existing.hashed_password) or existing.role != "super_admin":
            existing.hashed_password = hash_password("HannyAdmin")
            existing.role = "super_admin"
            existing.is_suspended = False
            db.commit()
            logger.info("Updated existing local development admin 'HannyAdmin' with requested dev credentials.")
            return True
        logger.info("Local development admin 'HannyAdmin' already configured. Seed skipped.")
        return False

    try:
        dev_admin = User(
            id=gen_id("usr_"),
            username="HannyAdmin",
            email="hannyadmin@businessarchitect.internal",
            hashed_password=hash_password("HannyAdmin"),
            role="super_admin",
            is_suspended=False,
            terms_accepted=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        db.add(dev_admin)
        db.commit()
        logger.info("Successfully seeded local development Super Admin account ('HannyAdmin').")
        return True
    except Exception as e:
        db.rollback()
        logger.error("Failed to seed development admin: %s", type(e).__name__)
        raise

def provision_initial_admin(db: Session) -> bool:
    """
    Idempotently provisions the initial Super Admin account using configuration.
    Requirements:
    1. Obtains credentials from environment variables / settings only when ADMIN_BOOTSTRAP_ENABLED is True.
    2. Hashes password using Argon2id.
    3. Never logs plaintext credentials.
    4. Never overwrites an existing admin or resets an existing password on restart.
    5. Returns True if created, False if already present or skipped.
    """
    # Enforce production security check first
    validate_production_credentials_safety()

    bootstrap_enabled = getattr(settings, "ADMIN_BOOTSTRAP_ENABLED", False)
    if not bootstrap_enabled:
        logger.info("Administrator bootstrap is disabled (ADMIN_BOOTSTRAP_ENABLED is false). Skipping provisioning.")
        return False

    raw_username = getattr(settings, "INITIAL_ADMIN_USERNAME", "") or "HannyAdmin"
    raw_password = (
        getattr(settings, "INITIAL_ADMIN_PASSWORD", "") or
        getattr(settings, "ADMIN_PASSWORD", "") or
        getattr(settings, "ADMIN_BOOTSTRAP_PASSWORD", "")
    )
    admin_email = getattr(settings, "INITIAL_ADMIN_EMAIL", "") or "admin@businessarchitect.internal"

    if not raw_password:
        if getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "").lower() == "production":
            raise RuntimeError("Admin bootstrap enabled in production, but INITIAL_ADMIN_PASSWORD is missing.")
        logger.warning("Admin bootstrap enabled but credentials not configured. Please set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD.")
        return False

    try:
        username = normalize_username(raw_username)
    except ValueError as e:
        logger.error("Failed to normalize admin username: %s", type(e).__name__)
        if getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "").lower() == "production":
            raise
        return False

    if not validate_admin_password_strength(raw_password):
        err_msg = "Admin bootstrap password does not meet security complexity requirements (minimum 12 characters, including uppercase, lowercase, numbers, and special symbols)."
        logger.error(err_msg)
        if getattr(settings, "IS_PROD", False) or getattr(settings, "APP_ENV", "").lower() == "production":
            raise RuntimeError(err_msg)
        return False

    # Check if a super_admin or user with this username already exists
    existing_user = db.query(User).filter(
        (User.username == username) | (User.role == "super_admin")
    ).first()

    if existing_user:
        # If user exists, do not overwrite or reset password
        logger.info("Administrator account already exists (ID: %s, Username: %s). Provisioning skipped.", existing_user.id, existing_user.username)
        return False

    try:
        hashed_pw = hash_password(raw_password)
        admin_user = User(
            id=gen_id("usr_"),
            username=username,
            email=admin_email,
            hashed_password=hashed_pw,
            role="super_admin",
            is_suspended=False,
            terms_accepted=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        db.add(admin_user)
        db.flush()

        # Audit bootstrap action
        audit_entry = AuditLog(
            id=gen_id("aud_"),
            actor_id=admin_user.id,
            action="admin_bootstrap",
            target_type="user",
            target_id=admin_user.id,
            outcome="success",
            reason="Initial Super Admin account provisioned via secure startup sequence",
            details={"username": username, "role": "super_admin"},
            created_at=datetime.now(timezone.utc)
        )
        db.add(audit_entry)
        db.commit()

        logger.info("Successfully provisioned initial Super Administrator account (ID: %s).", admin_user.id)
        return True
    except Exception as e:
        db.rollback()
        logger.error("Error provisioning initial administrator: %s", type(e).__name__)
        raise
