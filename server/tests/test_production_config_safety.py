import os
import pytest
from unittest.mock import patch, MagicMock
from app.core.config import Settings, validate_production_runtime_safety, KNOWN_DEV_SESSION_SECRETS
from app.core.admin_provisioning import (
    validate_production_credentials_safety,
    seed_development_admin,
    provision_initial_admin,
    KNOWN_DEV_PASSWORDS
)
from app.db.session import SessionLocal
from app.models.all_models import User, gen_id
from app.core.security import hash_password, verify_password

def test_production_rejects_development_password():
    """Verify that known dev passwords and weak passwords abort production startup."""
    from app.core import config
    orig_env = config.settings.APP_ENV
    orig_is_prod = config.settings.IS_PROD
    orig_pw = config.settings.INITIAL_ADMIN_PASSWORD
    orig_boot = config.settings.ADMIN_BOOTSTRAP_ENABLED

    try:
        config.settings.APP_ENV = "production"
        config.settings.IS_PROD = True
        config.settings.ADMIN_BOOTSTRAP_ENABLED = True

        for bad_pw in ["HannyAdmin", "admin", "password", "12345678", "hannyadmin"]:
            config.settings.INITIAL_ADMIN_PASSWORD = bad_pw
            with pytest.raises(RuntimeError, match="Insecure development credentials rejected"):
                validate_production_credentials_safety()

        # Weak password (lacking complexity or under 12 characters)
        config.settings.INITIAL_ADMIN_PASSWORD = "Short1!"
        with pytest.raises(RuntimeError, match="Production admin password must be at least 12 characters"):
            validate_production_credentials_safety()

        # Missing password when bootstrap is enabled
        config.settings.INITIAL_ADMIN_PASSWORD = ""
        with pytest.raises(RuntimeError, match="Production admin bootstrap requires a strong INITIAL_ADMIN_PASSWORD"):
            validate_production_credentials_safety()

    finally:
        config.settings.APP_ENV = orig_env
        config.settings.IS_PROD = orig_is_prod
        config.settings.INITIAL_ADMIN_PASSWORD = orig_pw
        config.settings.ADMIN_BOOTSTRAP_ENABLED = orig_boot

def test_production_rejects_development_session_secret():
    """Verify that default or weak session secrets abort production startup."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.IS_PROD = True
    mock_settings.APP_ENV = "production"
    mock_settings.COOKIE_SECURE = True
    mock_settings.DATABASE_URL = "postgresql://user:pass@ep-db.us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

    with patch.dict(os.environ, {"DATABASE_URL": mock_settings.DATABASE_URL, "ALLOWED_ORIGINS": "https://app.example.com"}):
        # Known dev session secret
        for bad_secret in KNOWN_DEV_SESSION_SECRETS:
            mock_settings.SESSION_SECRET = bad_secret
            with pytest.raises(RuntimeError, match="Production requires a strong, unique SESSION_SECRET"):
                validate_production_runtime_safety(mock_settings)

        # Too short secret
        mock_settings.SESSION_SECRET = "too-short-secret"
        with pytest.raises(RuntimeError, match="Production requires a strong, unique SESSION_SECRET"):
            validate_production_runtime_safety(mock_settings)

def test_production_rejects_local_sqlite_fallback():
    """Verify that local SQLite fallback is rejected in production."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.IS_PROD = True
    mock_settings.APP_ENV = "production"
    mock_settings.SESSION_SECRET = "a-very-strong-unique-production-session-secret-key-64-characters-long"
    mock_settings.COOKIE_SECURE = True

    # 1. DATABASE_URL is SQLite
    mock_settings.DATABASE_URL = "sqlite:///./dev_database.db"
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./dev_database.db", "ALLOWED_ORIGINS": "https://app.example.com"}):
        with pytest.raises(RuntimeError, match="Local SQLite database fallbacks are strictly rejected in production"):
            validate_production_runtime_safety(mock_settings)

    # 2. DATABASE_URL environment variable is missing
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="Production requires an explicit production DATABASE_URL"):
            validate_production_runtime_safety(mock_settings)

def test_production_rejects_localhost_cors_defaults():
    """Verify that localhost CORS defaults are rejected in production."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.IS_PROD = True
    mock_settings.APP_ENV = "production"
    mock_settings.SESSION_SECRET = "a-very-strong-unique-production-session-secret-key-64-characters-long"
    mock_settings.COOKIE_SECURE = True
    mock_settings.DATABASE_URL = "postgresql://user:pass@ep-db.us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

    # ALLOWED_ORIGINS unset in environment
    with patch.dict(os.environ, {"DATABASE_URL": mock_settings.DATABASE_URL}, clear=True):
        with pytest.raises(RuntimeError, match="Production requires an explicit ALLOWED_ORIGINS allowlist"):
            validate_production_runtime_safety(mock_settings)

    # ALLOWED_ORIGINS empty
    with patch.dict(os.environ, {"DATABASE_URL": mock_settings.DATABASE_URL, "ALLOWED_ORIGINS": "   "}):
        with pytest.raises(RuntimeError, match="Production requires an explicit ALLOWED_ORIGINS allowlist"):
            validate_production_runtime_safety(mock_settings)

def test_valid_production_configuration_passes():
    """Verify that a properly configured production environment validates successfully."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.IS_PROD = True
    mock_settings.APP_ENV = "production"
    mock_settings.SESSION_SECRET = "production-super-strong-secret-key-must-be-min-32-chars-long-1234567890"
    mock_settings.COOKIE_SECURE = True
    mock_settings.DATABASE_URL = "postgresql://user:pass@ep-db.us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

    with patch.dict(os.environ, {
        "DATABASE_URL": mock_settings.DATABASE_URL,
        "ALLOWED_ORIGINS": "https://app.businessarchitect.io,https://api.businessarchitect.io"
    }):
        # Should not raise any error
        validate_production_runtime_safety(mock_settings)

def test_development_seeding_blocked_in_production():
    """Verify development admin seeding is strictly a no-op in production."""
    from app.core import config
    orig_env = config.settings.APP_ENV
    orig_is_prod = config.settings.IS_PROD

    try:
        config.settings.APP_ENV = "production"
        config.settings.IS_PROD = True

        db = SessionLocal()
        try:
            res = seed_development_admin(db)
            assert res is False, "seed_development_admin must return False and perform no action in production"
        finally:
            db.close()
    finally:
        config.settings.APP_ENV = orig_env
        config.settings.IS_PROD = orig_is_prod

def test_production_bootstrap_idempotence_preserves_existing_password():
    """Verify repeated administrator bootstrap never resets an existing admin's password."""
    db = SessionLocal()
    from app.core import config
    orig_env = config.settings.APP_ENV
    orig_is_prod = config.settings.IS_PROD
    orig_boot = config.settings.ADMIN_BOOTSTRAP_ENABLED
    orig_user = config.settings.INITIAL_ADMIN_USERNAME
    orig_pw = config.settings.INITIAL_ADMIN_PASSWORD

    test_admin_username = f"admin_idem_{gen_id('')[:6]}"
    existing_pw = "OriginalAdminStrongPassword123!"

    try:
        # Create initial admin in database
        existing_admin = User(
            id=gen_id("usr_"),
            username=test_admin_username,
            email=f"{test_admin_username}@enterprise.io",
            hashed_password=hash_password(existing_pw),
            role="super_admin",
            is_suspended=False,
            terms_accepted=True
        )
        db.add(existing_admin)
        db.commit()

        # Configure environment as production with a different password attempt
        config.settings.APP_ENV = "production"
        config.settings.IS_PROD = True
        config.settings.ADMIN_BOOTSTRAP_ENABLED = True
        config.settings.INITIAL_ADMIN_USERNAME = test_admin_username
        config.settings.INITIAL_ADMIN_PASSWORD = "DifferentNewPassword123!@#"

        # Run bootstrap again
        result = provision_initial_admin(db)
        assert result is False, "provision_initial_admin must return False when admin already exists"

        # Verify password in database remains the original password, NOT the new one!
        db.refresh(existing_admin)
        assert verify_password(existing_pw, existing_admin.hashed_password) is True
        assert verify_password("DifferentNewPassword123!@#", existing_admin.hashed_password) is False

    finally:
        # Cleanup
        db.delete(existing_admin)
        db.commit()
        db.close()
        config.settings.APP_ENV = orig_env
        config.settings.IS_PROD = orig_is_prod
        config.settings.ADMIN_BOOTSTRAP_ENABLED = orig_boot
        config.settings.INITIAL_ADMIN_USERNAME = orig_user
        config.settings.INITIAL_ADMIN_PASSWORD = orig_pw

def test_ci_database_schema_and_alembic_head():
    """Verify the database schema contains all required tables and matches migrations."""
    db = SessionLocal()
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        tables = set(inspector.get_table_names())
        
        required_tables = {
            "users",
            "system_settings",
            "security_events",
            "audit_logs",
            "projects",
            "module_contents",
            "module_versions",
            "roadmap_tasks",
            "alembic_version"
        }
        for table in required_tables:
            assert table in tables, f"Expected table '{table}' in test database schema"

        # Check alembic_version has head revision
        from sqlalchemy import text
        res = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert res == "c1fa92de3310", f"Expected Alembic head revision 'c1fa92de3310', got '{res}'"
    finally:
        db.close()
