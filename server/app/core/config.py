import os
from typing import List
from pathlib import Path
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
        self.PROJECT_NAME: str = "Business Architect — Enterprise Blueprint"
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

        # Gemini AI
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # CORS
    @property
    def allowed_origins(self) -> List[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "")
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"]

    def get_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # For remote PostgreSQL / Supabase, guarantee sslmode=require if not explicitly specified
        if url.startswith("postgresql://") and "sslmode" not in url.lower() and "localhost" not in url and "127.0.0.1" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode=require"
        return url

settings = Settings()
