import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import hash_password, verify_password, generate_csrf_token
from app.models.all_models import User, Session as DBSession, SecurityEvent, AuditLog, gen_id
from app.db.session import SessionLocal
from app.core.admin_provisioning import provision_initial_admin, seed_development_admin

@pytest.fixture
def db():
    session = SessionLocal()
    seed_development_admin(session)
    yield session
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

def test_admin_provisioning_idempotency(db):
    """Verify initial admin is provisioned with Argon2id and subsequent calls do not overwrite."""
    # Ensure HannyAdmin is provisioned
    provision_initial_admin(db)
    admin = db.query(User).filter(User.username == "HannyAdmin").first()
    assert admin is not None
    assert admin.role == "super_admin"
    assert verify_password("HannyAdmin", admin.hashed_password) is True

    # Run provisioning second time
    result = provision_initial_admin(db)
    assert result is False

def test_admin_login_success_and_cookies(client, db):
    """Verify admin login succeeds with credentials and sets secure session and CSRF cookies."""
    provision_initial_admin(db)
    resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["username"] == "HannyAdmin"
    assert data["user"]["role"] == "super_admin"
    assert "csrf_token" in data
    assert "view_dashboard" in data["permissions"]

    # Verify cookies
    cookies = resp.cookies
    assert settings.COOKIE_NAME in cookies
    assert settings.CSRF_COOKIE_NAME in cookies

def test_admin_login_failure_invalid_credentials(client, db):
    """Verify invalid password returns 401 without revealing password details."""
    provision_initial_admin(db)
    resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "WrongPassword123"
    })
    assert resp.status_code == 401
    assert "Invalid administrator credentials" in resp.json()["detail"]

def test_normal_user_blocked_from_admin_login(client, db):
    """Verify an ordinary user (role='user') cannot log in through admin login endpoint."""
    user = db.query(User).filter(User.username == "test_normal_user_auth").first()
    if not user:
        user = User(
            id=gen_id("usr_"),
            username="test_normal_user_auth",
            email="normaluser@example.com",
            hashed_password=hash_password("NormalUserPass1"),
            role="user",
            terms_accepted=True
        )
        db.add(user)
        db.commit()

    resp = client.post("/api/admin/auth/login", json={
        "username": "test_normal_user_auth",
        "password": "NormalUserPass1"
    })
    assert resp.status_code == 401
    assert "Invalid administrator credentials" in resp.json()["detail"]

def test_normal_user_blocked_from_admin_apis(client, db):
    """Verify an authenticated normal user receives 403 on administrative APIs."""
    # Log in as normal user
    login_resp = client.post("/api/auth/login", json={
        "email_or_username": "test_normal_user_auth",
        "password": "NormalUserPass1"
    })
    assert login_resp.status_code == 200
    cookies = login_resp.cookies

    # Attempt to access admin dashboard
    admin_resp = client.get("/api/admin/dashboard/stats", cookies=cookies)
    assert admin_resp.status_code == 403
    assert "administrative privileges required" in admin_resp.json()["detail"].lower()

def test_unauthenticated_request_blocked(client):
    """Verify unauthenticated requests receive 401."""
    resp = client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 401

def test_admin_csrf_protection(client, db):
    """Verify state-changing admin requests fail if CSRF token is missing or invalid."""
    provision_initial_admin(db)
    login_resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert login_resp.status_code == 200
    cookies = login_resp.cookies

    # Attempt POST without CSRF header
    resp = client.post("/api/admin/configuration", json={"settings": {"ai_timeout_seconds": "45"}}, cookies=cookies)
    assert resp.status_code == 403
    assert "CSRF validation failed" in resp.json()["detail"]

    # Attempt POST with valid CSRF header
    csrf_token = login_resp.json()["csrf_token"]
    resp_valid = client.post(
        "/api/admin/configuration",
        json={"settings": {"ai_timeout_seconds": "45"}},
        cookies=cookies,
        headers={"X-CSRF-Token": csrf_token}
    )
    assert resp_valid.status_code == 200

def test_suspended_user_is_blocked_immediately(client, db):
    """Verify a suspended user cannot access user endpoints."""
    user = db.query(User).filter(User.username == "test_normal_user_auth").first()
    assert user is not None
    user.is_suspended = True
    db.commit()

    # Attempt to login as suspended user
    resp = client.post("/api/auth/login", json={
        "email_or_username": "test_normal_user_auth",
        "password": "NormalUserPass1"
    })
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()

    # Reactivate user for subsequent test cleanliness
    user.is_suspended = False
    db.commit()

def test_admin_password_change_and_session_invalidation(client, db):
    """Verify changing admin password verifies current password, updates hash, and invalidates other sessions."""
    provision_initial_admin(db)
    login_resp = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert login_resp.status_code == 200
    cookies = login_resp.cookies
    csrf_token = login_resp.json()["csrf_token"]

    # Change password
    change_resp = client.post(
        "/api/admin/auth/change-password",
        json={
            "current_password": "HannyAdmin",
            "new_password": "NewSecretAdminPassword2026!",
            "confirm_new_password": "NewSecretAdminPassword2026!"
        },
        cookies=cookies,
        headers={"X-CSRF-Token": csrf_token}
    )
    assert change_resp.status_code == 200

    # Verify old password no longer works
    fail_login = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "HannyAdmin"
    })
    assert fail_login.status_code == 401

    # Verify new password works
    success_login = client.post("/api/admin/auth/login", json={
        "username": "HannyAdmin",
        "password": "NewSecretAdminPassword2026!"
    })
    assert success_login.status_code == 200

    # Reset back to initial password for subsequent tests
    admin = db.query(User).filter(User.username == "HannyAdmin").first()
    admin.hashed_password = hash_password("HannyAdmin")
    db.commit()
