import hmac
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from app.core.config import settings

ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16
)

# Precomputed valid Argon2id hash to mitigate user enumeration timing side-channels
DUMMY_PASSWORD_HASH = ph.hash("DummyPasswordVerificationForTimingMitigation123!")

def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError):
        return False

def generate_session_token() -> str:
    """Generate a high-entropy cryptographically secure session token."""
    return secrets.token_hex(32)

def generate_csrf_token(session_token: str) -> str:
    """Generate a CSRF token bound to the session token."""
    key = settings.SESSION_SECRET.encode("utf-8")
    msg = session_token.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def verify_csrf_token(csrf_token: str, session_token: str) -> bool:
    """Constant-time verification of CSRF token against session token."""
    if not csrf_token or not session_token:
        return False
    expected = generate_csrf_token(session_token)
    return hmac.compare_digest(csrf_token, expected)
