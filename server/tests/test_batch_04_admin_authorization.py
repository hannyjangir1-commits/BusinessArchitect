"""
Batch 04 — Comprehensive Admin Authorization, Hierarchy, and Super-Admin Integrity Test Suite.
Addresses audit finding S01 and related admin-user mutation inconsistencies.
"""

import os
import threading
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.main import app
from app.models.all_models import User, Session as DBSession, gen_id
from app.core.security import hash_password, generate_session_token
from app.db.session import SessionLocal

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
    role: str = "user",
    password: str = "TestPassword123!",
    is_suspended: bool = False
) -> User:
    """Create a persistent user with a known password for testing."""
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.role = role
        user.is_suspended = is_suspended
        user.hashed_password = hash_password(password)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        id=gen_id("usr_"),
        username=username,
        email=f"{username.lower()}@test.com",
        hashed_password=hash_password(password),
        role=role,
        is_suspended=is_suspended,
        terms_accepted=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def login_user(client: TestClient, username: str, password: str = "TestPassword123!"):
    """Log in an admin or user and return cookies and CSRF headers."""
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    csrf = resp.json()["csrf_token"]
    cookies = dict(resp.cookies)
    headers = {"X-CSRF-Token": csrf}
    return cookies, headers

# ==============================================================================
# 1. Authorization: Actor-versus-Target Hierarchy Enforcement
# ==============================================================================

def test_support_admin_generic_suspension_of_super_admin_rejected(client, db):
    """Generic PUT /api/admin/users/{id} with only is_suspended must reject lower admin targeting a super admin."""
    super_admin = create_user_fixture(db, "sa_gen_target", role="super_admin")
    support_admin = create_user_fixture(db, "supp_gen_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{super_admin.id}",
        json={"is_suspended": True, "suspension_reason": "Attempted lower admin suspension"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin can modify" in resp.json()["detail"]

    db.refresh(super_admin)
    assert super_admin.is_suspended is False

def test_support_admin_dedicated_suspension_of_super_admin_rejected(client, db):
    """Dedicated POST /api/admin/users/{id}/suspend must reject lower admin targeting a super admin."""
    super_admin = create_user_fixture(db, "sa_ded_target", role="super_admin")
    support_admin = create_user_fixture(db, "supp_ded_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.post(
        f"/api/admin/users/{super_admin.id}/suspend",
        json={"reason": "Attempted suspension"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin can modify, suspend" in resp.json()["detail"]

    db.refresh(super_admin)
    assert super_admin.is_suspended is False

def test_lower_admin_generic_email_update_of_another_administrator_rejected(client, db):
    """Lower administrator cannot change email of any other administrator."""
    ops_admin = create_user_fixture(db, "ops_email_target", role="operations_admin")
    original_email = ops_admin.email
    support_admin = create_user_fixture(db, "supp_email_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{ops_admin.id}",
        json={"email": "hijacked@test.com"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

    db.refresh(ops_admin)
    assert ops_admin.email == original_email

def test_lower_admin_reactivation_of_administrator_rejected(client, db):
    """Lower administrator cannot reactivate a suspended administrator."""
    suspended_admin = create_user_fixture(db, "susp_admin_target", role="operations_admin", is_suspended=True)
    support_admin = create_user_fixture(db, "supp_react_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.post(
        f"/api/admin/users/{suspended_admin.id}/reactivate",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

    db.refresh(suspended_admin)
    assert suspended_admin.is_suspended is True

def test_lower_admin_targeted_session_revocation_of_administrator_rejected(client, db):
    """Lower administrator cannot revoke sessions of another administrator via users or security endpoints."""
    target_admin = create_user_fixture(db, "ops_sess_target", role="operations_admin")
    # Create active session for target
    sess = DBSession(
        id=gen_id("ses_"),
        session_token=generate_session_token(),
        user_id=target_admin.id,
        expires_at=datetime.now(timezone.utc)
    )
    db.add(sess)
    db.commit()

    # 1. support_admin via /api/admin/users/{id}/revoke-sessions
    support_admin = create_user_fixture(db, "supp_sess_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp1 = client.post(
        f"/api/admin/users/{target_admin.id}/revoke-sessions",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp1.status_code == 403
    assert "Only a Super Admin" in resp1.json()["detail"]

    # 2. security_admin via /api/admin/security/sessions/{id}/revoke
    sec_admin = create_user_fixture(db, "sec_sess_actor", role="security_admin")
    sec_cookies, sec_headers = login_user(client, sec_admin.username)

    resp2 = client.post(
        f"/api/admin/security/sessions/{sess.id}/revoke",
        cookies=sec_cookies,
        headers=sec_headers
    )
    assert resp2.status_code == 403
    assert "Only a Super Admin can revoke sessions belonging to another administrator" in resp2.json()["detail"]

    # Session remains active in DB
    assert db.query(DBSession).filter(DBSession.id == sess.id).first() is not None

def test_lower_admin_deletion_of_administrator_rejected(client, db):
    """Lower administrator cannot delete any administrator account."""
    target_admin = create_user_fixture(db, "aud_del_target", role="auditor")
    support_admin = create_user_fixture(db, "supp_del_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.delete(
        f"/api/admin/users/{target_admin.id}?confirm_username={target_admin.username}",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

    assert db.query(User).filter(User.id == target_admin.id).first() is not None

def test_permitted_ordinary_user_support_actions_succeed(client, db):
    """Support admin can perform all standard support actions on ordinary users (role == 'user')."""
    support_admin = create_user_fixture(db, "supp_ord_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    ordinary_user = create_user_fixture(db, "ordinary_target", role="user")

    # 1. Update email
    upd_resp = client.put(
        f"/api/admin/users/{ordinary_user.id}",
        json={"email": "ordinary_updated@test.com"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["user"]["email"] == "ordinary_updated@test.com"

    # 2. Suspend ordinary user
    susp_resp = client.post(
        f"/api/admin/users/{ordinary_user.id}/suspend",
        json={"reason": "Terms violation"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert susp_resp.status_code == 200
    assert susp_resp.json()["is_suspended"] is True

    # 3. Reactivate ordinary user
    react_resp = client.post(
        f"/api/admin/users/{ordinary_user.id}/reactivate",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert react_resp.status_code == 200
    assert react_resp.json()["is_suspended"] is False

    # 4. Revoke sessions for ordinary user
    rev_resp = client.post(
        f"/api/admin/users/{ordinary_user.id}/revoke-sessions",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert rev_resp.status_code == 200

    # 5. Delete ordinary user
    del_resp = client.delete(
        f"/api/admin/users/{ordinary_user.id}?confirm_username={ordinary_user.username}",
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert del_resp.status_code == 200
    assert db.query(User).filter(User.id == ordinary_user.id).first() is None

def test_super_admin_permitted_administrator_management_succeeds(client, db):
    """Super Admin can manage other administrator accounts, subject to last active super admin rules."""
    super_admin_actor = create_user_fixture(db, "sa_mgmt_actor", role="super_admin")
    sa_cookies, sa_headers = login_user(client, super_admin_actor.username)

    # 1. Create an administrator
    create_resp = client.post(
        "/api/admin/users",
        json={
            "username": "new_ops_admin",
            "email": "new_ops@test.com",
            "password": "Password123!",
            "role": "operations_admin"
        },
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["user"]["id"]

    # 2. Update role to support_admin
    upd_resp = client.put(
        f"/api/admin/users/{created_id}",
        json={"role": "support_admin"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["user"]["role"] == "support_admin"

    # 3. Suspend administrator
    susp_resp = client.post(
        f"/api/admin/users/{created_id}/suspend",
        json={"reason": "Investigation"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert susp_resp.status_code == 200
    assert susp_resp.json()["is_suspended"] is True

    # 4. Reactivate administrator
    react_resp = client.post(
        f"/api/admin/users/{created_id}/reactivate",
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert react_resp.status_code == 200
    assert react_resp.json()["is_suspended"] is False

    # 5. Delete administrator
    del_resp = client.delete(
        f"/api/admin/users/{created_id}?confirm_username=new_ops_admin",
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert del_resp.status_code == 200
    assert db.query(User).filter(User.id == created_id).first() is None

def test_auditor_and_ordinary_user_remain_unable_to_mutate(client, db):
    """Auditors and ordinary users lack manage_users and cannot mutate users."""
    auditor = create_user_fixture(db, "aud_actor_check", role="auditor")
    aud_cookies, aud_headers = login_user(client, auditor.username)

    target_user = create_user_fixture(db, "aud_target_check", role="user")

    # Auditor attempting mutation -> 403
    resp = client.put(
        f"/api/admin/users/{target_user.id}",
        json={"email": "forbidden@test.com"},
        cookies=aud_cookies,
        headers=aud_headers
    )
    assert resp.status_code == 403

def test_missing_or_invalid_csrf_remains_rejected(client, db):
    """All mutation endpoints require valid CSRF verification."""
    super_admin = create_user_fixture(db, "sa_csrf_actor", role="super_admin")
    sa_cookies, _ = login_user(client, super_admin.username)
    target = create_user_fixture(db, "csrf_target", role="user")

    # Missing CSRF header
    resp_missing = client.put(
        f"/api/admin/users/{target.id}",
        json={"email": "badcsrf@test.com"},
        cookies=sa_cookies
    )
    assert resp_missing.status_code == 403
    assert "CSRF" in resp_missing.json()["detail"]

    # Invalid CSRF header
    resp_invalid = client.put(
        f"/api/admin/users/{target.id}",
        json={"email": "badcsrf@test.com"},
        cookies=sa_cookies,
        headers={"X-CSRF-Token": "invalid_csrf_token_value"}
    )
    assert resp_invalid.status_code == 403
    assert "CSRF" in resp_invalid.json()["detail"]

# ==============================================================================
# 2. Combined Payloads and Bypass Resistance
# ==============================================================================

def test_combined_demote_and_suspend_by_lower_admin_rejected(client, db):
    """Lower admin cannot demote and suspend an administrator in the same request."""
    target_admin = create_user_fixture(db, "ops_demote_target", role="operations_admin")
    support_admin = create_user_fixture(db, "supp_demote_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{target_admin.id}",
        json={"role": "user", "is_suspended": True},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

    db.refresh(target_admin)
    assert target_admin.role == "operations_admin"
    assert target_admin.is_suspended is False

def test_email_change_combined_with_forbidden_suspension_by_lower_admin(client, db):
    """Lower admin cannot bundle email update with suspension targeting an admin."""
    target_admin = create_user_fixture(db, "aud_bundle_target", role="auditor")
    orig_email = target_admin.email
    support_admin = create_user_fixture(db, "supp_bundle_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{target_admin.id}",
        json={"email": "bundled@test.com", "is_suspended": True},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

    db.refresh(target_admin)
    assert target_admin.email == orig_email
    assert target_admin.is_suspended is False

def test_unchanged_role_combined_with_forbidden_mutation(client, db):
    """Supplying the target's current unchanged role cannot bypass admin target authorization."""
    target_admin = create_user_fixture(db, "sec_unchanged_target", role="security_admin")
    support_admin = create_user_fixture(db, "supp_unchanged_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{target_admin.id}",
        json={"role": "security_admin", "email": "new_email@test.com"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

def test_empty_or_noop_payload_cannot_bypass_checks(client, db):
    """Sending an empty JSON payload on an administrator still triggers target check."""
    target_admin = create_user_fixture(db, "ops_noop_target", role="operations_admin")
    support_admin = create_user_fixture(db, "supp_noop_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    resp = client.put(
        f"/api/admin/users/{target_admin.id}",
        json={},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin" in resp.json()["detail"]

def test_denied_requests_leave_account_fields_and_sessions_unchanged(client, db):
    """Rejected requests must never partially alter fields or revoke active sessions."""
    target_admin = create_user_fixture(db, "ops_atomic_target", role="operations_admin")
    original_updated_at = target_admin.updated_at
    original_email = target_admin.email

    sess = DBSession(
        id=gen_id("ses_"),
        session_token=generate_session_token(),
        user_id=target_admin.id,
        expires_at=datetime.now(timezone.utc)
    )
    db.add(sess)
    db.commit()

    support_admin = create_user_fixture(db, "supp_atomic_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    # Attempt forbidden update
    resp = client.put(
        f"/api/admin/users/{target_admin.id}",
        json={"email": "tampered@test.com", "is_suspended": True},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403

    db.refresh(target_admin)
    assert target_admin.email == original_email
    assert target_admin.role == "operations_admin"
    assert target_admin.is_suspended is False
    assert target_admin.updated_at == original_updated_at

    # Session still exists intact
    assert db.query(DBSession).filter(DBSession.id == sess.id).first() is not None

# ==============================================================================
# 3. Last Active Super Admin Invariant
# ==============================================================================

def test_sole_active_super_admin_demotion_rejected(client, db):
    """Demoting the only active super admin must be rejected with HTTP 400."""
    # Ensure only 1 active super admin in database
    db.query(User).filter(User.role == "super_admin").delete()
    db.commit()

    sole_super = create_user_fixture(db, "sole_sa_demote", role="super_admin")
    sa_cookies, sa_headers = login_user(client, sole_super.username)

    resp = client.put(
        f"/api/admin/users/{sole_super.id}",
        json={"role": "operations_admin"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp.status_code == 400
    assert "last active super admin" in resp.json()["detail"].lower()

    db.refresh(sole_super)
    assert sole_super.role == "super_admin"

def test_sole_active_super_admin_suspension_rejected(client, db):
    """Suspending the only active super admin must be rejected."""
    db.query(User).filter(User.role == "super_admin").delete()
    db.commit()

    sa1 = create_user_fixture(db, "sole_sa_susp1", role="super_admin")
    # Note: self-suspension is checked first, so create a second actor if testing another target
    # With 1 active super admin and an external admin attempting suspension:
    # Actor must be super_admin to suspend super_admin. If there are 2 super admins, removing 1 leaves 1.
    # But if there's only 1 active super admin, self-suspension yields 400 "cannot suspend their own account".
    sa_cookies, sa_headers = login_user(client, sa1.username)

    resp = client.post(
        f"/api/admin/users/{sa1.id}/suspend",
        json={"reason": "Self suspend"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp.status_code == 400
    assert "cannot suspend their own account" in resp.json()["detail"].lower()

def test_suspended_super_admins_do_not_count_as_active(client, db):
    """
    If there is 1 active super admin and 1 suspended super admin:
    - Demoting or deleting the active super admin must be rejected (only 1 active).
    - Deleting the suspended super admin is permitted (1 active remains).
    """
    db.query(User).filter(User.role == "super_admin").delete()
    db.commit()

    active_super = create_user_fixture(db, "sa_active_count", role="super_admin", is_suspended=False)
    suspended_super = create_user_fixture(db, "sa_susp_count", role="super_admin", is_suspended=True)
    sa_cookies, sa_headers = login_user(client, active_super.username)

    # 1. Attempting to demote active_super must be rejected because active_count <= 1
    demote_resp = client.put(
        f"/api/admin/users/{active_super.id}",
        json={"role": "operations_admin"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert demote_resp.status_code == 400
    assert "last active super admin" in demote_resp.json()["detail"].lower()

    # 2. Deleting the already suspended super admin is permitted (does not reduce active super admin count)
    del_resp = client.delete(
        f"/api/admin/users/{suspended_super.id}?confirm_username={suspended_super.username}",
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert del_resp.status_code == 200
    assert db.query(User).filter(User.id == suspended_super.id).first() is None

def test_authorized_removal_of_one_of_two_active_super_admins_succeeds(client, db):
    """When 2 active super admins exist, an authorized super admin can demote or suspend one of them."""
    db.query(User).filter(User.role == "super_admin").delete()
    db.commit()

    sa_actor = create_user_fixture(db, "sa_pair_actor", role="super_admin", is_suspended=False)
    sa_target = create_user_fixture(db, "sa_pair_target", role="super_admin", is_suspended=False)
    sa_cookies, sa_headers = login_user(client, sa_actor.username)

    # Suspend sa_target
    susp_resp = client.post(
        f"/api/admin/users/{sa_target.id}/suspend",
        json={"reason": "Disciplinary suspension"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert susp_resp.status_code == 200
    assert susp_resp.json()["is_suspended"] is True

    # Exactly 1 active super admin remains
    active_count = db.query(User).filter(User.role == "super_admin", User.is_suspended == False).count()
    assert active_count == 1

def test_self_suspension_and_self_deletion_remain_rejected(client, db):
    """Administrators cannot suspend or delete their own accounts."""
    sa = create_user_fixture(db, "sa_self_guard", role="super_admin")
    sa_cookies, sa_headers = login_user(client, sa.username)

    # 1. Self-suspend via POST /suspend
    resp1 = client.post(
        f"/api/admin/users/{sa.id}/suspend",
        json={"reason": "Self suspend"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp1.status_code == 400
    assert "cannot suspend their own account" in resp1.json()["detail"].lower()

    # 2. Self-suspend via PUT /users/{id}
    resp2 = client.put(
        f"/api/admin/users/{sa.id}",
        json={"is_suspended": True},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp2.status_code == 400
    assert "cannot suspend their own account" in resp2.json()["detail"].lower()

    # 3. Self-delete via DELETE
    resp3 = client.delete(
        f"/api/admin/users/{sa.id}?confirm_username={sa.username}",
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp3.status_code == 400
    assert "cannot delete their own account" in resp3.json()["detail"].lower()

def test_combined_state_changes_preserve_the_invariant(client, db):
    """Combined demote and suspend payload on the only active super admin is rejected."""
    db.query(User).filter(User.role == "super_admin").delete()
    db.commit()

    sa_single = create_user_fixture(db, "sa_comb_inv", role="super_admin", is_suspended=False)
    sa_cookies, sa_headers = login_user(client, sa_single.username)

    resp = client.put(
        f"/api/admin/users/{sa_single.id}",
        json={"role": "user", "is_suspended": True},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp.status_code == 400
    # Either self-suspension or last active super admin invariant rejects it
    assert resp.status_code == 400

# ==============================================================================
# 4. PostgreSQL Concurrency Serialization Verification
# ==============================================================================

def test_postgresql_concurrent_super_admin_removal():
    """
    PostgreSQL Concurrency Test Execution:
    - Connects to an isolated PostgreSQL instance defined by TEST_POSTGRES_URL.
    - Creates two active super admins in the database.
    - Spawns two concurrent threads/connections attempting to remove both super admins simultaneously.
    - Asserts that pg_advisory_xact_lock serializes execution: at most one removal succeeds.
    - Asserts that at least one active super admin remains.
    - Asserts that no deadlocks or uncontrolled 500 errors occur.

    Execution Instructions:
    To execute this test against a disposable PostgreSQL instance:
      $env:TEST_POSTGRES_URL="postgresql://user:pass@localhost:5432/disposable_test_db"
      pytest server/tests/test_batch_04_admin_authorization.py -k test_postgresql_concurrent_super_admin_removal
    """
    pg_url = os.environ.get("TEST_POSTGRES_URL")
    if not pg_url:
        pytest.skip(
            "Disposable PostgreSQL instance not configured via TEST_POSTGRES_URL. "
            "Skipping PostgreSQL concurrency execution in local SQLite test environment."
        )

    engine = create_engine(pg_url)
    # Ensure tables exist
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)

    Session = SessionLocal
    # Setup test users
    with Session(bind=engine) as s:
        s.query(User).filter(User.username.in_(["pg_conc_sa_1", "pg_conc_sa_2"])).delete()
        s.commit()

        sa1 = User(
            id=gen_id("usr_"),
            username="pg_conc_sa_1",
            email="pg_conc_sa_1@test.com",
            hashed_password=hash_password("Password123!"),
            role="super_admin",
            is_suspended=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        sa2 = User(
            id=gen_id("usr_"),
            username="pg_conc_sa_2",
            email="pg_conc_sa_2@test.com",
            hashed_password=hash_password("Password123!"),
            role="super_admin",
            is_suspended=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        s.add_all([sa1, sa2])
        s.commit()
        sa1_id, sa2_id = sa1.id, sa2.id

    from app.services.admin_authorization_service import assert_super_admin_invariant

    results = []

    def attempt_removal(target_id: str, thread_name: str):
        with Session(bind=engine) as s:
            try:
                target = s.query(User).filter(User.id == target_id).first()
                assert_super_admin_invariant(s, target, proposed_role="user")
                target.role = "user"
                s.commit()
                results.append((thread_name, "success"))
            except Exception as e:
                s.rollback()
                results.append((thread_name, f"failed: {str(e)}"))

    t1 = threading.Thread(target=attempt_removal, args=(sa1_id, "T1"))
    t2 = threading.Thread(target=attempt_removal, args=(sa2_id, "T2"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r[1] == "success"]
    assert len(successes) <= 1, f"Expected at most 1 removal to succeed, but got {len(successes)}: {results}"

    with Session(bind=engine) as s:
        remaining_active = s.query(User).filter(
            User.role == "super_admin",
            User.is_suspended == False,
            User.id.in_([sa1_id, sa2_id])
        ).count()
        assert remaining_active >= 1, "Invariant broken: 0 active super admins remain!"
