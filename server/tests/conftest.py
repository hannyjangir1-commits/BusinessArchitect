"""Keep the test suite isolated from developer and production configuration."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parents[1]
_DB_HANDLE, _DB_PATH_TEXT = tempfile.mkstemp(
    prefix=".businessarchitect-pytest-",
    suffix=".sqlite3",
    dir=_SERVER_DIR,
)
os.close(_DB_HANDLE)
_DB_PATH = Path(_DB_PATH_TEXT)
_DB_PATH.unlink(missing_ok=True)

# Environment variables take precedence over values loaded from the repository's
# .env file. This prevents tests from ever selecting the developer's configured DB
# or making real Gemini requests.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_API_KEYS"] = ""
os.environ["ADMIN_BOOTSTRAP_ENABLED"] = "false"
os.environ["INITIAL_ADMIN_USERNAME"] = ""
os.environ["INITIAL_ADMIN_PASSWORD"] = ""
os.environ["INITIAL_ADMIN_EMAIL"] = ""
os.environ["SESSION_SECRET"] = "pytest-only-session-secret-never-use-outside-tests"
os.environ["COOKIE_SECURE"] = "false"


def pytest_sessionstart(session):
    """Build the isolated database from the same migrations used in deployment."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(_SERVER_DIR / "alembic.ini"))
    command.upgrade(config, "head")


import pytest

@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Ensure clean auth rate limit state across test runs."""
    try:
        from app.core.auth_limiter import reset_auth_limiter_state
        reset_auth_limiter_state()
    except Exception:
        pass
    try:
        from app.core.ai_limiter import reset_ai_limiter_state
        reset_ai_limiter_state()
    except Exception:
        pass
    yield
    try:
        from app.core.auth_limiter import reset_auth_limiter_state
        reset_auth_limiter_state()
    except Exception:
        pass
    try:
        from app.core.ai_limiter import reset_ai_limiter_state
        reset_ai_limiter_state()
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    """Close SQLite connections and remove only the temporary DB created above."""
    try:
        from app.db.session import engine

        engine.dispose()
    except Exception:
        pass

    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{_DB_PATH}{suffix}").unlink(missing_ok=True)
