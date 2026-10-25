import os
from pathlib import Path
from fastapi import FastAPI, Request, Response, status, HTTPException
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

# Registration Admission Protection Middleware (Phase 2)
@app.middleware("http")
async def registration_admission_middleware(request: Request, call_next):
    # Strictly intercept registration requests before expensive body parsing or hashing
    if request.url.path in ("/api/auth/register", "/api/v1/auth/register") and request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 65536:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Registration request body exceeds maximum allowed size (64KB)."}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."}
                )

        from app.core.client_identity import extract_client_ip
        from app.core.auth_limiter import check_and_record_registration_admission
        client_ip = extract_client_ip(request, settings.TRUSTED_PROXIES)
        try:
            with SessionLocal() as lim_db:
                check_and_record_registration_admission(lim_db, client_ip)
        except HTTPException as he:
            return JSONResponse(
                status_code=he.status_code,
                content={"detail": he.detail},
                headers=he.headers
            )

        # Mark that admission check ran and was recorded before Pydantic parsing
        request.state.admission_checked = True

    return await call_next(request)

# Maintenance Mode Middleware (F-05)
@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    path = request.url.path
    clean_path = path.rstrip("/")
    # Strictly bypass maintenance checks for all liveness and health probes, admin APIs, static assets, and SPA routes
    if (
        clean_path in ("/health", "/health/live", "/api/health", "/api/health/live") or
        path.startswith("/health/live") or
        path.startswith("/api/health/live") or
        path.startswith("/api/admin") or
        path.startswith("/assets") or
        not path.startswith("/api/")
    ):
        return await call_next(request)

    # Check maintenance mode for user-facing API routes (Batch 02: In-Process TTL Cache)
    try:
        from app.services.system_setting_service import (
            check_maintenance_cache_fast,
            get_maintenance_mode_cached_async,
        )
        cached = check_maintenance_cache_fast()
        if cached is not None:
            is_maintenance = cached
        else:
            is_maintenance = await get_maintenance_mode_cached_async()

        if is_maintenance:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "System is currently under maintenance. Please try again later."}
            )
    except Exception:
        pass

    return await call_next(request)

# Observability & Request Correlation Diagnostics Middleware (Batch 01)
@app.middleware("http")
async def diagnostics_middleware(request: Request, call_next):
    import time
    import logging
    from app.core.diagnostics import (
        _current_request_id,
        _current_diagnostics,
        RequestDiagnostics,
        sanitize_or_generate_request_id,
        normalize_route_template
    )

    req_logger = logging.getLogger("request.timing")

    # 3.1 Request Correlation ID: sanitize incoming or generate fresh random ID
    incoming_id = request.headers.get("X-Request-ID")
    req_id = sanitize_or_generate_request_id(incoming_id)
    token_req_id = _current_request_id.set(req_id)

    # 3.2 & 3.3 Request Diagnostics & Stage Accumulator
    diag = RequestDiagnostics(req_id, enabled=settings.PERF_DIAGNOSTICS)
    token_diag = _current_diagnostics.set(diag)

    t_start = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        total_duration_ms = (time.perf_counter() - t_start) * 1000.0
        route_template = normalize_route_template(request)
        req_logger.error(
            "Request failed",
            extra={
                "request_id": req_id,
                "method": request.method,
                "route": route_template,
                "status_code": 500,
                "duration_ms": round(total_duration_ms, 2),
                "sql_statements": diag.sql.statements,
                "sql_commits": diag.sql.commits,
            }
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred.", "request_id": req_id},
            headers={"X-Request-ID": req_id}
        )
    else:
        total_duration_ms = (time.perf_counter() - t_start) * 1000.0
        route_template = normalize_route_template(request)

        # 3.2 Structured request completion logging without exposing query strings or bodies
        req_logger.info(
            "Request completed",
            extra={
                "request_id": req_id,
                "method": request.method,
                "route": route_template,
                "status_code": status_code,
                "duration_ms": round(total_duration_ms, 2),
                "sql_statements": diag.sql.statements,
                "sql_commits": diag.sql.commits,
            }
        )

        # 3.1 Return correlation ID header
        response.headers["X-Request-ID"] = req_id

        # 3.6 Standards-compatible Server-Timing header if diagnostics enabled
        if diag.enabled:
            timing_header = diag.build_server_timing_header(total_duration_ms)
            if timing_header:
                response.headers["Server-Timing"] = timing_header
            response.headers["X-SQL-Statements"] = str(diag.sql.statements)
            response.headers["X-SQL-Commits"] = str(diag.sql.commits)

        return response
    finally:
        _current_diagnostics.reset(token_diag)
        _current_request_id.reset(token_req_id)

# Response compression middleware for compressible payloads (Batch 03)
# Reliably respects minimum_size threshold and excludes already-compressed media types
import gzip as gzip_module
import zlib
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.datastructures import Headers as StarletteHeaders, MutableHeaders as StarletteMutableHeaders

class SmartGZipMiddleware:
    """
    ASGI response compression middleware that reliably respects the minimum_size threshold
    and prevents compressing already-compressed file types.
    """
    def __init__(self, app: ASGIApp, minimum_size: int = 1000):
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = StarletteHeaders(scope=scope)
        accept_encoding = headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            await self.app(scope, receive, send)
            return

        initial_message = None
        started = False
        buffer = []
        buffer_size = 0
        compressor = None

        async def send_wrapper(message: Message) -> None:
            nonlocal initial_message, started, buffer, buffer_size, compressor
            if message["type"] == "http.response.start":
                initial_message = message
                return

            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                if not started:
                    buffer.append(body)
                    buffer_size += len(body)

                    if not more_body:
                        # Full response received
                        full_body = b"".join(buffer)
                        raw_headers = StarletteMutableHeaders(raw=initial_message["headers"])
                        content_type = raw_headers.get("content-type", "").partition(";")[0].strip().lower()
                        is_excluded = any(
                            content_type.startswith(ex.rstrip("*"))
                            for ex in ("image/", "video/", "audio/", "font/", "application/zip", "application/gzip", "text/event-stream")
                        ) or "content-encoding" in raw_headers

                        if buffer_size < self.minimum_size or is_excluded:
                            # Send original uncompressed response
                            await send(initial_message)
                            await send({"type": "http.response.body", "body": full_body, "more_body": False})
                        else:
                            # Compress with gzip
                            compressed = gzip_module.compress(full_body, compresslevel=6)
                            raw_headers.add_vary_header("Accept-Encoding")
                            raw_headers["Content-Encoding"] = "gzip"
                            raw_headers["Content-Length"] = str(len(compressed))
                            await send(initial_message)
                            await send({"type": "http.response.body", "body": compressed, "more_body": False})
                        started = True
                        return
                    else:
                        if buffer_size < self.minimum_size:
                            # Keep buffering until threshold reached
                            return
                        else:
                            started = True
                            full_buf = b"".join(buffer)
                            raw_headers = StarletteMutableHeaders(raw=initial_message["headers"])
                            content_type = raw_headers.get("content-type", "").partition(";")[0].strip().lower()
                            is_excluded = any(
                                content_type.startswith(ex.rstrip("*"))
                                for ex in ("image/", "video/", "audio/", "font/", "application/zip", "application/gzip", "text/event-stream")
                            ) or "content-encoding" in raw_headers

                            if is_excluded:
                                await send(initial_message)
                                await send({"type": "http.response.body", "body": full_buf, "more_body": True})
                            else:
                                compressor = zlib.compressobj(6, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
                                compressed = compressor.compress(full_buf) + compressor.flush(zlib.Z_SYNC_FLUSH)
                                raw_headers.add_vary_header("Accept-Encoding")
                                raw_headers["Content-Encoding"] = "gzip"
                                if "content-length" in raw_headers:
                                    del raw_headers["content-length"]
                                await send(initial_message)
                                await send({"type": "http.response.body", "body": compressed, "more_body": True})
                            return
                else:
                    if compressor is not None:
                        if more_body:
                            compressed = compressor.compress(body) + compressor.flush(zlib.Z_SYNC_FLUSH)
                        else:
                            compressed = compressor.compress(body) + compressor.flush()
                        await send({"type": "http.response.body", "body": compressed, "more_body": more_body})
                    else:
                        await send(message)

        await self.app(scope, receive, send_wrapper)

app.add_middleware(SmartGZipMiddleware, minimum_size=1000)


# CORS setup for local development and same-origin / cross-origin deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.core.client_identity import TrustedProxyMiddleware
app.add_middleware(TrustedProxyMiddleware)

# API Routers
api_v1 = FastAPI(title="API V1")

# Global sanitized exception handlers with correlation IDs
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    from app.core.diagnostics import _current_request_id
    req_id = _current_request_id.get() or "unknown"
    import logging
    logging.getLogger("uvicorn.error").error(
        f"Unhandled exception on {request.method} {request.url.path} [request_id={req_id}]: {type(exc).__name__}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "request_id": req_id
        },
        headers={"X-Request-ID": req_id}
    )

async def global_http_exception_handler(request: Request, exc: HTTPException):
    from app.core.diagnostics import _current_request_id
    req_id = _current_request_id.get() or "unknown"
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = req_id
    content = {"detail": exc.detail}
    if exc.status_code >= 500:
        content["request_id"] = req_id
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers
    )

app.add_exception_handler(Exception, global_unhandled_exception_handler)
app.add_exception_handler(HTTPException, global_http_exception_handler)
api_v1.add_exception_handler(Exception, global_unhandled_exception_handler)
api_v1.add_exception_handler(HTTPException, global_http_exception_handler)

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

    provider_status = "configured" if available_generation_keys else ("unconfigured" if not is_configured else "cooldown_active")

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
        "generation_provider_status": provider_status,
        "provider_probe_status": "provider_not_probed"
    }

@api_v1.get("/health/live")
def api_liveness():
    return {
        "status": "alive",
        "service": "Venture Atlas Backend",
        "environment": settings.APP_ENV
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

class HashedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

if client_dist:
    assets_dir = client_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", HashedStaticFiles(directory=str(assets_dir)), name="assets")

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
            headers = {}
            if target_file.is_relative_to((client_dist / "assets").resolve()):
                headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif target_file.name == "index.html":
                headers["Cache-Control"] = "no-cache"
            else:
                headers["Cache-Control"] = "no-cache"
            return FileResponse(str(target_file), headers=headers)

        # Fallback to SPA index.html for client-side routing
        return FileResponse(
            str(client_dist / "index.html"),
            headers={"Cache-Control": "no-cache"}
        )
