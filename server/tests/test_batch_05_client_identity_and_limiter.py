"""
Batch 05 — Comprehensive Client Identity, Trusted Proxy Boundary,
and Authentication Abuse Protection Test Suite.
Addresses audit finding S02 and registration-admission abuse protection.
"""

from datetime import datetime, timedelta, timezone
import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.main import app
from app.core.config import settings
from app.models.all_models import User, Session as DBSession, AuthRateLimitEvent, gen_id
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.core.client_identity import (
    extract_client_ip,
    CLIENT_ID_MISSING,
    CLIENT_ID_MALFORMED
)
from app.core.auth_limiter import (
    normalize_account_identifier,
    hash_key,
    check_rate_limit,
    record_attempt,
    clear_attempts,
    reset_auth_limiter_state,
    SCOPE_LOGIN_IP,
    SCOPE_LOGIN_ACCOUNT,
    SCOPE_ADMIN_LOGIN_IP,
    SCOPE_ADMIN_LOGIN_ACCOUNT,
    SCOPE_REGISTER_IP
)

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

def create_user_fixture(
    db: Session,
    username: str,
    email: str,
    role: str = "user",
    password: str = "Password123!"
) -> User:
    """Helper to seed test user with known password."""
    user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if user:
        user.role = role
        user.hashed_password = hash_password(password)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        id=gen_id("usr_"),
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_suspended=False,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ==============================================================================
# 1. Client Identity & Proxy Trust Boundary Unit Tests
# ==============================================================================

class DummyRequest:
    def __init__(self, host=None, headers=None):
        self.client = DummyClient(host) if host is not None else None
        self.headers = headers or {}

class DummyClient:
    def __init__(self, host):
        self.host = host

def test_extract_client_ip_missing_client():
    req = DummyRequest(host=None)
    assert extract_client_ip(req) == CLIENT_ID_MISSING
    req_empty = DummyRequest(host="   ")
    assert extract_client_ip(req_empty) == CLIENT_ID_MISSING

def test_extract_client_ip_untrusted_peer_ignores_forwarded_headers():
    # Peer is 203.0.113.5 (untrusted). It sends spoofed X-Forwarded-For.
    req = DummyRequest(
        host="203.0.113.5",
        headers={"X-Forwarded-For": "198.51.100.99, 10.0.0.1"}
    )
    # Default trusted_proxies is empty -> peer IP must be returned
    assert extract_client_ip(req, trusted_proxies=[]) == "203.0.113.5"
    # Even if trusted_proxies is configured with a different IP
    assert extract_client_ip(req, trusted_proxies=["127.0.0.1", "10.0.0.0/8"]) == "203.0.113.5"

def test_extract_client_ip_trusted_peer_traverses_right_to_left():
    # Peer is 10.0.0.1 (trusted reverse proxy).
    # X-Forwarded-For: client_ip, intermediate_proxy
    trusted = ["10.0.0.0/8", "127.0.0.1"]
    req = DummyRequest(
        host="10.0.0.1",
        headers={"X-Forwarded-For": "198.51.100.42, 10.0.0.2"}
    )
    # 10.0.0.2 is in 10.0.0.0/8 (trusted), so traversal steps left to 198.51.100.42 (untrusted -> client)
    assert extract_client_ip(req, trusted_proxies=trusted) == "198.51.100.42"

def test_extract_client_ip_all_hops_trusted():
    trusted = ["10.0.0.0/8", "127.0.0.1"]
    req = DummyRequest(
        host="10.0.0.1",
        headers={"X-Forwarded-For": "10.0.0.99, 10.0.0.2"}
    )
    # When all hops are trusted proxies, leftmost hop is the client
    assert extract_client_ip(req, trusted_proxies=trusted) == "10.0.0.99"

def test_extract_client_ip_malformed_and_oversized_headers():
    trusted = ["127.0.0.1"]
    # Malformed IP syntax
    req_malformed = DummyRequest(
        host="127.0.0.1",
        headers={"X-Forwarded-For": "not-an-ip-address"}
    )
    assert extract_client_ip(req_malformed, trusted_proxies=trusted) == CLIENT_ID_MALFORMED

    # Oversized header (> 512 chars)
    req_oversized = DummyRequest(
        host="127.0.0.1",
        headers={"X-Forwarded-For": "1.1.1.1, " * 60}
    )
    assert extract_client_ip(req_oversized, trusted_proxies=trusted) == CLIENT_ID_MALFORMED

    # Too many hops (> 10 hops)
    req_too_many_hops = DummyRequest(
        host="127.0.0.1",
        headers={"X-Forwarded-For": ", ".join(["192.168.1.1"] * 12)}
    )
    assert extract_client_ip(req_too_many_hops, trusted_proxies=trusted) == CLIENT_ID_MALFORMED

def test_extract_client_ip_ipv6_handling():
    trusted = ["::1", "fe80::/10"]
    # Direct IPv6 peer
    req_ipv6 = DummyRequest(host="2001:db8::1")
    assert extract_client_ip(req_ipv6) == "2001:db8::1"

    # Forwarded IPv6 through trusted loopback
    req_fwd_ipv6 = DummyRequest(
        host="::1",
        headers={"X-Forwarded-For": "2001:db8::cafe"}
    )
    assert extract_client_ip(req_fwd_ipv6, trusted_proxies=trusted) == "2001:db8::cafe"

    # Brackets stripped safely
    req_bracket = DummyRequest(host="[2001:db8::1]")
    assert extract_client_ip(req_bracket) == "2001:db8::1"


# ==============================================================================
# 2. Public User Login Rate Limiting Tests
# ==============================================================================

def test_public_login_ip_threshold_and_retry_after(client, db):
    """5 failed logins from the same client IP must trigger 429 with Retry-After header."""
    user = create_user_fixture(db, "lim_test_user_1", "lim_test_user_1@test.com", password="CorrectPassword123!")

    # 5 failed attempts
    for i in range(5):
        resp = client.post("/api/auth/login", json={
            "email_or_username": user.username,
            "password": "WrongPassword!"
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email/username or password"

    # 6th attempt must be rejected with 429
    resp_blocked = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "WrongPassword!"
    })
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too many failed login attempts. Please try again later."
    assert "Retry-After" in resp_blocked.headers
    retry_after = int(resp_blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 900

def test_public_login_forged_x_forwarded_for_cannot_bypass_limits(client, db):
    """Untrusted clients attempting to rotate X-Forwarded-For remain throttled on their real connection."""
    user = create_user_fixture(db, "lim_test_user_forge", "lim_test_user_forge@test.com", password="CorrectPassword123!")

    # Attacker tries sending rotating X-Forwarded-For headers
    for i in range(5):
        resp = client.post(
            "/api/auth/login",
            json={"email_or_username": user.username, "password": "WrongPassword!"},
            headers={"X-Forwarded-For": f"198.51.100.{i+1}"}
        )
        assert resp.status_code == 401

    # 6th attempt with another new fake IP is still blocked
    resp_blocked = client.post(
        "/api/auth/login",
        json={"email_or_username": user.username, "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "198.51.100.99"}
    )
    assert resp_blocked.status_code == 429

def test_public_login_account_scoped_protection_across_changing_ips(client, db, monkeypatch):
    """Attacking the same account across different IPs triggers account-scoped protection."""
    user = create_user_fixture(db, "victim_account", "victim_account@test.com", password="CorrectPassword123!")

    # Enable 127.0.0.1 as a trusted proxy so client can simulate upstream proxies presenting distinct client IPs
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["testclient", "127.0.0.1"])

    # 5 attempts across 5 distinct IP addresses targeting the same victim account
    for i in range(5):
        resp = client.post(
            "/api/auth/login",
            json={"email_or_username": user.username, "password": "WrongPassword!"},
            headers={"X-Forwarded-For": f"203.0.113.{i+10}"}
        )
        assert resp.status_code == 401

    # 6th attempt from a brand-new 6th IP address targeting victim_account is blocked by account-scoped bucket
    resp_blocked = client.post(
        "/api/auth/login",
        json={"email_or_username": user.username, "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "203.0.113.99"}
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too many failed login attempts. Please try again later."

def test_different_accounts_do_not_share_account_bucket(client, db, monkeypatch):
    """Failed logins on User A do not consume User B's account bucket."""
    user_a = create_user_fixture(db, "target_user_a", "target_user_a@test.com", password="Password123!")
    user_b = create_user_fixture(db, "target_user_b", "target_user_b@test.com", password="Password123!")

    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["testclient"])

    # 5 failed attempts on User A from IP A
    for i in range(5):
        client.post(
            "/api/auth/login",
            json={"email_or_username": user_a.username, "password": "WrongPassword!"},
            headers={"X-Forwarded-For": "198.51.100.1"}
        )

    # User B from IP B can still attempt login normally
    resp_b = client.post(
        "/api/auth/login",
        json={"email_or_username": user_b.username, "password": "Password123!"},
        headers={"X-Forwarded-For": "198.51.100.2"}
    )
    assert resp_b.status_code == 200

def test_successful_login_resets_failed_counter(client, db):
    """Successful login resets account failed attempt counter."""
    user = create_user_fixture(db, "reset_counter_user", "reset_counter_user@test.com", password="CorrectPassword123!")

    # 4 failed attempts (1 below threshold)
    for _ in range(4):
        resp = client.post("/api/auth/login", json={
            "email_or_username": user.username,
            "password": "WrongPassword!"
        })
        assert resp.status_code == 401

    # Successful login
    resp_ok = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "CorrectPassword123!"
    })
    assert resp_ok.status_code == 200

    # Next failed attempt starts counter fresh, does not trigger 429
    resp_fresh = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "WrongPassword!"
    })
    assert resp_fresh.status_code == 401


# ==============================================================================
# 3. Administrative Login Rate Limiting Tests
# ==============================================================================

def test_admin_login_stricter_account_threshold(client, db, monkeypatch):
    """Admin login enforces a stricter 3-attempt account threshold."""
    admin = create_user_fixture(db, "sa_lim_test", "sa_lim_test@test.com", role="super_admin", password="AdminPassword123!")
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["testclient"])

    # 3 failed attempts on admin account across 3 distinct IPs
    for i in range(3):
        resp = client.post(
            "/api/admin/auth/login",
            json={"username": admin.username, "password": "WrongPassword!"},
            headers={"X-Forwarded-For": f"192.0.2.{i+1}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid administrator credentials"

    # 4th attempt from a 4th IP is blocked by account threshold
    resp_blocked = client.post(
        "/api/admin/auth/login",
        json={"username": admin.username, "password": "WrongPassword!"},
        headers={"X-Forwarded-For": "192.0.2.99"}
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too many failed login attempts. Please try again later."
    assert "Retry-After" in resp_blocked.headers

def test_admin_login_ip_threshold(client, db):
    """5 failed attempts on admin login from same IP trigger 429."""
    for i in range(5):
        resp = client.post("/api/admin/auth/login", json={
            "username": f"nonexistent_admin_{i}",
            "password": "WrongPassword!"
        })
        assert resp.status_code == 401

    resp_blocked = client.post("/api/admin/auth/login", json={
        "username": "another_admin",
        "password": "WrongPassword!"
    })
    assert resp_blocked.status_code == 429


# ==============================================================================
# 4. Registration Admission Protection Tests
# ==============================================================================

def test_registration_admission_limit_applies_before_password_hashing(client, db, monkeypatch):
    """Registration attempts from the same network are bounded before expensive Argon2 password hashing."""
    hash_calls = []
    original_hash = hash_password

    def tracking_hash(pwd):
        hash_calls.append(pwd)
        return original_hash(pwd)

    monkeypatch.setattr("app.api.auth.hash_password", tracking_hash)

    # 5 registration attempts (AUTH_REGISTER_IP_MAX_ATTEMPTS=5)
    for i in range(5):
        resp = client.post("/api/auth/register", json={
            "username": f"reg_user_{i}",
            "email": f"reg_user_{i}@test.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "terms_accepted": True
        })
        assert resp.status_code == 201

    assert len(hash_calls) == 5

    # 6th attempt is blocked by admission limit before calling hash_password!
    resp_blocked = client.post("/api/auth/register", json={
        "username": "reg_user_excess",
        "email": "reg_user_excess@test.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    })
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["detail"] == "Too many registration attempts from this network. Please try again later."
    assert "Retry-After" in resp_blocked.headers

    # Argon2 was NOT called on the blocked attempt!
    assert len(hash_calls) == 5

def test_registration_failed_validations_count_toward_admission_budget(client, db):
    """Invalid requests (e.g. password mismatch) still count against the admission limit to prevent CPU abuse."""
    for i in range(5):
        resp = client.post("/api/auth/register", json={
            "username": f"mismatch_{i}",
            "email": f"mismatch_{i}@test.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
            "terms_accepted": True
        })
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Passwords do not match"

    # 6th attempt is blocked with 429
    resp_blocked = client.post("/api/auth/register", json={
        "username": "mismatch_6",
        "email": "mismatch_6@test.com",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "terms_accepted": True
    })
    assert resp_blocked.status_code == 429


# ==============================================================================
# 5. Security & Isolation Properties
# ==============================================================================

def test_no_passwords_or_tokens_stored_in_limiter_records(client, db):
    """Verify that limiter records only contain scope, key_hash, and timestamp (no credentials or tokens)."""
    client.post("/api/auth/login", json={
        "email_or_username": "secret_user@test.com",
        "password": "UltraSecretPassword123!"
    })

    records = db.query(AuthRateLimitEvent).all()
    assert len(records) >= 1
    for r in records:
        assert len(r.key_hash) == 64
        # Verify no plaintext user or password exists in key_hash
        assert "secret_user" not in r.key_hash
        assert "UltraSecretPassword123!" not in r.key_hash
        assert "Password" not in r.key_hash

def test_sentinel_strings_remain_limited(client, db):
    """Sentinels like 'testclient' and 'unknown' cannot bypass rate limiting."""
    for _ in range(5):
        resp = client.post("/api/auth/login", json={
            "email_or_username": "nonexistent@test.com",
            "password": "badpassword"
        })
        assert resp.status_code == 401

    resp_blocked = client.post("/api/auth/login", json={
        "email_or_username": "nonexistent@test.com",
        "password": "badpassword"
    })
    assert resp_blocked.status_code == 429

def test_limiter_expiry_with_controllable_clock(db):
    """Attempts older than the window expire and allow new requests."""
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    scope = SCOPE_LOGIN_IP
    ip = "192.0.2.1"

    # Record 5 attempts at base_time
    for _ in range(5):
        record_attempt(scope, ip, now=base_time)

    # At base_time + 10s: blocked
    with pytest.raises(Exception) as exc_info:
        check_rate_limit(db, scope, ip, max_attempts=5, window_seconds=900, detail="blocked", now=base_time + timedelta(seconds=10))
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) == 890

    # At base_time + 901s: window has elapsed, check passes cleanly
    check_rate_limit(db, scope, ip, max_attempts=5, window_seconds=900, detail="blocked", now=base_time + timedelta(seconds=901))

def test_failure_responses_do_not_reveal_account_existence(client, db):
    """Invalid password for existing user and non-existent user yield identical 401 responses."""
    user = create_user_fixture(db, "real_user_account", "real_user_account@test.com", password="CorrectPassword123!")

    # Existing user with bad password
    resp_real = client.post("/api/auth/login", json={
        "email_or_username": user.username,
        "password": "WrongPassword123!"
    })

    # Non-existent user
    resp_fake = client.post("/api/auth/login", json={
        "email_or_username": "completely_fake_account_xyz",
        "password": "WrongPassword123!"
    })

    assert resp_real.status_code == 401
    assert resp_fake.status_code == 401
    assert resp_real.json() == resp_fake.json() == {"detail": "Invalid email/username or password"}

def test_parallel_requests_cannot_trivially_bypass_registration_limit(client, db):
    """Concurrent attempts are serialized and properly bounded."""
    results = []
    threads = []

    def make_attempt(idx):
        with TestClient(app) as local_cli:
            resp = local_cli.post("/api/auth/register", json={
                "username": f"par_user_{idx}",
                "email": f"par_user_{idx}@test.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "terms_accepted": True
            })
            results.append(resp.status_code)

    # Launch 8 parallel registration attempts (limit is 5)
    for i in range(8):
        t = threading.Thread(target=make_attempt, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5.0)

    # Exactly 5 succeeded (201) and 3 were blocked (429)
    successes = [code for code in results if code == 201]
    throttled = [code for code in results if code == 429]

    assert len(successes) == 5, f"Expected 5 successes, got {len(successes)}: {results}"
    assert len(throttled) == 3, f"Expected 3 throttled (429), got {len(throttled)}: {results}"
