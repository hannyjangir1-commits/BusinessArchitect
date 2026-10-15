import os
from pathlib import Path
from fastapi import FastAPI, Request
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
    # Safe, idempotent startup admin provisioning
    try:
        with SessionLocal() as db:
            provision_initial_admin(db)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Admin provisioning failed during startup: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Blueprint & Business Architect API",
    version="1.0.0",
    lifespan=lifespan
)

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
def api_health():
    db_connected = False
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_connected = True
    except Exception:
        db_connected = False

    is_configured = bool(settings.GEMINI_API_KEY)

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "Business Architect Backend",
        "environment": settings.APP_ENV,
        "database_connected": db_connected,
        "generation_configured": is_configured,
        "gemini_configured": is_configured
    }

app.mount("/api", api_v1)

# Health check at root /health for Render
@app.get("/health")
def root_health():
    return {
        "status": "ok",
        "service": "Business Architect Web Service",
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
        # Allow /api and /health to not be captured
        if full_path.startswith("api/") or full_path == "health":
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # If a specific static file is requested and exists in dist, serve it
        target_file = client_dist / full_path
        if full_path and target_file.is_file():
            return FileResponse(str(target_file))

        # Fallback to SPA index.html for React Router
        return FileResponse(str(client_dist / "index.html"))
