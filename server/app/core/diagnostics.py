"""Safe performance baseline diagnostics and request-stage observability.

Provides request correlation IDs, monotonic stage timing, per-request SQL counters,
safe Server-Timing headers, and sanitized database configuration inspection.
Never captures or logs SQL parameters, request bodies, auth headers, or cookies.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
import uuid
import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("request.timing")

# Request ID validation: strict alphanumeric, hyphen, underscore up to 64 chars
SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# Fixed allowlist of named diagnostic stages
ALLOWED_STAGES: Set[str] = {
    "maintenance_lookup",
    "auth_lookup",
    "auth_activity_write",
    "db_connection_wait",
    "project_query",
    "project_metadata_query",
    "module_query",
    "version_metadata_query",
    "serialization",
    "provider_call",
}

# Fixed allowlist of metric names for Server-Timing header
ALLOWED_SERVER_TIMING_METRICS: Set[str] = {
    "total",
    "maint",
    "auth",
    "db",
    "project",
    "module",
    "ai",
}


class SQLCounters:
    """Request-local counters for SQL execution, commits, and rollbacks."""
    __slots__ = ("statements", "commits", "rollbacks", "db_duration_ms")

    def __init__(self) -> None:
        self.statements: int = 0
        self.commits: int = 0
        self.rollbacks: int = 0
        self.db_duration_ms: float = 0.0


class RequestDiagnostics:
    """Request-local timing and diagnostic context."""
    __slots__ = ("request_id", "enabled", "start_time", "stages", "sql")

    def __init__(self, request_id: str, enabled: bool = False) -> None:
        self.request_id: str = request_id
        self.enabled: bool = enabled
        self.start_time: float = time.perf_counter()
        self.stages: Dict[str, float] = {}
        self.sql: SQLCounters = SQLCounters()

    def record_stage_duration(self, stage: str, duration_ms: float) -> None:
        if stage in ALLOWED_STAGES:
            self.stages[stage] = self.stages.get(stage, 0.0) + duration_ms

    def build_server_timing_header(self, total_duration_ms: float) -> Optional[str]:
        if not self.enabled:
            return None

        # Bounded duration helper
        def _fmt(val: float) -> str:
            bounded = max(0.0, min(val, 3600000.0))
            return f"{bounded:.1f}"

        parts: List[str] = [f"total;dur={_fmt(total_duration_ms)}"]

        maint_dur = self.stages.get("maintenance_lookup", 0.0)
        if maint_dur > 0:
            parts.append(f"maint;dur={_fmt(maint_dur)}")

        auth_dur = self.stages.get("auth_lookup", 0.0) + self.stages.get("auth_activity_write", 0.0)
        if auth_dur > 0:
            parts.append(f"auth;dur={_fmt(auth_dur)}")

        db_dur = self.sql.db_duration_ms
        if db_dur > 0:
            parts.append(f"db;dur={_fmt(db_dur)}")

        proj_dur = self.stages.get("project_query", 0.0) + self.stages.get("project_metadata_query", 0.0)
        if proj_dur > 0:
            parts.append(f"project;dur={_fmt(proj_dur)}")

        mod_dur = self.stages.get("module_query", 0.0) + self.stages.get("version_metadata_query", 0.0)
        if mod_dur > 0:
            parts.append(f"module;dur={_fmt(mod_dur)}")

        ai_dur = self.stages.get("provider_call", 0.0)
        if ai_dur > 0:
            parts.append(f"ai;dur={_fmt(ai_dur)}")

        return ", ".join(parts)


# Context variables providing strict request-local isolation across concurrent async tasks
_current_request_id: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)
_current_diagnostics: ContextVar[Optional[RequestDiagnostics]] = ContextVar("current_diagnostics", default=None)


def get_current_request_id() -> Optional[str]:
    """Retrieve the correlation ID of the currently executing request."""
    return _current_request_id.get()


def get_current_diagnostics() -> Optional[RequestDiagnostics]:
    """Retrieve the diagnostics context of the currently executing request."""
    return _current_diagnostics.get()


def sanitize_or_generate_request_id(incoming: Optional[str]) -> str:
    """Validate incoming request ID or generate a cryptographically random hexadecimal ID."""
    if incoming and isinstance(incoming, str):
        cleaned = incoming.strip()
        if SAFE_REQUEST_ID_REGEX.match(cleaned):
            return cleaned
    return uuid.uuid4().hex


@contextmanager
def record_stage(stage_name: str):
    """Context manager to measure and accumulate duration for a named request stage."""
    diag = _current_diagnostics.get()
    if diag is None or not diag.enabled or stage_name not in ALLOWED_STAGES:
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        diag.record_stage_duration(stage_name, elapsed_ms)


# Track registered SQLAlchemy engines to prevent duplicate event listener registration
_registered_engines: Set[int] = set()


def register_sql_diagnostics_listeners(engine: Any) -> None:
    """Attach non-intrusive event listeners to count SQL statements, commits, and rollbacks.

    Only counts events when an active request diagnostics context is present.
    Never logs SQL text, parameters, or schema secrets.
    """
    engine_id = id(engine)
    if engine_id in _registered_engines:
        return

    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def _on_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        diag = _current_diagnostics.get()
        if diag is not None and diag.enabled:
            # Store cursor execution start time safely on connection info dict
            conn.info["_diag_stmt_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _on_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        diag = _current_diagnostics.get()
        if diag is not None and diag.enabled:
            diag.sql.statements += 1
            t_start = conn.info.pop("_diag_stmt_start", None)
            if t_start is not None:
                diag.sql.db_duration_ms += (time.perf_counter() - t_start) * 1000.0

    @event.listens_for(engine, "commit")
    def _on_commit(conn):
        diag = _current_diagnostics.get()
        if diag is not None and diag.enabled:
            diag.sql.commits += 1

    @event.listens_for(engine, "rollback")
    def _on_rollback(conn):
        diag = _current_diagnostics.get()
        if diag is not None and diag.enabled:
            diag.sql.rollbacks += 1

    _registered_engines.add(engine_id)


def normalize_route_template(request: Request) -> str:
    """Extract low-cardinality route template without exposing user-provided IDs or query values."""
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        root_path = request.scope.get("root_path", "")
        return f"{root_path}{route.path}"

    raw_path = request.url.path
    # Normalize common resource IDs to prevent high-cardinality logging
    normalized = re.sub(r"/(proj_[a-zA-Z0-9_\-]+|[a-f0-9\-]{32,36}|\d+)", "/{id}", raw_path)
    return normalized


def classify_database_connection(url_string: Optional[str] = None) -> Dict[str, Any]:
    """Inspect and classify database connection parameters without exposing passwords, users, or host secrets."""
    from app.core.config import settings
    raw_url = url_string or settings.get_database_url()

    parsed = urllib.parse.urlsplit(raw_url)
    scheme = parsed.scheme.lower()

    if "+" in scheme:
        driver = scheme
    elif scheme == "postgresql":
        driver = "postgresql+psycopg2"
    elif scheme == "sqlite":
        driver = "sqlite"
    else:
        driver = scheme

    hostname = (parsed.hostname or "").lower()
    port = parsed.port

    if "pooler.supabase.com" in hostname:
        if port == 6543:
            endpoint_category = "supabase_transaction_pooler"
        elif port == 5432:
            endpoint_category = "supabase_session_pooler"
        else:
            endpoint_category = "supabase_pooler_custom_port"
    elif ".supabase.co" in hostname:
        endpoint_category = "supabase_direct"
    elif "sqlite" in scheme or ":memory:" in raw_url or raw_url.endswith(".db") or raw_url.endswith(".sqlite3"):
        endpoint_category = "local_sqlite"
        port = None
    elif "localhost" in hostname or "127.0.0.1" in hostname:
        endpoint_category = "local_postgresql"
    else:
        endpoint_category = "remote_postgresql"

    if endpoint_category == "local_sqlite":
        pool_class = "SingletonThreadPool / StaticPool"
        pool_size: Any = "not_applicable"
        max_overflow: Any = "not_applicable"
        pool_recycle: Any = "not_applicable"
    elif port == 6543:
        pool_class = "NullPool"
        pool_size = "not_applicable"
        max_overflow = "not_applicable"
        pool_recycle = "not_applicable"
    else:
        pool_class = "QueuePool"
        pool_size = 5
        max_overflow = 10
        pool_recycle = 300

    ssl_configured = "sslmode" in raw_url.lower()

    installed_drivers: List[str] = []
    try:
        import psycopg  # noqa: F401
        installed_drivers.append("psycopg_v3")
    except ImportError:
        pass

    try:
        import psycopg2  # noqa: F401
        installed_drivers.append("psycopg2_v2")
    except ImportError:
        pass

    return {
        "driver": driver,
        "endpoint_category": endpoint_category,
        "port": port,
        "pool_class": pool_class,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
        "ssl_configured": ssl_configured,
        "connect_timeout_seconds": "unset",
        "statement_timeout_seconds": "unset",
        "installed_pg_drivers": installed_drivers,
        "both_driver_families_required": len(installed_drivers) > 1,
    }
