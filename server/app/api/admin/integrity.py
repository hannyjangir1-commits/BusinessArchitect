from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask,
    CopilotMessage, Session as DBSession, AuditLog, AuthRateLimitEvent
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.telemetry import record_audit_log
from app.services.version_service import VersionService
from app.services.roadmap_service import RoadmapDomainService

router = APIRouter(prefix="/integrity", tags=["Admin Data Integrity"])

class RepairActionRequest(BaseModel):
    action: str  # clean_expired_sessions, fix_missing_active_versions, prune_excess_versions, clean_orphaned_records
    confirmation: bool = False

@router.get("/scan")
def run_integrity_scan(
    current_admin: User = Depends(require_permission("run_integrity_scan")),
    db: Session = Depends(get_db)
):
    findings = []

    # 1. Orphaned projects (user_id not in users)
    orphaned_projects = db.query(Project.id, Project.name).filter(
        ~Project.user_id.in_(db.query(User.id))
    ).all()
    if orphaned_projects:
        findings.append({
            "code": "ORPHANED_PROJECTS",
            "severity": "high",
            "title": f"{len(orphaned_projects)} Orphaned Project(s)",
            "description": "Projects found whose owner user no longer exists in database",
            "count": len(orphaned_projects),
            "repairable": True,
            "repair_action": "clean_orphaned_records",
            "items": [{"id": p[0], "name": p[1]} for p in orphaned_projects[:10]]
        })

    # 2. Orphaned module contents
    orphaned_modules = db.query(ModuleContent.id, ModuleContent.module_type).filter(
        ~ModuleContent.project_id.in_(db.query(Project.id))
    ).all()
    if orphaned_modules:
        findings.append({
            "code": "ORPHANED_MODULES",
            "severity": "medium",
            "title": f"{len(orphaned_modules)} Orphaned Module Content Record(s)",
            "description": "Module contents found whose parent project does not exist",
            "count": len(orphaned_modules),
            "repairable": True,
            "repair_action": "clean_orphaned_records",
            "items": [{"id": m[0], "type": m[1]} for m in orphaned_modules[:10]]
        })

    # 3. Invalid active version pointers / state (Fix B06)
    modules_with_missing_active = []
    all_modules = db.query(ModuleContent).all()
    for m in all_modules:
        versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == m.id).all()
        if not versions:
            if m.active_version_id is not None:
                modules_with_missing_active.append(m.id)
        else:
            if not m.active_version_id:
                modules_with_missing_active.append(m.id)
            else:
                target = next((v for v in versions if v.id == m.active_version_id), None)
                if not target:
                    modules_with_missing_active.append(m.id)
                else:
                    active_count = sum(1 for v in versions if v.is_active)
                    if not target.is_active or active_count != 1:
                        modules_with_missing_active.append(m.id)

    if modules_with_missing_active:
        findings.append({
            "code": "INVALID_ACTIVE_VERSION",
            "severity": "medium",
            "title": f"{len(modules_with_missing_active)} Module(s) with Invalid Active Version Reference",
            "description": "Modules whose active_version_id is null, foreign, or mismatched with version active flags",
            "count": len(modules_with_missing_active),
            "repairable": True,
            "repair_action": "fix_missing_active_versions",
            "items": [{"module_id": mid} for mid in modules_with_missing_active[:10]]
        })

    # 4. Modules with more than 5 versions
    excess_version_modules = (
        db.query(ModuleVersion.module_content_id, func.count(ModuleVersion.id))
        .group_by(ModuleVersion.module_content_id)
        .having(func.count(ModuleVersion.id) > 5)
        .all()
    )
    if excess_version_modules:
        findings.append({
            "code": "EXCESS_VERSIONS",
            "severity": "low",
            "title": f"{len(excess_version_modules)} Module(s) Exceeding 5-Version Limit",
            "description": "Modules with more than 5 versions stored",
            "count": len(excess_version_modules),
            "repairable": True,
            "repair_action": "prune_excess_versions",
            "items": [{"module_id": m[0], "version_count": m[1]} for m in excess_version_modules[:10]]
        })

    # 5. Expired sessions
    now = datetime.now(timezone.utc)
    expired_sessions_count = db.query(func.count(DBSession.id)).filter(DBSession.expires_at < now).scalar() or 0
    if expired_sessions_count > 0:
        findings.append({
            "code": "EXPIRED_SESSIONS",
            "severity": "low",
            "title": f"{expired_sessions_count} Expired Session(s) Lingering",
            "description": "Sessions past expiration time that have not been pruned",
            "count": expired_sessions_count,
            "repairable": True,
            "repair_action": "clean_expired_sessions",
            "items": []
        })

    # 6. Expired rate limit events
    cutoff_24h = now - timedelta(hours=24)
    expired_limits_count = db.query(func.count(AuthRateLimitEvent.id)).filter(AuthRateLimitEvent.created_at < cutoff_24h).scalar() or 0
    if expired_limits_count > 0:
        findings.append({
            "code": "EXPIRED_RATE_LIMITS",
            "severity": "low",
            "title": f"{expired_limits_count} Expired Rate Limit Event(s) Lingering",
            "description": "Auth rate limit events past the 24-hour retention window",
            "count": expired_limits_count,
            "repairable": True,
            "repair_action": "clean_expired_rate_limits",
            "items": []
        })

    return {
        "status": "clean" if not findings else "issues_found",
        "findings_count": len(findings),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "findings": findings
    }

@router.post("/repair")
def execute_repair(
    req: RepairActionRequest,
    current_admin: User = Depends(require_permission("execute_repair")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    if not req.confirmation:
        raise HTTPException(status_code=400, detail="Repair requires explicit confirmation parameter set to true")

    action = req.action.strip()
    repaired_count = 0

    try:
        errors = []
        if action == "clean_expired_sessions":
            now = datetime.now(timezone.utc)
            repaired_count = db.query(DBSession).filter(DBSession.expires_at < now).delete()
            db.commit()

        elif action == "fix_missing_active_versions":
            from app.services.task_graph_validator import project_first_lock
            all_modules = db.query(ModuleContent).all()
            all_modules.sort(key=lambda m: (m.project_id, m.id))
            for m in all_modules:
                proj = db.query(Project).filter(Project.id == m.project_id).first()
                if not proj:
                    continue
                try:
                    with project_first_lock(db, proj.id, m.id):
                        was_repaired = VersionService.repair_active_version_for_module(db, m)
                        if was_repaired:
                            repaired_count += 1
                            db.commit()
                except Exception as mod_err:
                    db.rollback()
                    errors.append({
                        "module_id": m.id,
                        "project_id": m.project_id,
                        "error": str(mod_err)
                    })

        elif action == "prune_excess_versions":
            from app.services.task_graph_validator import project_first_lock
            excess_modules = (
                db.query(ModuleContent)
                .join(ModuleVersion, ModuleVersion.module_content_id == ModuleContent.id)
                .group_by(ModuleContent.id)
                .having(func.count(ModuleVersion.id) > 5)
                .all()
            )
            excess_modules.sort(key=lambda m: (m.project_id, m.id))
            for m in excess_modules:
                try:
                    with project_first_lock(db, m.project_id, m.id):
                        deleted = VersionService.prune_excess_versions_for_module(db, m, limit=5)
                        if deleted > 0:
                            repaired_count += deleted
                            db.commit()
                except Exception as mod_err:
                    db.rollback()
                    errors.append({
                        "module_id": m.id,
                        "project_id": m.project_id,
                        "error": str(mod_err)
                    })

        elif action == "clean_orphaned_records":
            # Delete orphaned tasks
            del_tasks = db.query(RoadmapTask).filter(~RoadmapTask.project_id.in_(db.query(Project.id))).delete(synchronize_session=False)
            # Delete orphaned copilot messages
            del_msgs = db.query(CopilotMessage).filter(~CopilotMessage.project_id.in_(db.query(Project.id))).delete(synchronize_session=False)
            # Delete orphaned modules
            del_mods = db.query(ModuleContent).filter(~ModuleContent.project_id.in_(db.query(Project.id))).delete(synchronize_session=False)
            # Delete orphaned projects
            del_projs = db.query(Project).filter(~Project.user_id.in_(db.query(User.id))).delete(synchronize_session=False)
            repaired_count = del_tasks + del_msgs + del_mods + del_projs
            db.commit()

        elif action == "clean_expired_rate_limits":
            from app.core.auth_limiter import cleanup_expired_events
            repaired_count = cleanup_expired_events(max_retention_seconds=86400, batch_size=5000)

        else:
            raise HTTPException(status_code=400, detail=f"Unrecognized repair action: '{action}'")

        outcome = "partial_success" if errors and repaired_count > 0 else ("failed" if errors else "success")
        record_audit_log(
            db,
            actor_id=current_admin.id,
            action=f"integrity_repair_{action}",
            target_type="data_repair",
            target_id=action,
            outcome=outcome,
            reason=f"Admin executed transactional repair '{action}' (repaired: {repaired_count}, failed: {len(errors)})",
            details={"repaired_count": repaired_count, "errors": errors}
        )

        if errors and repaired_count == 0:
            raise HTTPException(
                status_code=500,
                detail=f"Repair '{action}' failed for all targeted modules: {errors[0].get('error')}"
            )

        msg = f"Successfully executed repair '{action}'. Repaired {repaired_count} record(s)."
        if errors:
            msg = f"Executed repair '{action}' with partial completion. Repaired {repaired_count} record(s), {len(errors)} module(s) failed."

        return {
            "message": msg,
            "action": action,
            "repaired_count": repaired_count,
            "status": outcome,
            "errors": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Repair transaction failed due to an unexpected internal error."
        )
