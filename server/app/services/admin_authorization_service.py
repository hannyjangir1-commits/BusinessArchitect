"""Centralized administrative authorization, actor-versus-target policy, and super-admin integrity enforcement."""

from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.all_models import User
from app.api.deps import ADMIN_ROLES

# 64-bit signed integer key for PostgreSQL transaction-scoped advisory locking ('SUPERADM')
SUPER_ADMIN_INVARIANT_LOCK_KEY = 6004834884214473805

def acquire_super_admin_invariant_lock(db: Session) -> None:
    """Acquire transaction-scoped serialization before evaluating active super admin population invariants.

    On PostgreSQL, pg_advisory_xact_lock serializes all transactions that could reduce the
    active super admin population. The lock is held until the surrounding transaction commits
    or rolls back. On SQLite, database operations run serialized within their database connection.
    """
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": SUPER_ADMIN_INVARIANT_LOCK_KEY}
        )

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
    if not actor.role or actor.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Access denied: administrative privileges required."
        )

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
    if not actor.role or actor.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Access denied: administrative privileges required."
        )

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
    """Enforce the last-active-super-admin invariant:

    After any successful admin account mutation, at least one non-suspended super_admin must remain.
    If the mutation reduces the active super admin population (demotion, suspension, deletion, or combined),
    a database-backed lock is acquired and the authoritative active count is evaluated.
    """
    current_is_active_super = (target.role == "super_admin" and not target.is_suspended)

    if is_deletion:
        proposed_is_active_super = False
    else:
        final_role = proposed_role.strip() if proposed_role is not None else target.role
        final_suspended = proposed_suspended if proposed_suspended is not None else target.is_suspended
        proposed_is_active_super = (final_role == "super_admin" and not final_suspended)

    # Invariant is endangered only when removing an active super admin
    if current_is_active_super and not proposed_is_active_super:
        acquire_super_admin_invariant_lock(db)
        db.expire_all()

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
