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
    PROJECT_NAME: str = "AI Business Architect — Enterprise Blueprint"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    IS_PROD: bool = APP_ENV.lower() == "production"

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Security
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "super-secret-development-session-key-minimum-32-chars")
    COOKIE_NAME: str = "aba_session"
    CSRF_COOKIE_NAME: str = "aba_csrf"
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true" or IS_PROD
    COOKIE_SAMESITE: str = "lax"
    SESSION_EXPIRE_DAYS: int = 7

    # Admin Provisioning
    INITIAL_ADMIN_USERNAME: str = os.getenv("INITIAL_ADMIN_USERNAME", "HannyAdmin")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "Hanny@BusinessArchitect")
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "admin@businessarchitect.internal")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dev_database.db")

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
        return url

settings = Settings()
