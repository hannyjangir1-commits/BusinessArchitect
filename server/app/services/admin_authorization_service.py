"""Centralized administrative authorization, actor-versus-target policy, and super-admin integrity enforcement."""

import logging
import threading
from typing import Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.all_models import User
from app.api.deps import ADMIN_ROLES, _get_permissions_for_role

logger = logging.getLogger(__name__)

# 64-bit signed integer key for PostgreSQL transaction-scoped advisory locking ('SUPERADM')
SUPER_ADMIN_INVARIANT_LOCK_KEY = 6004834884214473805

# In-process lock to serialize multi-threaded operations in SQLite test environments
_sqlite_concurrency_lock = threading.RLock()
_local_lock_state = threading.local()


def acquire_super_admin_invariant_lock(db: Session) -> None:
    """Acquire transaction-scoped serialization before evaluating admin mutation invariants.

    On PostgreSQL, pg_advisory_xact_lock serializes transactions that mutate administrator
    accounts or could reduce the active super admin population. The lock is held through the
    surrounding transaction until commit or rollback.
    On SQLite, an in-process reentrant lock serializes thread execution with depth tracking.
    """
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": SUPER_ADMIN_INVARIANT_LOCK_KEY}
        )
    elif bind and bind.dialect.name == "sqlite":
        _sqlite_concurrency_lock.acquire()
        depth = getattr(_local_lock_state, "depth", 0)
        _local_lock_state.depth = depth + 1


def release_sqlite_lock_if_held() -> None:
    """Safely release the SQLite in-process lock if acquired."""
    depth = getattr(_local_lock_state, "depth", 0)
    while depth > 0:
        try:
            _sqlite_concurrency_lock.release()
        except RuntimeError:
            pass
        depth -= 1
    _local_lock_state.depth = 0


def synchronize_and_authoritative_load(
    db: Session,
    actor: User,
    target_id: Optional[str] = None,
    required_permission: Optional[str] = "manage_users"
) -> Tuple[User, Optional[User]]:
    """Acquire the invariant synchronization lock and authoritatively refresh actor and target from DB.

    Guarantees that:
    1. The transaction-level serialization lock is acquired before inspecting actor or target state.
    2. Actor freshness is verified: an actor demoted or suspended while waiting for the lock is rejected.
    3. Target freshness is verified: stale in-memory role/suspension state cannot bypass hierarchy checks.
    4. Target is reloaded with populate_existing() to discard any stale session cache.
    """
    acquire_super_admin_invariant_lock(db)
    try:
        db.expire_all()

        # 1. Authoritative check on Actor
        authoritative_actor = db.query(User).filter(User.id == actor.id).populate_existing().first()
        if not authoritative_actor:
            raise HTTPException(status_code=401, detail="Authentication required")

        if authoritative_actor.is_suspended:
            raise HTTPException(
                status_code=403,
                detail="Account has been suspended. Please contact administrative support."
            )

        if not authoritative_actor.role or authoritative_actor.role not in ADMIN_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Access denied: administrative privileges required."
            )

        if required_permission:
            actor_perms = _get_permissions_for_role(authoritative_actor.role)
            if required_permission not in actor_perms:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: role '{authoritative_actor.role}' lacks '{required_permission}' permission."
                )

        # 2. Authoritative check on Target if provided
        authoritative_target = None
        if target_id is not None:
            authoritative_target = db.query(User).filter(User.id == target_id).populate_existing().first()
            if not authoritative_target:
                raise HTTPException(status_code=404, detail="User not found")

        return authoritative_actor, authoritative_target
    except Exception:
        release_sqlite_lock_if_held()
        raise


def validate_admin_mutation_target(
    actor: User,
    target: User,
    proposed_role: Optional[str] = None
) -> None:
    """Enforce central actor-versus-target authorization policy:

    - Ordinary users cannot use admin-user mutation routes.
    - Only a super admin may create, promote, demote, suspend, reactivate,
      delete, change email of, or revoke sessions belonging to an administrator account.
    - Lower administrators with manage_users can only manage ordinary users (role == 'user').
    - Supplying an unchanged role must not grant permission.
    - Omitting the role must not bypass permission.
    - Combined payloads are evaluated against the target's original role AND proposed state.
    - A lower admin cannot demote an admin and treat the target as ordinary user in the same request.
    """
    # 1. Target is currently an administrator: only a super_admin may modify/suspend/reactivate/delete
    if target.role in ADMIN_ROLES:
        if actor.role != "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Only a Super Admin can modify, suspend, reactivate, delete, or manage sessions for an administrator account."
            )

    # 2. Target is an ordinary user, but proposed role is an administrator role (promotion)
    target_role = proposed_role.strip() if proposed_role is not None else target.role
    if target_role in ADMIN_ROLES and target.role not in ADMIN_ROLES:
        if actor.role != "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Only a Super Admin can grant administrator privileges."
            )


def validate_session_revocation_target(actor: User, target_user: User) -> None:
    """Ensure targeted session revocation respects admin hierarchy while allowing self-service."""
    if target_user.role in ADMIN_ROLES:
        if target_user.id != actor.id and actor.role != "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Only a Super Admin can revoke sessions belonging to another administrator."
            )


def assert_super_admin_invariant(
    db: Session,
    target: User,
    proposed_role: Optional[str] = None,
    proposed_suspended: Optional[bool] = None,
    is_deletion: bool = False
) -> None:
    """Enforce the last-active-super-admin invariant using fresh authoritative target state.

    After any successful admin account mutation, at least one non-suspended super_admin must remain.
    Because the invariant synchronization lock is acquired and the target state refreshed before
    inspecting the role or suspension state, stale identity-map data cannot skip invariant checking.
    """
    acquire_super_admin_invariant_lock(db)
    try:
        db.expire_all()
        db.refresh(target)

        current_is_active_super = (target.role == "super_admin" and not target.is_suspended)

        if is_deletion:
            proposed_is_active_super = False
        else:
            final_role = proposed_role.strip() if proposed_role is not None else target.role
            final_suspended = proposed_suspended if proposed_suspended is not None else target.is_suspended
            proposed_is_active_super = (final_role == "super_admin" and not final_suspended)

        # Invariant is endangered only when removing an active super admin
        if current_is_active_super and not proposed_is_active_super:
            active_count = db.query(User).filter(
                User.role == "super_admin",
                User.is_suspended == False
            ).count()

            if active_count <= 1:
                if is_deletion:
                    detail = "Cannot delete the last active Super Admin account"
                elif proposed_suspended is True and (proposed_role is None or proposed_role == target.role):
                    detail = "Cannot suspend the last active Super Admin account"
                else:
                    detail = "Cannot alter the role of the last active Super Admin account"
                raise HTTPException(status_code=400, detail=detail)
    except Exception:
        release_sqlite_lock_if_held()
        raise
