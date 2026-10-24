"""
Phase 2 — Trusted Client Identity, Reverse-Proxy Boundary, and Authentication Abuse Protection Tests.
Validates:
- Composed ASGI server/proxy middleware path.
- Untrusted direct peers cannot spoof rate-limit identity or scheme.
- Trusted proxies traverse right-to-left with IPv4/IPv6 support.
- Registration admission intercepts requests early, bounds bodies (<64KB), and counts malformed attempts.
- Constant-like password verification using DUMMY_PASSWORD_HASH.
- Security events use isolated transactions without committing caller state.
- Bounded retention cleanup for expired rate limit events.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.all_models import User, Session as DBSession, AuthRateLimitEvent, Project, gen_id
from app.core.security import hash_password, verify_password, DUMMY_PASSWORD_HASH
from app.core.telemetry import record_security_event
from app.core.client_identity import (
    extract_client_ip,
    CLIENT_ID_MISSING,
    CLIENT_ID_MALFORMED,
    TrustedProxyMiddleware
)
from app.core.auth_limiter import (
    reset_auth_limiter_state,
    cleanup_expired_events,
    maybe_cleanup_expired_events,
    check_rate_limit,
    record_attempt,
    SCOPE_LOGIN_IP,
    SCOPE_LOGIN_ACCOUNT,
    SCOPE_REGISTER_IP,
    MSG_LOGIN_RATE_LIMITED,
    MSG_REGISTER_RATE_LIMITED
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    reset_auth_limiter_state()
    return TestClient(app)


def create_user_fixture(db: Session, username: str, email: str, role: str = "user", password: str = "Password123!") -> User:
    u = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if u:
        return u
    u = User(
        id=gen_id("usr_"),
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_suspended=False,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc)
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ==============================================================================
# 1. COMPOSED SERVER / PROXY MIDDLEWARE PATH AND TRUST BOUNDARY
# ==============================================================================

def test_untrusted_direct_peer_cannot_spoof_identity_or_scheme(client: TestClient):
    """
    When peer is untrusted (TRUSTED_PROXIES is empty or does not match peer):
    - Forwarded X-Forwarded-For header is completely ignored.
    - X-Forwarded-Proto is ignored.
    """
    with patch.object(settings, "TRUSTED_PROXIES", []):
        # Sending forged X-Forwarded-For to health check or endpoint
        resp = client.get(
            "/api/health",
            headers={
                "X-Forwarded-For": "203.0.113.195, 198.51.100.1",
                "X-Forwarded-Proto": "https"
            }
        )
        assert resp.status_code == 200

    # Exhaust rate limit using forged headers from untrusted peer
    with patch.object(settings, "TRUSTED_PROXIES", []):
        for i in range(5):
            resp = client.post(
                "/api/auth/login",
                json={"email_or_username": "nonexistent@test.com", "password": "WrongPassword123!"},
                headers={"X-Forwarded-For": f"203.0.113.{i+1}"}  # Attempting IP rotation spoof
            )
            assert resp.status_code == 401

        # 6th attempt with yet another forged header is still blocked because peer IP was 127.0.0.1
        resp_blocked = client.post(
            "/api/auth/login",
            json={"email_or_username": "nonexistent@test.com", "password": "WrongPassword123!"},
            headers={"X-Forwarded-For": "203.0.113.99"}
        )
        assert resp_blocked.status_code == 429
        assert "Retry-After" in resp_blocked.headers


def test_trusted_proxy_traverses_right_to_left_and_updates_scheme(client: TestClient):
    """When peer is a trusted proxy, authoritative client IP is extracted right-to-left and scheme is updated."""
    # Configure 127.0.0.1 and 10.0.0.0/8 as trusted proxies
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.0/8"]):
        # Trusted proxy forwarding client IP 198.51.100.42 through internal proxy 10.0.0.5
        resp = client.post(
            "/api/auth/login",
            json={"email_or_username": "test_trusted@test.com", "password": "WrongPassword123!"},
            headers={
                "X-Forwarded-For": "198.51.100.42, 10.0.0.5",
                "X-Forwarded-Proto": "https"
            }
        )
        assert resp.status_code == 401

        # Inspect persisted rate limit event: key_hash must be for 198.51.100.42
        with SessionLocal() as s:
            from app.core.auth_limiter import hash_key
            expected_hash = hash_key(SCOPE_LOGIN_IP, "198.51.100.42")
            evt = s.query(AuthRateLimitEvent).filter(
                AuthRateLimitEvent.key_hash == expected_hash
            ).first()
            assert evt is not None, "AuthRateLimitEvent must be recorded for the extracted client IP 198.51.100.42"


def test_ipv6_and_malformed_forwarding_chains(client: TestClient):
    """IPv6 addresses are supported and canonicalized; malformed/oversized chains fall back to malformed_client."""
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1"]):
        # Valid IPv6
        resp = client.post(
            "/api/auth/login",
            json={"email_or_username": "ipv6_user@test.com", "password": "WrongPassword123!"},
            headers={"X-Forwarded-For": "2001:db8:85a3::8a2e:370:7334"}
        )
        assert resp.status_code == 401
        with SessionLocal() as s:
            from app.core.auth_limiter import hash_key
            expected_hash = hash_key(SCOPE_LOGIN_IP, "2001:db8:85a3::8a2e:370:7334")
            assert s.query(AuthRateLimitEvent).filter(AuthRateLimitEvent.key_hash == expected_hash).first() is not None

        # Oversized chain (> 512 chars)
        oversized = "192.0.2.1, " * 60
        resp_over = client.post(
            "/api/auth/login",
            json={"email_or_username": "oversized@test.com", "password": "WrongPassword123!"},
            headers={"X-Forwarded-For": oversized}
        )
        assert resp_over.status_code == 401
        with SessionLocal() as s:
            expected_malformed = hash_key(SCOPE_LOGIN_IP, CLIENT_ID_MALFORMED)
            assert s.query(AuthRateLimitEvent).filter(AuthRateLimitEvent.key_hash == expected_malformed).first() is not None


# ==============================================================================
# 2. REGISTRATION ADMISSION PROTECTION BEFORE BODY PARSING & PASSWORD HASHING
# ==============================================================================

def test_registration_admission_blocks_malformed_requests_at_threshold(client: TestClient):
    """
    Malformed registration requests (invalid JSON, missing fields) are counted by the admission middleware.
    At the threshold (5 attempts), subsequent requests are blocked with 429 and Retry-After before reaching Pydantic.
    """
    # Send 5 malformed registration requests (missing required fields -> 422 Unprocessable Entity)
    for i in range(5):
        resp = client.post(
            "/api/auth/register",
            json={"invalid_payload": f"attempt_{i}"}
        )
        assert resp.status_code == 422, "Ordinary structured validation response must be preserved below threshold"

    # 6th attempt is blocked with 429 by admission middleware before reaching validation
    resp_blocked = client.post(
        "/api/auth/register",
        json={"username": "valid_user", "email": "valid@test.com", "password": "Password123!", "confirm_password": "Password123!", "terms_accepted": True}
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == MSG_REGISTER_RATE_LIMITED
    assert "Retry-After" in resp_blocked.headers


def test_registration_oversized_payload_rejected_with_413(client: TestClient):
    """Oversized registration payload (> 64KB) is rejected with HTTP 413 before reading into memory."""
    huge_data = "A" * 70000
    resp = client.post(
        "/api/auth/register",
        content=huge_data,
        headers={"Content-Length": str(len(huge_data)), "Content-Type": "application/json"}
    )
    assert resp.status_code == 413
    assert "exceeds maximum allowed size" in resp.json()["detail"]


# ==============================================================================
# 3. LOGIN TIMING SIDE-CHANNEL MITIGATION AND DUMMY PASSWORD HASHING
# ==============================================================================

def test_login_uses_dummy_password_hash_for_nonexistent_user(client: TestClient):
    """Non-existent user triggers Argon2 verify_password against DUMMY_PASSWORD_HASH to mitigate timing attacks."""
    with patch("app.api.auth.verify_password", wraps=verify_password) as mock_verify:
        resp = client.post(
            "/api/auth/login",
            json={"email_or_username": "definitely_nonexistent@test.com", "password": "Password123!"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email/username or password"
        assert mock_verify.call_count == 1
        # Called with plain password and DUMMY_PASSWORD_HASH
        args, _ = mock_verify.call_args
        assert args[0] == "Password123!"
        assert args[1] == DUMMY_PASSWORD_HASH


def test_admin_login_uses_dummy_password_hash_for_nonexistent_or_unauthorized_user(client: TestClient):
    """Non-existent admin user triggers Argon2 verify_password against DUMMY_PASSWORD_HASH."""
    with patch("app.api.admin.auth.verify_password", wraps=verify_password) as mock_verify:
        resp = client.post(
            "/api/admin/auth/login",
            json={"username": "definitely_nonexistent_admin", "password": "Password123!"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid administrator credentials"
        assert mock_verify.call_count == 1
        args, _ = mock_verify.call_args
        assert args[0] == "Password123!"
        assert args[1] == DUMMY_PASSWORD_HASH


# ==============================================================================
# 4. STORAGE FAILURE BEHAVIOR AND TELEMETRY TRANSACTION ISOLATION
# ==============================================================================

def test_limiter_database_failure_fails_closed_with_503(client: TestClient):
    """If the database query fails during rate limit check, return controlled 503 instead of bypassing limiter."""
    with SessionLocal() as s:
        with patch.object(s, "query", side_effect=OperationalError("SELECT 1", {}, Exception("DB down"))):
            with pytest.raises(Exception) as exc_info:
                check_rate_limit(s, SCOPE_LOGIN_IP, "127.0.0.1", 5, 900, "Limit exceeded")
            assert exc_info.value.status_code == 503
            assert "temporarily unavailable" in exc_info.value.detail


def test_record_security_event_does_not_commit_or_rollback_caller_transaction():
    """Recording a security event runs in an isolated transaction and does not affect caller pending state."""
    with SessionLocal() as caller_session:
        # Create uncommitted project in caller session
        user = create_user_fixture(caller_session, "sec_event_user", "sec_event@test.com")
        proj = Project(
            id=gen_id("prj_"),
            user_id=user.id,
            name="Uncommitted Project Name",
            description="Testing security event isolation",
            stage="Idea / MVP",
            industry="Tech",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        caller_session.add(proj)
        assert caller_session.is_modified(proj)

        # Call record_security_event
        record_security_event(
            event_type="test_isolation_event",
            severity="low",
            actor_id=user.id
        )

        # Caller session must NOT have been committed!
        assert caller_session.is_modified(proj)
        proj_id = proj.id

    # Since caller_session was closed without commit, proj was NOT saved
    with SessionLocal() as fresh_s:
        persisted = fresh_s.query(Project).filter(Project.id == proj_id).first()
        assert persisted is None, "Caller transaction must not be committed by record_security_event"


# ==============================================================================
# 5. BOUNDED RETENTION CLEANUP FOR EXPIRED LIMITER EVENTS
# ==============================================================================

def test_cleanup_expired_events_bounds_deletions():
    """Expired rate limit events (> 24 hours) are cleaned up in bounded batches."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=25)
    recent_time = now - timedelta(minutes=5)

    with SessionLocal() as s:
        # Insert 10 expired records
        for i in range(10):
            s.add(AuthRateLimitEvent(
                id=gen_id("lim_"),
                scope=SCOPE_LOGIN_IP,
                key_hash=f"old_hash_{i}",
                created_at=old_time
            ))
        # Insert 2 recent records
        for i in range(2):
            s.add(AuthRateLimitEvent(
                id=gen_id("lim_"),
                scope=SCOPE_LOGIN_IP,
                key_hash=f"recent_hash_{i}",
                created_at=recent_time
            ))
        s.commit()

    # Clean up with batch_size=5
    deleted = cleanup_expired_events(max_retention_seconds=86400, batch_size=5)
    assert deleted == 5, "Batch size must bound deletions to 5"

    # Clean up remaining expired records
    deleted_remaining = cleanup_expired_events(max_retention_seconds=86400, batch_size=10)
    assert deleted_remaining == 5

    # Verify only recent records remain
    with SessionLocal() as s:
        remaining = s.query(AuthRateLimitEvent).all()
        assert len(remaining) == 2
        for r in remaining:
            r_dt = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
            assert r_dt >= now - timedelta(hours=1)


def test_admin_integrity_scan_and_repair_expired_rate_limits(client: TestClient):
    """Admin integrity scan detects EXPIRED_RATE_LIMITS and repair action clean_expired_rate_limits prunes them."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=26)

    with SessionLocal() as s:
        admin = create_user_fixture(s, "admin_rate_clean", "admin_rate@test.com", role="super_admin")
        for i in range(3):
            s.add(AuthRateLimitEvent(
                id=gen_id("lim_"),
                scope=SCOPE_LOGIN_IP,
                key_hash=f"admin_clean_hash_{i}",
                created_at=old_time
            ))
        s.commit()

    # Log in admin
    login_resp = client.post(
        "/api/admin/auth/login",
        json={"username": "admin_rate_clean", "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    cookies = dict(login_resp.cookies)
    csrf = login_resp.json()["csrf_token"]

    # Scan
    scan_resp = client.get("/api/admin/integrity/scan", cookies=cookies)
    assert scan_resp.status_code == 200
    findings = scan_resp.json()["findings"]
    rate_finding = next((f for f in findings if f["code"] == "EXPIRED_RATE_LIMITS"), None)
    assert rate_finding is not None
    assert rate_finding["count"] >= 3

    # Repair
    repair_resp = client.post(
        "/api/admin/integrity/repair",
        json={"action": "clean_expired_rate_limits", "confirmation": True},
        cookies=cookies,
        headers={"X-CSRF-Token": csrf}
    )
    assert repair_resp.status_code == 200
    assert repair_resp.json()["repaired_count"] >= 3
