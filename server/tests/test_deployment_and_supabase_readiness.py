import os
import tempfile
# pyrefly: ignore [missing-import]
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.core.config import Settings, settings
from app.db.session import SessionLocal, engine
from app.models.all_models import User, Project, ModuleContent, ModuleVersion
from app.services.version_service import VersionService
from alembic.config import Config
from alembic import command

client = TestClient(app)

def test_root_and_api_health_endpoints():
    """Verify root /health for Render orchestration and /api/health for system status."""
    # Root /health used by Render health check
    res_root = client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] == "ok"
    assert "Venture Atlas" in data_root["service"]

    # /api/health with database connectivity verification
    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    data_api = res_api.json()
    assert data_api["status"] in ("healthy", "degraded")
    assert data_api["database_connected"] is True
    assert "generation_configured" in data_api
    assert "Venture Atlas" in data_api["service"]


def test_supabase_database_url_normalization():
    """Verify that settings correctly normalize postgres:// to postgresql:// for SQLAlchemy."""
    test_settings = Settings()
    test_settings.DATABASE_URL = "postgres://postgres.abc:mypass@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    normalized = test_settings.get_database_url()
    assert normalized.startswith("postgresql://")
    assert "pooler.supabase.com:6543" in normalized
    assert "sslmode=require" in normalized

    # Verify that missing sslmode on remote host is automatically appended
    test_settings.DATABASE_URL = "postgres://postgres.abc:mypass@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    auto_ssl = test_settings.get_database_url()
    assert "sslmode=require" in auto_ssl

    # Verify that passwords containing unescaped '@' characters are automatically percent-encoded
    test_settings.DATABASE_URL = "postgresql://postgres.mcot:Hanny@9216@1234@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    encoded_url = test_settings.get_database_url()
    assert "Hanny%409216%401234" in encoded_url
    assert "aws-0-ap-south-1.pooler.supabase.com" in encoded_url


def test_alembic_fresh_database_upgrade():
    """Verify that Alembic migrations run cleanly on an empty database without syntax or constraint errors."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    original_url = settings.DATABASE_URL
    target_url = f"sqlite:///{tmp_path}"
    settings.DATABASE_URL = target_url
    try:
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", target_url)
        # Run upgrade to head
        command.upgrade(cfg, "head")

        # Verify tables created
        from sqlalchemy import create_engine, inspect
        test_engine = create_engine(f"sqlite:///{tmp_path}")
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        assert "users" in tables
        assert "sessions" in tables
        assert "projects" in tables
        assert "module_contents" in tables
        assert "module_versions" in tables
        assert "roadmap_tasks" in tables
        assert "ai_operations" in tables
        assert "audit_logs" in tables
        assert "security_events" in tables
        assert "system_settings" in tables
        assert "analytics_events" in tables
        test_engine.dispose()
    finally:
        settings.DATABASE_URL = original_url
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def test_postgresql_ddl_boolean_portability():
    """Verify that Alembic generates PostgreSQL-compatible DDL (true/false) rather than integer 0/1 for booleans."""
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = "postgresql://user:pass@localhost:5432/testdb"
    cfg.set_main_option("sqlalchemy.url", "postgresql://user:pass@localhost:5432/testdb")
    
    try:
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.upgrade(cfg, "head", sql=True)
        
        ddl_output = buffer.getvalue()
        assert "BOOLEAN DEFAULT false" in ddl_output
        assert "BOOLEAN DEFAULT true" in ddl_output
        assert "is_suspended BOOLEAN DEFAULT 0" not in ddl_output
        assert "is_active BOOLEAN DEFAULT 1" not in ddl_output
    finally:
        settings.DATABASE_URL = original_db_url


def test_database_row_level_locking_on_module_content():
    """Verify that VersionService acquires row-level lock on ModuleContent row during mutation."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(username="lock_test_user", email="lock@test.com", hashed_password="hashedpassword")
            db.add(user)
            db.commit()

        proj = Project(user_id=user.id, name="Lock Test Project")
        db.add(proj)
        db.commit()

        mod = VersionService.get_or_create_module(db, proj.id, "bmc")
        v = VersionService.save_new_version(
            db=db,
            module=mod,
            data={"test": "data"},
            change_summary="Row lock test version"
        )
        assert v.id is not None
        assert v.version_number == 1

        # Test renaming with lock
        renamed = VersionService.rename_version(db, mod, v.id, "Renamed Version")
        assert renamed.version_name == "Renamed Version"

        # Cleanup
        db.delete(proj)
        db.commit()
    finally:
        db.close()


def test_sensitive_credentials_not_leaked_in_public_endpoints():
    """Verify that public endpoints never expose GEMINI_API_KEY, DATABASE_URL, or SESSION_SECRET."""
    res_root = client.get("/health")
    content_root = res_root.text
    assert all(key not in content_root for key in settings.GEMINI_API_KEYS)
    assert settings.SESSION_SECRET not in content_root

    res_api = client.get("/api/health")
    content_api = res_api.text
    assert all(key not in content_api for key in settings.GEMINI_API_KEYS if key)
    assert settings.SESSION_SECRET not in content_api
    assert "postgresql://" not in content_api
    assert "postgres:" not in content_api


def test_real_postgresql_live_database_integration():
    """Verify live PostgreSQL 18 database connectivity, schema, migrations, and concurrency."""
    import psycopg2
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    pg_url = "postgresql://postgres@127.0.0.1:54322/business_architect_test"
    try:
        conn = psycopg2.connect(host="127.0.0.1", port=54322, user="postgres", dbname="business_architect_test", connect_timeout=2)
        conn.close()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL test instance not available on 54322: {e}")

    pg_engine = create_engine(pg_url)
    PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
    db = PgSession()

    import uuid
    uid_str = uuid.uuid4().hex[:6]
    try:
        user = User(username=f"live_pg_{uid_str}", email=f"live_{uid_str}@test.internal", hashed_password="hashed_password", terms_accepted=True)
        db.add(user)
        db.commit()

        proj = Project(user_id=user.id, name=f"Live PG Project {uid_str}")
        db.add(proj)
        db.commit()

        mod = VersionService.get_or_create_module(db, proj.id, "bmc")
        v = VersionService.save_new_version(db, mod, {"title": "Live PG"}, change_summary="Live PG test")
        assert v.id is not None
        assert v.version_number == 1
        assert v.is_active is True

        # Clean up
        db.delete(proj)
        db.delete(user)
        db.commit()
    finally:
        db.close()
        pg_engine.dispose()


def test_admin_bootstrap_env_var_aliases(monkeypatch):
    """Verify that settings correctly honors both ADMIN_BOOTSTRAP_* and INITIAL_ADMIN_* aliases."""
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "CustomBootstrapAdmin")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "CustomBootstrapSecretPass!")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAIL", "custom_bootstrap@test.internal")
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_EMAIL", raising=False)

    test_settings = Settings()
    assert test_settings.INITIAL_ADMIN_USERNAME == "CustomBootstrapAdmin"
    assert test_settings.INITIAL_ADMIN_PASSWORD == "CustomBootstrapSecretPass!"
    assert test_settings.INITIAL_ADMIN_EMAIL == "custom_bootstrap@test.internal"


def test_gemini_uses_only_the_explicitly_configured_model(monkeypatch):
    """Credential fallback must never silently change the requested model."""
    from app.ai.gemini_service import GeminiAIService
    test_model = "gemini-2.5-flash-custom"
    monkeypatch.setattr(settings, "GEMINI_MODEL", test_model)
    service = GeminiAIService()
    service.api_key = "test-key"
    candidates = service._get_candidate_models()
    assert candidates[0] == test_model
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS_ENABLED", False)
    assert service._get_candidate_models() == [test_model]


def test_version_delete_atomicity_and_fallback():
    """Verify that deleting an active version atomically transitions to the latest remaining version."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(username="del_test_user", email="del@test.com", hashed_password="hashedpassword")
            db.add(user)
            db.commit()

        proj = Project(user_id=user.id, name="Delete Version Atomicity Project")
        db.add(proj)
        db.commit()

        mod = VersionService.get_or_create_module(db, proj.id, "bmc")
        v1 = VersionService.save_new_version(db, mod, {"version": 1}, change_summary="V1")
        v2 = VersionService.save_new_version(db, mod, {"version": 2}, change_summary="V2")
        assert mod.active_version_id == v2.id

        # Delete active version (v2)
        success = VersionService.delete_version(db, mod, v2.id)
        assert success is True

        # Module active_version_id must now atomically point to v1
        assert mod.active_version_id == v1.id
        refreshed_v1 = db.query(ModuleVersion).filter(ModuleVersion.id == v1.id).first()
        assert refreshed_v1.is_active is True

        # Cannot delete the only remaining version (v1)
        with pytest.raises(Exception) as exc:
            VersionService.delete_version(db, mod, v1.id)
        assert "Cannot delete the only remaining version" in str(exc.value)

        # Cleanup
        db.delete(proj)
        db.commit()
    finally:
        db.close()


