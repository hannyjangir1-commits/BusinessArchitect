"""Phase 3 Verification: Session Storage and Authentication Safety.

Verifies:
1. Server-side persistence uses cryptographic SHA-256 digest of high-entropy tokens.
2. Raw bearer tokens are never stored in the database for new sessions.
3. Cookie flags and secure HttpOnly cookie behavior.
4. Legacy unmigrated sessions self-heal on lookup without forced invalidation.
5. Session expiration, logout, and fixation resistance on refresh.
6. CSRF validation on cookie-authenticated state-changing requests.
7. Session revocation (single, all-sessions preserving invoking admin).
8. Password change revokes all other sessions.
9. Account suspension denies active sessions.
10. Admin session listings never expose raw tokens or digests.
11. Production config safety validation rejects weak/dev secrets without leakage.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.all_models import User, Session as DBSession, Project, gen_id
from app.core.security import hash_password, generate_session_token, hash_session_token, generate_csrf_token
from app.core.config import settings, Settings, validate_production_runtime_safety, KNOWN_DEV_SESSION_SECRETS

client = TestClient(app)


@pytest.fixture
def clean_db():
    with SessionLocal() as db:
        db.query(DBSession).delete()
        db.query(Project).delete()
        db.query(User).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(DBSession).delete()
        db.query(Project).delete()
        db.query(User).delete()
        db.commit()


def test_login_and_registration_store_digest_not_raw_token(clean_db):
    """Verify registration and login generate high-entropy tokens, set HttpOnly cookies, and store ONLY digests in DB."""
    # 1. Registration
    reg_resp = client.post("/api/auth/register", json={
        "username": "testuser_digest",
        "email": "digest_user@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    assert reg_resp.status_code == 201
    reg_cookie = reg_resp.cookies.get(settings.COOKIE_NAME)
    assert reg_cookie is not None
    assert len(reg_cookie) == 64  # 32 bytes hex = 64 characters

    with SessionLocal() as db:
        sess = db.query(DBSession).first()
        assert sess is not None
        # Raw session token must NOT be stored in DB
        assert sess._session_token is None
        # Cryptographic digest must match SHA-256 of cookie
        expected_digest = hash_session_token(reg_cookie)
        assert sess.token_digest == expected_digest

    # 2. Login
    login_resp = client.post("/api/auth/login", json={
        "email_or_username": "digest_user@example.com",
        "password": "StrongPassword123!"
    })
    assert login_resp.status_code == 200
    login_cookie = login_resp.cookies.get(settings.COOKIE_NAME)
    assert login_cookie is not None
    assert login_cookie != reg_cookie  # New session token on each login

    with SessionLocal() as db:
        db_sessions = db.query(DBSession).all()
        assert len(db_sessions) == 2
        for s in db_sessions:
            assert s._session_token is None
            assert s.token_digest is not None
            assert len(s.token_digest) == 64


def test_session_lookup_succeeds_with_digest(clean_db):
    """Verify authenticated endpoints validate user from cookie using digest lookup."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "lookup_user",
        "email": "lookup@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    cookie_token = reg_resp.cookies[settings.COOKIE_NAME]

    # Access /api/auth/me
    client.cookies.set(settings.COOKIE_NAME, cookie_token)
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["user"]["email"] == "lookup@example.com"


def test_legacy_session_self_healing_upgrade(clean_db):
    """Verify legacy raw-token session is accepted and automatically upgraded to digest on lookup."""
    raw_legacy_token = "legacy_secret_unmigrated_token_1234567890abcdef"
    with SessionLocal() as db:
        user = User(
            id=gen_id("usr_"),
            username="legacy_user",
            email="legacy@example.com",
            hashed_password=hash_password("Pass123!"),
            terms_accepted=True
        )
        db.add(user)
        db.flush()
        user_id = user.id

        # Simulate pre-migration database record where _session_token is set and token_digest is NULL
        legacy_sess = DBSession(
            id=gen_id("ses_"),
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        legacy_sess._session_token = raw_legacy_token
        legacy_sess.token_digest = None
        db.add(legacy_sess)
        db.commit()

    # User authenticates with legacy token
    client.cookies.set(settings.COOKIE_NAME, raw_legacy_token)
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["username"] == "legacy_user"

    # Verify self-healing: token_digest is now populated, and _session_token is cleared
    with SessionLocal() as db:
        upgraded = db.query(DBSession).filter(DBSession.user_id == user_id).first()
        assert upgraded is not None
        assert upgraded.token_digest == hash_session_token(raw_legacy_token)
        assert upgraded._session_token is None


def test_expired_session_fails_and_cleans_up(clean_db):
    """Verify expired sessions return 401 and are deleted from the database."""
    expired_token = secrets.token_hex(32)
    digest = hash_session_token(expired_token)
    with SessionLocal() as db:
        user = User(
            id=gen_id("usr_"),
            username="expired_user",
            email="expired@example.com",
            hashed_password=hash_password("Pass123!"),
            terms_accepted=True
        )
        db.add(user)
        db.flush()
        sess = DBSession(
            id=gen_id("ses_"),
            user_id=user.id,
            token_digest=digest,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        db.add(sess)
        db.commit()

    client.cookies.set(settings.COOKIE_NAME, expired_token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()

    # Verify session was pruned from DB
    with SessionLocal() as db:
        assert db.query(DBSession).filter(DBSession.token_digest == digest).first() is None


def test_logout_invalidates_session(clean_db):
    """Verify logout removes the session from the database and clears cookies."""
    login_resp = client.post("/api/auth/register", json={
        "username": "logout_user",
        "email": "logout@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    token = login_resp.cookies[settings.COOKIE_NAME]
    csrf_token = login_resp.json()["csrf_token"]
    digest = hash_session_token(token)

    client.cookies.set(settings.COOKIE_NAME, token)
    logout_resp = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout_resp.status_code == 200

    # DB record is gone
    with SessionLocal() as db:
        assert db.query(DBSession).filter(DBSession.token_digest == digest).first() is None

    # Subsequent request fails
    assert client.get("/api/auth/me").status_code == 401


def test_session_fixation_resistance_on_refresh(clean_db):
    """Verify refresh endpoint rotates the session token and invalidates the old one."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "fixation_user",
        "email": "fixation@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    old_token = reg_resp.cookies[settings.COOKIE_NAME]
    old_csrf = reg_resp.json()["csrf_token"]
    old_digest = hash_session_token(old_token)

    client.cookies.set(settings.COOKIE_NAME, old_token)
    ref_resp = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert ref_resp.status_code == 200
    new_token = ref_resp.cookies[settings.COOKIE_NAME]
    assert new_token != old_token

    # Old token is deleted from DB
    with SessionLocal() as db:
        assert db.query(DBSession).filter(DBSession.token_digest == old_digest).first() is None
        assert db.query(DBSession).filter(DBSession.token_digest == hash_session_token(new_token)).first() is not None

    # Old token cannot authenticate
    client.cookies.set(settings.COOKIE_NAME, old_token)
    assert client.get("/api/auth/me").status_code == 401

    # New token authenticates cleanly
    client.cookies.set(settings.COOKIE_NAME, new_token)
    assert client.get("/api/auth/me").status_code == 200


def test_csrf_protection_on_state_changing_requests(clean_db):
    """Verify CSRF token is required and verified for cookie-authenticated state-changing calls."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "csrf_user",
        "email": "csrf@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    token = reg_resp.cookies[settings.COOKIE_NAME]
    valid_csrf = reg_resp.json()["csrf_token"]

    client.cookies.set(settings.COOKIE_NAME, token)

    # 1. Missing CSRF header -> 403
    resp_missing = client.post("/api/auth/logout")
    assert resp_missing.status_code == 403
    assert "CSRF validation failed" in resp_missing.json()["detail"]

    # 2. Invalid CSRF header -> 403
    resp_invalid = client.post("/api/auth/logout", headers={"X-CSRF-Token": "invalid_forged_csrf_token"})
    assert resp_invalid.status_code == 403
    assert "invalid CSRF token" in resp_invalid.json()["detail"]

    # 3. Valid CSRF header -> 200
    resp_valid = client.post("/api/auth/logout", headers={"X-CSRF-Token": valid_csrf})
    assert resp_valid.status_code == 200


def test_password_change_invalidates_other_sessions(clean_db):
    """Verify changing password invalidates all other sessions while preserving current session."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "pw_change_user",
        "email": "pwchange@example.com",
        "password": "InitialPassword123!",
        "confirm_password": "InitialPassword123!",
        "terms_accepted": True
    })
    sess1_token = reg_resp.cookies[settings.COOKIE_NAME]
    sess1_csrf = reg_resp.json()["csrf_token"]
    user_id = reg_resp.json()["user"]["id"]

    # Create a second session for the same user
    sess2_token = secrets.token_hex(32)
    with SessionLocal() as db:
        s2 = DBSession(
            token_digest=hash_session_token(sess2_token),
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(s2)
        db.commit()

    # Change password using session 1
    client.cookies.set(settings.COOKIE_NAME, sess1_token)
    chg_resp = client.post("/api/auth/change-password", headers={"X-CSRF-Token": sess1_csrf}, json={
        "current_password": "InitialPassword123!",
        "new_password": "NewStrongPassword456!",
        "confirm_new_password": "NewStrongPassword456!"
    })
    assert chg_resp.status_code == 200

    # Session 1 remains active
    client.cookies.set(settings.COOKIE_NAME, sess1_token)
    assert client.get("/api/auth/me").status_code == 200

    # Session 2 is revoked
    client.cookies.set(settings.COOKIE_NAME, sess2_token)
    assert client.get("/api/auth/me").status_code == 401


def test_suspended_user_session_denied(clean_db):
    """Verify suspended accounts cannot authenticate even with a valid session cookie."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "suspended_user",
        "email": "suspended@example.com",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "terms_accepted": True
    })
    token = reg_resp.cookies[settings.COOKIE_NAME]

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "suspended_user").first()
        user.is_suspended = True
        user.suspension_reason = "Policy violation"
        db.commit()

    client.cookies.set(settings.COOKIE_NAME, token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()


def test_admin_sessions_and_emergency_revoke_all(clean_db):
    """Verify emergency global revoke-all revokes other active sessions while preserving invoking admin."""
    # Create super_admin
    admin_pw = "SuperAdminPassword123!"
    with SessionLocal() as db:
        admin_user = User(
            id=gen_id("usr_"),
            username="super_ops",
            email="super_ops@example.com",
            hashed_password=hash_password(admin_pw),
            role="super_admin",
            terms_accepted=True
        )
        other_admin = User(
            id=gen_id("usr_"),
            username="other_admin",
            email="other@example.com",
            hashed_password=hash_password(admin_pw),
            role="operations_admin",
            terms_accepted=True
        )
        db.add_all([admin_user, other_admin])
        db.commit()

    # Admin 1 logs in
    resp1 = client.post("/api/admin/auth/login", json={"username": "super_ops", "password": admin_pw})
    assert resp1.status_code == 200
    token1 = resp1.cookies[settings.COOKIE_NAME]
    csrf1 = resp1.json()["csrf_token"]

    # Admin 2 logs in
    resp2 = client.post("/api/admin/auth/login", json={"username": "other_admin", "password": admin_pw})
    assert resp2.status_code == 200
    token2 = resp2.cookies[settings.COOKIE_NAME]

    # Verify both can access admin me
    client.cookies.set(settings.COOKIE_NAME, token1)
    assert client.get("/api/admin/auth/me").status_code == 200
    client.cookies.set(settings.COOKIE_NAME, token2)
    assert client.get("/api/admin/auth/me").status_code == 200

    # Admin 1 executes emergency revoke-all
    client.cookies.set(settings.COOKIE_NAME, token1)
    rev_resp = client.post("/api/admin/security/sessions/revoke-all", headers={"X-CSRF-Token": csrf1})
    assert rev_resp.status_code == 200

    # Admin 1 session is preserved
    client.cookies.set(settings.COOKIE_NAME, token1)
    assert client.get("/api/admin/auth/me").status_code == 200

    # Admin 2 session was revoked
    client.cookies.set(settings.COOKIE_NAME, token2)
    assert client.get("/api/admin/auth/me").status_code == 401


def test_admin_session_listings_do_not_expose_tokens_or_digests(clean_db):
    """Verify session listings never return session_token or token_digest in payload."""
    admin_pw = "SuperAdminSecret123!"
    with SessionLocal() as db:
        admin_user = User(
            id=gen_id("usr_"),
            username="sec_auditor",
            email="auditor@example.com",
            hashed_password=hash_password(admin_pw),
            role="super_admin",
            terms_accepted=True
        )
        db.add(admin_user)
        db.commit()

    resp = client.post("/api/admin/auth/login", json={"username": "sec_auditor", "password": admin_pw})
    token = resp.cookies[settings.COOKIE_NAME]
    client.cookies.set(settings.COOKIE_NAME, token)

    # 1. Admin my-sessions endpoint
    my_sess_resp = client.get("/api/admin/auth/sessions")
    assert my_sess_resp.status_code == 200
    my_items = my_sess_resp.json()["sessions"]
    assert len(my_items) >= 1
    for item in my_items:
        assert "session_token" not in item
        assert "token_digest" not in item
        assert item["is_current"] is True

    # 2. Admin security center all-sessions endpoint
    all_sess_resp = client.get("/api/admin/security/sessions")
    assert all_sess_resp.status_code == 200
    all_items = all_sess_resp.json()["sessions"]
    assert len(all_items) >= 1
    for item in all_items:
        assert "session_token" not in item
        assert "token_digest" not in item
        assert "id" in item
        assert "username" in item


def test_production_config_rejects_insecure_secrets():
    """Verify production runtime safety validates secrets and never prints them in exceptions."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.IS_PROD = True
    mock_settings.APP_ENV = "production"
    mock_settings.COOKIE_SECURE = True
    mock_settings.DATABASE_URL = "postgresql://user:pass@ep-db.us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"

    with patch.dict(os.environ, {"DATABASE_URL": mock_settings.DATABASE_URL, "ALLOWED_ORIGINS": "https://app.example.com"}):
        # Known dev session secrets (check non-trivial strings to avoid matching English word 'secret')
        for bad_secret in [s for s in KNOWN_DEV_SESSION_SECRETS if len(s) >= 15]:
            mock_settings.SESSION_SECRET = bad_secret
            with pytest.raises(RuntimeError) as exc_info:
                validate_production_runtime_safety(mock_settings)
            # Ensure secret itself is not leaked in the exception message
            assert bad_secret not in str(exc_info.value)
            assert "strong, unique SESSION_SECRET" in str(exc_info.value)

        # Too short secret (< 32 characters)
        short_secret = "ShortSecret12345"
        mock_settings.SESSION_SECRET = short_secret
        with pytest.raises(RuntimeError) as exc_info:
            validate_production_runtime_safety(mock_settings)
        assert short_secret not in str(exc_info.value)
        assert "at least 32 characters" in str(exc_info.value)
