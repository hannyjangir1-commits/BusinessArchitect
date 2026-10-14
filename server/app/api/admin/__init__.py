from fastapi import APIRouter
from app.api.admin import (
    auth, dashboard, users, projects, ai_ops,
    analytics, system, integrity, security, audit,
    config, maintenance, reports
)

admin_router = APIRouter(prefix="/admin")

admin_router.include_router(auth.router)
admin_router.include_router(dashboard.router)
admin_router.include_router(users.router)
admin_router.include_router(projects.router)
admin_router.include_router(ai_ops.router)
admin_router.include_router(analytics.router)
admin_router.include_router(system.router)
admin_router.include_router(integrity.router)
admin_router.include_router(security.router)
admin_router.include_router(audit.router)
admin_router.include_router(config.router)
admin_router.include_router(maintenance.router)
admin_router.include_router(reports.router)

__all__ = ["admin_router"]
