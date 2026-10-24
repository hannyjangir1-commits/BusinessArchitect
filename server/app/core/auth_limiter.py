"""Shared authentication abuse protection and rate limiting service.

Provides IP-scoped and account-scoped throttling for public login, administrative login,
and public registration admission before expensive Argon2 password hashing.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import struct
import threading
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.models.all_models import AuthRateLimitEvent, gen_id
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Bounded striped locks for in-process concurrency control.
# Strictly bounded memory: 256 locks allocated once at module import.
# Eliminates memory amplification from arbitrary keys while serializing concurrent attempts
# to the same rate limit bucket.
_BUCKET_LOCK_STRIPES = 256
_STRIPED_LOCKS = [threading.Lock() for _ in range(_BUCKET_LOCK_STRIPES)]


def _get_bucket_lock(k_hash: str) -> threading.Lock:
    """Return a deterministic striped lock for the given bucket hash."""
    idx = int(k_hash[:8], 16) % _BUCKET_LOCK_STRIPES
    return _STRIPED_LOCKS[idx]


# Scopes
SCOPE_LOGIN_IP = "login_ip"
SCOPE_LOGIN_ACCOUNT = "login_account"
SCOPE_ADMIN_LOGIN_IP = "admin_login_ip"
SCOPE_ADMIN_LOGIN_ACCOUNT = "admin_login_account"
SCOPE_REGISTER_IP = "register_ip"

# Generic user-facing messages that never reveal account existence
MSG_LOGIN_RATE_LIMITED = "Too many failed login attempts. Please try again later."
MSG_ADMIN_LOGIN_RATE_LIMITED = "Too many failed login attempts. Please try again later."
MSG_REGISTER_RATE_LIMITED = "Too many registration attempts from this network. Please try again later."


def normalize_account_identifier(raw: Optional[str]) -> str:
    """
    Normalize account identifier (username or email) matching login semantics.
    Enforces lowercasing and bounds input length to prevent memory amplification.
    """
    if not raw or not isinstance(raw, str):
        return "unknown_account"
    cleaned = raw.strip().lower()
    if not cleaned:
        return "unknown_account"
    return cleaned[:256]


def hash_key(scope: str, raw_key: str) -> str:
    """Generate fixed-length 64-character SHA-256 hash to prevent raw credential storage."""
    clean_key = raw_key.strip() if raw_key else "empty"
    return hashlib.sha256(f"{scope}:{clean_key}".encode("utf-8")).hexdigest()


def check_rate_limit(
    db: Session,
    scope: str,
    raw_key: str,
    max_attempts: int,
    window_seconds: int,
    detail: str,
    now: Optional[datetime] = None
) -> None:
    """
    Check if the specified scope and key have exceeded maximum allowed attempts.
    Raises HTTPException(429) with a deterministic Retry-After header if limit is reached.
    """
    if not getattr(settings, "AUTH_RATE_LIMITING_ENABLED", True):
        return

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    k_hash = hash_key(scope, raw_key)

    # On PostgreSQL, acquire bucket-level advisory lock to serialize concurrent attempts
    # on the exact same bucket without serializing unrelated keys.
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        lock_id = struct.unpack(">q", hashlib.sha256(k_hash.encode()).digest()[:8])[0]
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})

    cutoff = current_time - timedelta(seconds=window_seconds)

    records = db.query(AuthRateLimitEvent.created_at).filter(
        AuthRateLimitEvent.scope == scope,
        AuthRateLimitEvent.key_hash == k_hash,
        AuthRateLimitEvent.created_at >= cutoff
    ).order_by(AuthRateLimitEvent.created_at.asc()).all()

    if len(records) >= max_attempts:
        oldest = records[0][0]
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        elapsed = (current_time - oldest).total_seconds()
        retry_after = max(1, int(window_seconds - elapsed))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)}
        )


def record_attempt(
    scope: str,
    raw_key: str,
    now: Optional[datetime] = None
) -> None:
    """
    Persist an attempt in an isolated, dedicated database transaction.
    This guarantees that rate limit records are committed immediately and
    never commit, interfere with, or get rolled back by the caller's session.
    """
    if not getattr(settings, "AUTH_RATE_LIMITING_ENABLED", True):
        return

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    k_hash = hash_key(scope, raw_key)

    with SessionLocal() as lim_db:
        try:
            evt = AuthRateLimitEvent(
                id=gen_id("lim_"),
                scope=scope,
                key_hash=k_hash,
                created_at=current_time
            )
            lim_db.add(evt)
            lim_db.commit()
        except Exception as exc:
            lim_db.rollback()
            logger.error("Failed to record auth rate limit attempt: %s", type(exc).__name__)


def clear_attempts(scope: str, raw_key: str) -> None:
    """Clear failed attempts for a key in an isolated transaction upon successful authentication."""
    k_hash = hash_key(scope, raw_key)
    with SessionLocal() as lim_db:
        try:
            lim_db.query(AuthRateLimitEvent).filter(
                AuthRateLimitEvent.scope == scope,
                AuthRateLimitEvent.key_hash == k_hash
            ).delete()
            lim_db.commit()
        except Exception:
            lim_db.rollback()


def check_login_rate_limits(
    db: Session,
    client_ip: str,
    account_identifier: str,
    is_admin: bool = False,
    now: Optional[datetime] = None
) -> None:
    """
    Enforce dual-scope login rate limits (client IP and account identifier).
    Checks IP limit first, then checks account limit to prevent IP rotation attacks.
    """
    ip_scope = SCOPE_ADMIN_LOGIN_IP if is_admin else SCOPE_LOGIN_IP
    account_scope = SCOPE_ADMIN_LOGIN_ACCOUNT if is_admin else SCOPE_LOGIN_ACCOUNT

    ip_max = settings.ADMIN_LOGIN_IP_MAX_ATTEMPTS if is_admin else settings.AUTH_LOGIN_IP_MAX_ATTEMPTS
    ip_window = settings.ADMIN_LOGIN_IP_WINDOW_SECONDS if is_admin else settings.AUTH_LOGIN_IP_WINDOW_SECONDS

    acc_max = settings.ADMIN_LOGIN_ACCOUNT_MAX_ATTEMPTS if is_admin else settings.AUTH_LOGIN_ACCOUNT_MAX_ATTEMPTS
    acc_window = settings.ADMIN_LOGIN_ACCOUNT_WINDOW_SECONDS if is_admin else settings.AUTH_LOGIN_ACCOUNT_WINDOW_SECONDS

    detail = MSG_ADMIN_LOGIN_RATE_LIMITED if is_admin else MSG_LOGIN_RATE_LIMITED

    # 1. IP-scoped check
    check_rate_limit(db, ip_scope, client_ip, ip_max, ip_window, detail, now=now)

    # 2. Account-scoped check
    norm_acc = normalize_account_identifier(account_identifier)
    check_rate_limit(db, account_scope, norm_acc, acc_max, acc_window, detail, now=now)


def record_login_failure(
    client_ip: str,
    account_identifier: str,
    is_admin: bool = False,
    now: Optional[datetime] = None
) -> None:
    """Record a failed login attempt across both IP and Account buckets."""
    ip_scope = SCOPE_ADMIN_LOGIN_IP if is_admin else SCOPE_LOGIN_IP
    account_scope = SCOPE_ADMIN_LOGIN_ACCOUNT if is_admin else SCOPE_LOGIN_ACCOUNT

    record_attempt(ip_scope, client_ip, now=now)
    record_attempt(account_scope, normalize_account_identifier(account_identifier), now=now)


def record_login_success(
    client_ip: str,
    account_identifier: str,
    is_admin: bool = False
) -> None:
    """Reset failed login records for the successfully authenticated account."""
    account_scope = SCOPE_ADMIN_LOGIN_ACCOUNT if is_admin else SCOPE_LOGIN_ACCOUNT
    clear_attempts(account_scope, normalize_account_identifier(account_identifier))


def check_and_record_registration_admission(
    db: Session,
    client_ip: str,
    now: Optional[datetime] = None
) -> None:
    """
    Admission check for public registration before expensive password hashing (Argon2id).
    Validates that client IP has not exceeded the registration attempt threshold,
    then records the admission attempt immediately.
    """
    k_hash = hash_key(SCOPE_REGISTER_IP, client_ip)
    lock = _get_bucket_lock(k_hash)
    with lock:
        db.expire_all()
        check_rate_limit(
            db,
            SCOPE_REGISTER_IP,
            client_ip,
            settings.AUTH_REGISTER_IP_MAX_ATTEMPTS,
            settings.AUTH_REGISTER_IP_WINDOW_SECONDS,
            MSG_REGISTER_RATE_LIMITED,
            now=now
        )
        record_attempt(SCOPE_REGISTER_IP, client_ip, now=now)


def reset_auth_limiter_state() -> None:
    """Helper for test cleanup to ensure clean test execution."""
    with SessionLocal() as lim_db:
        try:
            lim_db.query(AuthRateLimitEvent).delete()
            lim_db.commit()
        except Exception:
            lim_db.rollback()
