import os
from pathlib import Path
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.core.admin_provisioning import provision_initial_admin
from app.api import auth, projects, modules, tasks, copilot, exports
from app.api.admin import admin_router

# In development with SQLite, ensure tables exist; in production, Alembic handles migrations
if settings.APP_ENV == "development" and "sqlite" in settings.DATABASE_URL:
    Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production runtime safety validation
    if settings.IS_PROD or settings.APP_ENV == "production":
        from app.core.config import validate_production_runtime_safety
        validate_production_runtime_safety(settings)

    # Safe, idempotent startup admin provisioning
    try:
        with SessionLocal() as db:
            from app.core.admin_provisioning import (
                validate_production_credentials_safety,
                seed_development_admin,
                provision_initial_admin
            )
            if settings.IS_PROD or settings.APP_ENV == "production":
                validate_production_credentials_safety()
                if settings.ADMIN_BOOTSTRAP_ENABLED:
                    provision_initial_admin(db)
            else:
                if settings.APP_ENV == "development":
                    seed_development_admin(db)
                if settings.ADMIN_BOOTSTRAP_ENABLED:
                    provision_initial_admin(db)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Admin provisioning failed during startup: {e}")
        if settings.IS_PROD or settings.APP_ENV == "production":
            raise
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Venture Atlas business planning API",
    version="1.0.0",
    lifespan=lifespan
)

# Maintenance Mode Middleware (F-05)
@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    path = request.url.path
    # Allow health checks, admin APIs, static assets, and SPA fallback routes
    if (
        path in ("/health", "/health/live", "/api/health") or
        path.startswith("/api/admin") or
        path.startswith("/assets") or
        not path.startswith("/api/")
    ):
        return await call_next(request)

    # Check maintenance mode for user-facing API routes
    try:
        from app.services.system_setting_service import get_setting_bool
        with SessionLocal() as db:
            is_maintenance = get_setting_bool(db, "maintenance_mode", False)
            if is_maintenance:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "System is currently under maintenance. Please try again later."}
                )
    except Exception:
        pass

    return await call_next(request)

# CORS setup for local development and same-origin / cross-origin deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
api_v1 = FastAPI(title="API V1")
api_v1.include_router(auth.router)
api_v1.include_router(projects.router)
api_v1.include_router(modules.router)
api_v1.include_router(tasks.router)
api_v1.include_router(copilot.router)
api_v1.include_router(exports.router)
api_v1.include_router(admin_router)

@api_v1.get("/health")
def api_health(response: Response):
    db_connected = False
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_connected = True
    except Exception:
        db_connected = False

    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    is_configured = bool(settings.GEMINI_API_KEYS)
    try:
        from app.ai.gemini_service import ai_service
        available_generation_keys = len(ai_service._available_key_slots())
    except Exception:
        available_generation_keys = 0

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "Venture Atlas Backend",
        "environment": settings.APP_ENV,
        "database_connected": db_connected,
        "generation_configured": is_configured,
        "gemini_configured": is_configured,
        "generation_model": settings.GEMINI_MODEL,
        "configured_generation_keys": len(settings.GEMINI_API_KEYS),
        "available_generation_keys": available_generation_keys,
        "generation_provider_status": "ready" if available_generation_keys else ("unconfigured" if not is_configured else "cooling_down_or_unavailable")
    }

app.mount("/api", api_v1)

# Health check at root /health for Render & Docker container readiness (F-12)
@app.get("/health")
def root_readiness(response: Response):
    db_connected = False
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_connected = True
    except Exception:
        db_connected = False

    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "Venture Atlas Web Service",
            "database": "disconnected",
            "environment": settings.APP_ENV
        }

    return {
        "status": "ok",
        "service": "Venture Atlas Web Service",
        "database": "connected",
        "environment": settings.APP_ENV
    }

# Liveness probe: returns 200 as long as web server is accepting traffic (F-12)
@app.get("/health/live")
def root_liveness():
    return {
        "status": "alive",
        "service": "Venture Atlas Web Service",
        "environment": settings.APP_ENV
    }

# Frontend Static Files & SPA Fallback
# Check potential build paths (local vs Docker)
possible_dist_dirs = [
    Path(__file__).resolve().parent.parent.parent / "client" / "dist",
    Path("/app/client/dist"),
    Path(__file__).resolve().parent.parent / "client_dist"
]

client_dist = None
for p in possible_dist_dirs:
    if p.exists() and (p / "index.html").exists():
        client_dist = p
        break

if client_dist:
    assets_dir = client_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow /api and /health to not be captured by SPA fallback
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("health"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # If a specific static file is requested and exists in dist, serve it
        target_file = (client_dist / full_path).resolve()
        if not target_file.is_relative_to(client_dist.resolve()):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if full_path and target_file.is_file():
            return FileResponse(str(target_file))

        # Fallback to SPA index.html for React Router
        return FileResponse(str(client_dist / "index.html"))
