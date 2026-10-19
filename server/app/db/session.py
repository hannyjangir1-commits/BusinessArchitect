from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

db_url = settings.get_database_url()

engine_kwargs = {
    "pool_pre_ping": True,
}

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / Supabase pooler resilience settings
    if ":6543" in db_url:
        # Supabase PgBouncer Transaction Pooler (port 6543):
        # Use NullPool to allow PgBouncer to manage connection lifecycle cleanly
        from sqlalchemy.pool import NullPool
        engine_kwargs["poolclass"] = NullPool
    else:
        # Standard PostgreSQL / Session Pooler
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
        engine_kwargs["pool_recycle"] = 300

    if "sslmode" not in db_url.lower() and "localhost" not in db_url and "127.0.0.1" not in db_url:
        engine_kwargs.setdefault("connect_args", {})["sslmode"] = "require"

engine = create_engine(db_url, **engine_kwargs)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        # SQLite otherwise silently ignores ondelete and foreign key constraints.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and handles transaction cleanup."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
