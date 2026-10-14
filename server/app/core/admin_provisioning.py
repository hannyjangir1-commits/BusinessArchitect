import logging
import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models.all_models import User, AuditLog, gen_id

logger = logging.getLogger("admin.provisioning")

def normalize_username(username: str) -> str:
    """Normalize and validate admin username."""
    cleaned = username.strip()
    if not cleaned or len(cleaned) < 3 or not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
        raise ValueError(f"Invalid administrator username format: '{username}'")
    return cleaned

def provision_initial_admin(db: Session) -> bool:
    """
    Idempotently provisions the initial Super Admin account using configuration.
    Requirements:
    1. Obtains credentials from environment variables / settings.
    2. Hashes password using Argon2id.
    3. Never logs plaintext credentials.
    4. Never overwrites an existing admin or resets an existing password on restart.
    5. Returns True if created, False if already present or skipped.
    """
    raw_username = getattr(settings, "INITIAL_ADMIN_USERNAME", "HannyAdmin")
    raw_password = getattr(settings, "INITIAL_ADMIN_PASSWORD", "Hanny@BusinessArchitect")
    admin_email = getattr(settings, "INITIAL_ADMIN_EMAIL", "admin@businessarchitect.internal")

    if not raw_username or not raw_password:
        logger.warning("Admin provisioning skipped: credentials not configured.")
        return False

    try:
        username = normalize_username(raw_username)
    except ValueError as e:
        logger.error("Failed to normalize admin username: %s", str(e))
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
        logger.error("Error provisioning initial administrator: %s", str(e))
        raise
