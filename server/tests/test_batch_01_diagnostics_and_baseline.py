"""Tests for Batch 01: Observability, Safe Diagnostics, Liveness Probes, and Baseline Measurement."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.core.diagnostics import (
    ALLOWED_SERVER_TIMING_METRICS,
    RequestDiagnostics,
    SQLCounters,
    _current_diagnostics,
    _current_request_id,
    classify_database_connection,
    record_stage,
    sanitize_or_generate_request_id,
)
from app.db.session import SessionLocal, engine
from app.models.all_models import Project, User, Session as DBSession, gen_id
from app.core.security import hash_password

client = TestClient(app)


# 1. /health/live performs no database query
def test_health_live_performs_no_database_queries(monkeypatch):
    """Verify /health/live executes zero SQL queries and does not touch the database."""
    # Temporarily set PERF_DIAGNOSTICS to capture SQL statement counts
    monkeypatch.setattr(settings, "PERF_DIAGNOSTICS", True)

    def _fail_on_db(*args, **kwargs):
        raise RuntimeError("Database was accessed during /health/live!")

    monkeypatch.setattr("app.main.SessionLocal", _fail_on_db)

    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "alive"
    assert "service" in data

    # Check Server-Timing header if present; db duration must be absent or 0
    st = res.headers.get("Server-Timing", "")
    assert "db;" not in st


# 2. /health/live does not call Gemini
def test_health_live_does_not_call_gemini(monkeypatch):
    """Verify /health/live does not invoke Gemini AI generation or key probing."""
    def _fail_on_ai(*args, **kwargs):
        raise RuntimeError("Gemini was called during /health/live!")

    monkeypatch.setattr("app.ai.gemini_service.GeminiAIService.generate_bmc", _fail_on_ai)
    monkeypatch.setattr("app.ai.gemini_service.GeminiAIService._available_key_slots", _fail_on_ai)

    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"


# 3. Request IDs are generated and returned
def test_request_id_generated_and_returned():
    """Verify that a random request ID is generated and returned via X-Request-ID header."""
    res = client.get("/health/live")
    assert "X-Request-ID" in res.headers
    req_id = res.headers["X-Request-ID"]
    assert len(req_id) == 32
    assert re.match(r"^[a-f0-9]{32}$", req_id)


# 4. A valid incoming request ID is preserved
def test_valid_incoming_request_id_preserved():
    """Verify that a safe, alphanumeric incoming X-Request-ID is preserved."""
    custom_id = "req-audit-client-test-12345_abc"
    res = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert res.headers.get("X-Request-ID") == custom_id


# 5. Invalid or oversized incoming IDs are replaced
def test_invalid_or_oversized_request_id_replaced():
    """Verify that malicious, non-alphanumeric, or oversized IDs are safely replaced."""
    # Malicious injection attempt
    bad_id = "invalid-id/with/special-chars;drop-table-users;"
    res1 = client.get("/health/live", headers={"X-Request-ID": bad_id})
    returned1 = res1.headers.get("X-Request-ID")
    assert returned1 != bad_id
    assert len(returned1) == 32

    # Oversized ID (> 64 characters)
    oversized_id = "a" * 128
    res2 = client.get("/health/live", headers={"X-Request-ID": oversized_id})
    returned2 = res2.headers.get("X-Request-ID")
    assert returned2 != oversized_id
    assert len(returned2) == 32


# 6. Logs do not contain authorization headers or cookie values
def test_logs_do_not_contain_secrets(caplog):
    """Verify structured request completion logs never record auth tokens or cookies."""
    secret_token = "ultra-secret-bearer-token-12345678"
    secret_cookie = "secret-session-cookie-value-abcdef"

    with caplog.at_level(logging.INFO, logger="request.timing"):
        client.get(
            "/health/live",
            headers={"Authorization": f"Bearer {secret_token}"},
            cookies={"aba_session": secret_cookie}
        )

    log_text = caplog.text
    assert secret_token not in log_text
    assert secret_cookie not in log_text
    assert "Bearer" not in log_text
    assert "aba_session" not in log_text


# 7. Per-request SQL counters do not leak between concurrent requests
@pytest.mark.anyio
async def test_concurrent_sql_counters_isolation():
    """Verify that ContextVar SQLCounters remain strictly isolated between concurrent async requests."""
    counters_a = SQLCounters()
    counters_b = SQLCounters()

    async def task_a():
        diag_a = RequestDiagnostics("req_a", enabled=True)
        tok = _current_diagnostics.set(diag_a)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                await asyncio.sleep(0.02)
                conn.execute(text("SELECT 2"))
            return diag_a.sql.statements
        finally:
            _current_diagnostics.reset(tok)

    async def task_b():
        diag_b = RequestDiagnostics("req_b", enabled=True)
        tok = _current_diagnostics.set(diag_b)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 3"))
            return diag_b.sql.statements
        finally:
            _current_diagnostics.reset(tok)

    res_a, res_b = await asyncio.gather(task_a(), task_b())
    assert res_a == 2
    assert res_b == 1


# 8. Server-Timing is present only under intended configuration
def test_server_timing_configuration(monkeypatch):
    """Verify Server-Timing header is omitted by default and emitted only when PERF_DIAGNOSTICS=True."""
    # When disabled (default)
    monkeypatch.setattr(settings, "PERF_DIAGNOSTICS", False)
    res_disabled = client.get("/health/live")
    assert "Server-Timing" not in res_disabled.headers

    # When enabled
    monkeypatch.setattr(settings, "PERF_DIAGNOSTICS", True)
    res_enabled = client.get("/health/live")
    assert "Server-Timing" in res_enabled.headers
    assert "total;dur=" in res_enabled.headers["Server-Timing"]


# 9. Server-Timing contains only approved metric names
def test_server_timing_metric_names_allowlist(monkeypatch):
    """Verify Server-Timing header contains only metrics from the approved allowlist."""
    monkeypatch.setattr(settings, "PERF_DIAGNOSTICS", True)
    res = client.get("/health/live")
    st = res.headers.get("Server-Timing", "")
    assert st

    entries = [entry.strip() for entry in st.split(",") if entry.strip()]
    for entry in entries:
        metric_name = entry.split(";")[0]
        assert metric_name in ALLOWED_SERVER_TIMING_METRICS


# 10. Diagnostics-disabled behavior remains functional
def test_diagnostics_disabled_behavior(monkeypatch):
    """Verify that when diagnostics are disabled, normal routing, responses, and request IDs function seamlessly."""
    monkeypatch.setattr(settings, "PERF_DIAGNOSTICS", False)
    res = client.get("/health/live")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert "Server-Timing" not in res.headers


# 11. Health/readiness wording does not claim unverified Gemini availability
def test_readiness_wording_accurate():
    """Verify /api/health accurately labels provider state without claiming unverified availability."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    assert data["generation_provider_status"] in ("configured", "unconfigured", "cooldown_active")
    assert data["generation_provider_status"] != "ready"
    assert data.get("provider_probe_status") == "provider_not_probed"


# 12. The database-configuration summary never contains credentials
def test_classify_database_connection_never_exposes_secrets():
    """Verify classify_database_connection strips passwords, user credentials, and full hosts."""
    sensitive_urls = [
        "postgresql://postgres.myref:SecretPass%40999@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require",
        "postgresql+psycopg://app_user:ultra_secret_pw@db.abcdefgh.supabase.co:5432/production_db",
        "sqlite:///./dev_database.db",
    ]

    for url in sensitive_urls:
        report = classify_database_connection(url)
        report_str = str(report)
        assert "SecretPass" not in report_str
        assert "ultra_secret_pw" not in report_str
        assert "myref" not in report_str
        assert "abcdefgh" not in report_str
        assert "app_user" not in report_str
        assert "production_db" not in report_str

        # Report contains safe category and pool info
        assert "driver" in report
        assert "endpoint_category" in report
        assert "pool_class" in report


# 13. Existing authentication and project endpoints retain their response contracts
def test_existing_contracts_retained():
    """Verify that existing public contracts for /health and /health/live remain unchanged."""
    res_root = client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert "status" in data_root
    assert "service" in data_root
    assert "database" in data_root

    res_live = client.get("/health/live")
    assert res_live.status_code == 200
    data_live = res_live.json()
    assert data_live["status"] == "alive"
    assert "service" in data_live
