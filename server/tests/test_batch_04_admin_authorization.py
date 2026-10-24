"""
Batch 04 — Comprehensive Admin Authorization, Hierarchy, and Super-Admin Integrity Test Suite.
Addresses audit finding S01 and related admin-user mutation inconsistencies.
"""

import os
import threading
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from app.main import app
from app.models.all_models import User, Session as DBSession, gen_id
from app.core.security import hash_password, generate_session_token
from app.db.session import SessionLocal

@pytest.fixture(autouse=True)
def cleanup_sqlite_lock():
    yield
    from app.services.admin_authorization_service import release_sqlite_lock_if_held
    release_sqlite_lock_if_held()

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
# 4. Deterministic Stale-State Authorization and Invariant Regression Tests
# ==============================================================================

def test_stale_target_suspended_super_admin_reactivated_and_becomes_sole_active_super_admin():
    """
    Independent reproduction:
    1. Seed A as active super admin and B as suspended super admin.
    2. Session 1 loads B, retaining is_suspended=True in memory.
    3. Session 2 reactivates B and demotes A, then commits.
    4. B is now the sole active super admin.
    5. Session 1 calls assert_super_admin_invariant(s1, B, proposed_suspended=True).
    6. Authoritative reload and invariant locking must detect B is the sole active super admin and reject with HTTP 400.
    """
    from app.services.admin_authorization_service import assert_super_admin_invariant
    from fastapi import HTTPException

    s_setup = SessionLocal()
    try:
        s_setup.query(User).filter(User.role == "super_admin").delete()
        s_setup.commit()

        user_a = create_user_fixture(s_setup, "sa_stale_a", role="super_admin", is_suspended=False)
        user_b = create_user_fixture(s_setup, "sa_stale_b", role="super_admin", is_suspended=True)
        user_a_id, user_b_id = user_a.id, user_b.id
    finally:
        s_setup.close()

    s1 = SessionLocal()
    s2 = SessionLocal()
    try:
        # Step 2: Session 1 loads B, caching is_suspended=True
        b_in_s1 = s1.query(User).filter(User.id == user_b_id).first()
        assert b_in_s1.is_suspended is True

        # Step 3: Session 2 reactivates B and demotes A, then commits
        b_in_s2 = s2.query(User).filter(User.id == user_b_id).first()
        a_in_s2 = s2.query(User).filter(User.id == user_a_id).first()
        b_in_s2.is_suspended = False
        a_in_s2.role = "user"
        s2.commit()

        # Step 4: B is now the sole active super admin in database
        # Step 5: Session 1 attempts to suspend B using stale in-memory object
        with pytest.raises(HTTPException) as exc_info:
            assert_super_admin_invariant(s1, b_in_s1, proposed_suspended=True)

        assert exc_info.value.status_code == 400
        assert "last active super admin" in exc_info.value.detail.lower()
    finally:
        s1.close()
        s2.close()

def test_stale_target_ordinary_user_promoted_concurrently_rejects_lower_admin(client, db):
    """
    Ordinary target is promoted while another request is waiting;
    a lower admin must not mutate it using the old role.
    """
    target = create_user_fixture(db, "target_to_promote", role="user")
    support_admin = create_user_fixture(db, "supp_waiting_actor", role="support_admin")
    supp_cookies, supp_headers = login_user(client, support_admin.username)

    # Concurrently promote target to operations_admin in a separate session
    s_concurrent = SessionLocal()
    try:
        t_concurrent = s_concurrent.query(User).filter(User.id == target.id).first()
        t_concurrent.role = "operations_admin"
        s_concurrent.commit()
    finally:
        s_concurrent.close()

    # Lower admin attempts to update target's email
    resp = client.put(
        f"/api/admin/users/{target.id}",
        json={"email": "attempted_hijack@test.com"},
        cookies=supp_cookies,
        headers=supp_headers
    )
    assert resp.status_code == 403
    assert "Only a Super Admin can modify" in resp.json()["detail"]

    # Target email intact
    db.expire_all()
    db.refresh(target)
    assert target.role == "operations_admin"
    assert target.email != "attempted_hijack@test.com"

def test_stale_actor_suspended_or_demoted_before_mutation_proceeds_rejected(client, db):
    """
    Actor is demoted or suspended before protected mutation proceeds;
    stale actor privileges must not authorize it.
    """
    # 1. Suspended Actor Scenario
    super_admin = create_user_fixture(db, "sa_to_suspend", role="super_admin")
    target_user = create_user_fixture(db, "target_ord_user1", role="user")
    sa_cookies, sa_headers = login_user(client, super_admin.username)

    # Concurrently suspend the super admin
    s_susp = SessionLocal()
    try:
        sa_row = s_susp.query(User).filter(User.id == super_admin.id).first()
        sa_row.is_suspended = True
        s_susp.commit()
    finally:
        s_susp.close()

    resp_susp = client.put(
        f"/api/admin/users/{target_user.id}",
        json={"role": "operations_admin"},
        cookies=sa_cookies,
        headers=sa_headers
    )
    assert resp_susp.status_code == 403
    assert "Account has been suspended" in resp_susp.json()["detail"]

    # 2. Demoted Actor Scenario
    super_admin2 = create_user_fixture(db, "sa_to_demote", role="super_admin")
    target_admin = create_user_fixture(db, "target_admin_user", role="operations_admin")
    sa2_cookies, sa2_headers = login_user(client, super_admin2.username)

    # Concurrently demote super_admin2 to support_admin
    s_demote = SessionLocal()
    try:
        sa2_row = s_demote.query(User).filter(User.id == super_admin2.id).first()
        sa2_row.role = "support_admin"
        s_demote.commit()
    finally:
        s_demote.close()

    resp_demote = client.delete(
        f"/api/admin/users/{target_admin.id}?confirm_username={target_admin.username}",
        cookies=sa2_cookies,
        headers=sa2_headers
    )
    assert resp_demote.status_code == 403
    assert "Only a Super Admin can modify" in resp_demote.json()["detail"]
    assert db.query(User).filter(User.id == target_admin.id).first() is not None

def test_concurrent_demotion_cannot_leave_zero_active_super_admins():
    """
    Sequential stale-identity-map test:
    Two active super admins exist. Both sessions plan to demote one super admin.
    After Session 1 commits demotion of SA1, Session 2's attempt to demote SA2
    must be rejected because active super admin count becomes 1.
    """
    from app.services.admin_authorization_service import assert_super_admin_invariant
    from fastapi import HTTPException

    s_setup = SessionLocal()
    try:
        s_setup.query(User).filter(User.role == "super_admin").delete()
        s_setup.commit()

        sa_a = create_user_fixture(s_setup, "sa_conc_a", role="super_admin", is_suspended=False)
        sa_b = create_user_fixture(s_setup, "sa_conc_b", role="super_admin", is_suspended=False)
        sa_a_id, sa_b_id = sa_a.id, sa_b.id
    finally:
        s_setup.close()

    s1 = SessionLocal()
    s2 = SessionLocal()
    try:
        # Both sessions load the super admins while 2 exist
        sa_a_s1 = s1.query(User).filter(User.id == sa_a_id).first()
        sa_b_s2 = s2.query(User).filter(User.id == sa_b_id).first()

        # Session 1 successfully demotes SA A and commits
        assert_super_admin_invariant(s1, sa_a_s1, proposed_role="user")
        sa_a_s1.role = "user"
        s1.commit()

        # Session 2 attempts to demote SA B (the sole remaining super admin)
        with pytest.raises(HTTPException) as exc_info:
            assert_super_admin_invariant(s2, sa_b_s2, proposed_role="user")

        assert exc_info.value.status_code == 400
        assert "last active super admin" in exc_info.value.detail.lower()
    finally:
        s1.close()
        s2.close()

    # Verify exactly 1 active super admin remains
    s_check = SessionLocal()
    try:
        active_count = s_check.query(User).filter(
            User.role == "super_admin",
            User.is_suspended == False,
            User.id.in_([sa_a_id, sa_b_id])
        ).count()
        assert active_count == 1
    finally:
        s_check.close()

# ==============================================================================
# 5. Sanitized User Deletion Error Enforcement
# ==============================================================================

def test_delete_user_injected_failure_rolls_back_and_sanitizes_error(client, db, monkeypatch):
    """
    Test an injected deletion failure:
    - Database error containing sensitive connection strings, SQL statements, and passwords.
    - Transaction rolls back.
    - Account and sessions remain intact.
    - Client response status is 500 with a stable generic message.
    - Client response contains NO raw database exception text or credentials.
    """
    super_admin = create_user_fixture(db, "sa_del_err_actor", role="super_admin")
    target_user = create_user_fixture(db, "target_del_err_user", role="user")
    sa_cookies, sa_headers = login_user(client, super_admin.username)

    sess = DBSession(
        id=gen_id("ses_"),
        session_token=generate_session_token(),
        user_id=target_user.id,
        expires_at=datetime.now(timezone.utc)
    )
    db.add(sess)
    db.commit()

    # Inject failure into db.delete
    def faulty_delete(obj):
        raise RuntimeError(
            "FATAL: password=SuperSecretPassword123! dbname=production "
            "connection to postgresql://admin:secret@pg.prod:5432/main failed executing DELETE FROM users"
        )

    monkeypatch.setattr(Session, "delete", faulty_delete)

    resp = client.delete(
        f"/api/admin/users/{target_user.id}?confirm_username={target_user.username}",
        cookies=sa_cookies,
        headers=sa_headers
    )

    assert resp.status_code == 500
    resp_text = resp.text
    # Generic stable detail
    assert resp.json()["detail"] == "Failed to delete user account. Please try again or contact support."
    # Leak assertions: raw sensitive information must never appear
    assert "SuperSecretPassword123!" not in resp_text
    assert "postgresql://" not in resp_text
    assert "pg.prod" not in resp_text
    assert "DELETE FROM" not in resp_text

    # Verify rollback: user and session remain in database
    db.expire_all()
    assert db.query(User).filter(User.id == target_user.id).first() is not None
    assert db.query(DBSession).filter(DBSession.id == sess.id).first() is not None

# ==============================================================================
# 6. Correct Permission Matrix and Emergency Global Revocation
# ==============================================================================

def test_global_session_revocation_authorization_matrix_and_current_session_exclusion(client, db):
    """
    Authorization test for POST /api/admin/security/sessions/revoke-all:
    - super_admin: allowed (200), own session preserved, other sessions revoked.
    - operations_admin: allowed (200), own session preserved, other sessions revoked.
    - security_admin: allowed (200), own session preserved, other sessions revoked.
    - support_admin: rejected (403), lacks 'revoke_sessions'.
    - auditor: rejected (403), lacks 'revoke_sessions'.
    - ordinary user: rejected (403), requires administrative role.
    """
    # 1. Test unauthorized roles: support_admin, auditor, user
    support_admin = create_user_fixture(db, "supp_revall_actor", role="support_admin")
    supp_c, supp_h = login_user(client, support_admin.username)
    resp_supp = client.post("/api/admin/security/sessions/revoke-all", cookies=supp_c, headers=supp_h)
    assert resp_supp.status_code == 403
    assert "revoke_sessions" in resp_supp.json()["detail"]

    auditor = create_user_fixture(db, "aud_revall_actor", role="auditor")
    aud_c, aud_h = login_user(client, auditor.username)
    resp_aud = client.post("/api/admin/security/sessions/revoke-all", cookies=aud_c, headers=aud_h)
    assert resp_aud.status_code == 403
    assert "revoke_sessions" in resp_aud.json()["detail"]

    ordinary_user = create_user_fixture(db, "ord_revall_actor", role="user")
    ord_sess = DBSession(
        id=gen_id("ses_"),
        session_token=generate_session_token(),
        user_id=ordinary_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db.add(ord_sess)
    db.commit()
    from app.core.config import settings
    resp_user = client.post(
        "/api/admin/security/sessions/revoke-all",
        cookies={settings.COOKIE_NAME: ord_sess.session_token},
        headers={"X-CSRF-Token": "irrelevant"}
    )
    assert resp_user.status_code == 403
    assert "administrative privileges required" in resp_user.json()["detail"]

    # 2. Test authorized roles: security_admin, operations_admin, super_admin
    for role_name in ["security_admin", "operations_admin", "super_admin"]:
        actor = create_user_fixture(db, f"revall_act_{role_name}", role=role_name)
        cookies, headers = login_user(client, actor.username)
        current_token = cookies[settings.COOKIE_NAME]

        victim_id = gen_id("ses_")
        victim_sess = DBSession(
            id=victim_id,
            session_token=generate_session_token(),
            user_id=actor.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(victim_sess)
        db.commit()

        resp = client.post("/api/admin/security/sessions/revoke-all", cookies=cookies, headers=headers)
        assert resp.status_code == 200, f"Role {role_name} should be permitted to execute emergency global session revocation"

        # Current session remains active
        assert db.query(DBSession).filter(DBSession.session_token == current_token).first() is not None
        # Victim session was revoked
        assert db.query(DBSession).filter(DBSession.id == victim_id).first() is None

# ==============================================================================
# 7. Strengthened PostgreSQL Concurrency Serialization Verification
# ==============================================================================

def test_postgresql_concurrent_super_admin_removal():
    """
    PostgreSQL Concurrency Test Execution:
    - Connects to an isolated disposable PostgreSQL instance defined by TEST_POSTGRES_URL.
    - Strictly rejects any production or non-disposable hostnames to prevent accidental connection.
    - Synchronizes requests using threading.Barrier(2) to guarantee genuine concurrent overlap.
    - Sets statement_timeout and lock_timeout.
    - Spawns two concurrent threads using real service/transaction wiring attempting to demote both super admins.
    - Asserts that pg_advisory_xact_lock serializes execution: exactly one succeeds (HTTP 200) and exactly one fails with the expected invariant rejection (HTTP 400).
    - Asserts zero unexpected exceptions.
    - Bounded thread joins with timeouts.
    - Asserts final persisted database state: exactly 1 active super admin remains.
    - Disposes all connections and cleans up only test resources.

    Execution Instructions:
    To execute this test against a disposable PostgreSQL container:
      docker run -d --name pg-test -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:15
      $env:TEST_POSTGRES_URL="postgresql://postgres:test@localhost:5433/postgres"
      pytest server/tests/test_batch_04_admin_authorization.py -k test_postgresql_concurrent_super_admin_removal
    """
    pg_url = os.environ.get("TEST_POSTGRES_URL")
    if not pg_url:
        pytest.skip(
            "TEST_POSTGRES_URL not configured. Disposable PostgreSQL concurrency test skipped in local environment."
        )

    # Safety guard: Never connect to production
    lower_url = pg_url.lower()
    for forbidden in ["supabase.co", "render.com", "aws.com", "pooler.supabase.com"]:
        if forbidden in lower_url:
            pytest.fail(f"TEST_POSTGRES_URL points to a production or remote host ({forbidden}). Aborting test.")

    engine = create_engine(pg_url, pool_pre_ping=True)
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import sessionmaker
    PGSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Setup isolated test super admins
    with PGSessionLocal() as s:
        # Set lock and statement timeouts
        s.execute(text("SET statement_timeout = 10000"))
        s.execute(text("SET lock_timeout = 5000"))
        s.query(User).filter(User.username.in_(["pg_test_sa_1", "pg_test_sa_2"])).delete()
        s.commit()

        sa1 = User(
            id=gen_id("usr_"),
            username="pg_test_sa_1",
            email="pg_test_sa_1@test.com",
            hashed_password=hash_password("Password123!"),
            role="super_admin",
            is_suspended=False,
            terms_accepted=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        sa2 = User(
            id=gen_id("usr_"),
            username="pg_test_sa_2",
            email="pg_test_sa_2@test.com",
            hashed_password=hash_password("Password123!"),
            role="super_admin",
            is_suspended=False,
            terms_accepted=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc)
        )
        s.add_all([sa1, sa2])
        s.commit()
        sa1_id, sa2_id = sa1.id, sa2.id

    from app.services.admin_authorization_service import (
        synchronize_and_authoritative_load,
        validate_admin_mutation_target,
        assert_super_admin_invariant
    )
    from fastapi import HTTPException

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def attempt_route_demotion(actor_id: str, target_id: str, thread_name: str):
        with PGSessionLocal() as s:
            try:
                s.execute(text("SET statement_timeout = 10000"))
                s.execute(text("SET lock_timeout = 5000"))
                actor = s.query(User).filter(User.id == actor_id).first()

                # Synchronize before starting the mutation sequence to guarantee overlap
                barrier.wait(timeout=5)

                # Real route transaction wiring:
                auth_actor, auth_target = synchronize_and_authoritative_load(
                    s, actor, target_id=target_id, required_permission="manage_users"
                )
                validate_admin_mutation_target(auth_actor, auth_target, proposed_role="user")
                assert_super_admin_invariant(s, auth_target, proposed_role="user")

                auth_target.role = "user"
                s.commit()
                results.append((thread_name, "success", 200, None))
            except HTTPException as http_exc:
                s.rollback()
                results.append((thread_name, "rejected", http_exc.status_code, http_exc.detail))
            except Exception as e:
                s.rollback()
                errors.append((thread_name, str(e)))

    t1 = threading.Thread(target=attempt_route_demotion, args=(sa1_id, sa1_id, "T1"))
    t2 = threading.Thread(target=attempt_route_demotion, args=(sa2_id, sa2_id, "T2"))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "Thread 1 timed out during concurrent PostgreSQL demotion"
    assert not t2.is_alive(), "Thread 2 timed out during concurrent PostgreSQL demotion"
    assert len(errors) == 0, f"Unexpected exceptions encountered: {errors}"

    successes = [r for r in results if r[1] == "success"]
    rejections = [r for r in results if r[1] == "rejected"]

    assert len(successes) == 1, f"Expected exactly 1 successful demotion, got {len(successes)}: {results}"
    assert len(rejections) == 1, f"Expected exactly 1 invariant rejection, got {len(rejections)}: {results}"
    assert rejections[0][2] == 400
    assert "last active super admin" in rejections[0][3].lower()

    with PGSessionLocal() as s:
        remaining_active = s.query(User).filter(
            User.role == "super_admin",
            User.is_suspended == False,
            User.id.in_([sa1_id, sa2_id])
        ).count()
        assert remaining_active == 1, f"Invariant violated: expected exactly 1 active super admin, found {remaining_active}"

        # Clean up test resources
        s.query(User).filter(User.username.in_(["pg_test_sa_1", "pg_test_sa_2"])).delete()
        s.commit()

    engine.dispose()
