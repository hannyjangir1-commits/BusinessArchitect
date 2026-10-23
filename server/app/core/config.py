import os
import re
import urllib.parse
from typing import List
from pathlib import Path
# pyrefly: ignore[missing-import]
from dotenv import load_dotenv

# Load .env if present in current dir or repo root
root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
server_env = Path(__file__).resolve().parent.parent.parent / ".env"
if server_env.exists():
    load_dotenv(server_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()

class Settings:
    def __init__(self):
        self.PROJECT_NAME: str = "Venture Atlas — Business Planning"
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.IS_PROD: bool = self.APP_ENV.lower() == "production"

        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Security
        self.SESSION_SECRET: str = os.getenv("SESSION_SECRET", "super-secret-development-session-key-minimum-32-chars")
        self.COOKIE_NAME: str = "aba_session"
        self.CSRF_COOKIE_NAME: str = "aba_csrf"
        self.COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true" or self.IS_PROD
        self.COOKIE_SAMESITE: str = "lax"
        self.SESSION_EXPIRE_DAYS: int = 7

        # Admin Provisioning (controlled via ADMIN_BOOTSTRAP_ENABLED, supports both INITIAL_ADMIN_* and ADMIN_BOOTSTRAP_* aliases)
        self.ADMIN_BOOTSTRAP_ENABLED: bool = os.getenv("ADMIN_BOOTSTRAP_ENABLED", "false").lower() in ("true", "1", "yes")
        self.INITIAL_ADMIN_USERNAME: str = os.getenv("INITIAL_ADMIN_USERNAME") or os.getenv("ADMIN_BOOTSTRAP_USERNAME", "")
        self.INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD") or os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
        self.INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL") or os.getenv("ADMIN_BOOTSTRAP_EMAIL", "")

        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dev_database.db")

        # Gemini generation. GEMINI_API_KEYS is the preferred comma/newline-separated
        # pool; GEMINI_API_KEY remains a backwards-compatible single-key alias.
        raw_key_pool = os.getenv("GEMINI_API_KEYS", "")
        legacy_key = os.getenv("GEMINI_API_KEY", "").strip()
        parsed_keys = [key.strip() for key in re.split(r"[,;\s]+", raw_key_pool) if key.strip()]
        if not parsed_keys and legacy_key:
            parsed_keys = [legacy_key]
        self.GEMINI_API_KEYS: List[str] = list(dict.fromkeys(parsed_keys))
        self.GEMINI_API_KEY: str = self.GEMINI_API_KEYS[0] if self.GEMINI_API_KEYS else ""
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.GEMINI_TOTAL_TIMEOUT_SECONDS: int = max(
            10, min(int(os.getenv("GEMINI_TOTAL_TIMEOUT_SECONDS", "90")), 300)
        )
        self.GEMINI_KEY_COOLDOWN_SECONDS: int = max(
            15, min(int(os.getenv("GEMINI_KEY_COOLDOWN_SECONDS", "120")), 3600)
        )
        self.GEMINI_FALLBACK_MODELS_ENABLED: bool = os.getenv("GEMINI_FALLBACK_MODELS_ENABLED", "true").lower() in ("true", "1", "yes")

        # Observability & Performance Diagnostics (Batch 01)
        self.PERF_DIAGNOSTICS: bool = os.getenv("PERF_DIAGNOSTICS", "false").lower() in ("true", "1", "yes")

        # Authenticated Activity Write Throttling (Batch 02)
        # Bounded between 60 seconds (1 minute) and 86400 seconds (24 hours). Default: 600 seconds (10 minutes).
        raw_activity_throttle = os.getenv("USER_ACTIVITY_THROTTLE_SECONDS", "600").strip()
        try:
            parsed_throttle = int(raw_activity_throttle)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid USER_ACTIVITY_THROTTLE_SECONDS '{raw_activity_throttle}': must be an integer."
            ) from exc

        if parsed_throttle < 60 or parsed_throttle > 86400:
            raise ValueError(
                f"Invalid USER_ACTIVITY_THROTTLE_SECONDS '{parsed_throttle}': value must be between 60 and 86400 seconds."
            )
        self.USER_ACTIVITY_THROTTLE_SECONDS: int = parsed_throttle


    # CORS
    @property
    def allowed_origins(self) -> List[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "")
        origins = []
        if raw:
            origins.extend([o.strip() for o in raw.split(",") if o.strip()])
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
        if render_url and render_url not in origins:
            origins.append(render_url)
        if origins:
            return origins
        return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"]

    def get_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        # Automatically percent-encode passwords with special characters (e.g. unescaped '@')
        if "://" in url and "@" in url:
            scheme, rest = url.split("://", 1)
            authority, *path_parts = rest.split("/", 1)
            path = "/" + path_parts[0] if path_parts else ""
            if authority.count("@") > 1:
                userinfo, hostinfo = authority.rsplit("@", 1)
                if ":" in userinfo:
                    username, password = userinfo.split(":", 1)
                    unquoted_pw = urllib.parse.unquote(password)
                    encoded_pw = urllib.parse.quote_plus(unquoted_pw)
                    url = f"{scheme}://{username}:{encoded_pw}@{hostinfo}{path}"

        # For remote PostgreSQL / Supabase, guarantee sslmode=require if not explicitly specified
        if (url.startswith("postgresql://") or url.startswith("postgresql+")) and "sslmode" not in url.lower() and "localhost" not in url and "127.0.0.1" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        return url

KNOWN_DEV_SESSION_SECRETS = {
    "super-secret-development-session-key-minimum-32-chars",
    "test-session-secret-key-minimum-32-chars-long",
    "dev-secret-key-business-architect-minimum-32-chars",
    "a_very_long_random_secret_at_least_32_characters_long",
    "secret",
    "changeme",
    "development"
}

def validate_production_runtime_safety(cfg: Settings = None) -> None:
    """
    Validates that production environment variables are secure, explicit, and non-development.
    Fails safely by raising RuntimeError if insecure development defaults are detected.
    """
    target = cfg or settings
    is_prod = getattr(target, "IS_PROD", False) or getattr(target, "APP_ENV", "").lower() == "production"
    if not is_prod:
        return

    # 1. SESSION_SECRET
    secret = getattr(target, "SESSION_SECRET", "")
    if not secret or len(secret) < 32 or secret in KNOWN_DEV_SESSION_SECRETS:
        raise RuntimeError(
            "Production requires a strong, unique SESSION_SECRET of at least 32 characters. "
            "Known development session secrets and fallbacks are strictly rejected."
        )

    # 2. DATABASE_URL
    raw_db = getattr(target, "DATABASE_URL", "")
    raw_env_db = os.getenv("DATABASE_URL", "")
    if not raw_env_db or "sqlite" in raw_db.lower():
        raise RuntimeError(
            "Production requires an explicit production DATABASE_URL (e.g. PostgreSQL / Supabase). "
            "Local SQLite database fallbacks are strictly rejected in production."
        )

    # 3. ALLOWED_ORIGINS
    raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if not raw_origins:
        raise RuntimeError(
            "Production requires an explicit ALLOWED_ORIGINS allowlist or RENDER_EXTERNAL_URL. "
            "Default localhost CORS origins are strictly rejected in production."
        )

    # 4. COOKIE_SECURE
    if not getattr(target, "COOKIE_SECURE", False):
        raise RuntimeError(
            "Production requires COOKIE_SECURE=True to ensure session cookies are only transmitted over HTTPS."
        )

settings = Settings()
