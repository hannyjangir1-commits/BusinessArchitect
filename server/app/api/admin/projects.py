from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, RoadmapTask, CopilotMessage, AIOperation, AuditLog
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.telemetry import record_audit_log

router = APIRouter(prefix="/projects", tags=["Admin Project Management"])

class TransferOwnershipRequest(BaseModel):
    new_owner_username: str

@router.get("")
def list_projects(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    stage: Optional[str] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|name|updated_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_admin: User = Depends(require_permission("manage_projects")),
    db: Session = Depends(get_db)
):
    query = db.query(Project).join(User, Project.user_id == User.id)

    if search:
        search_clean = f"%{search.strip()}%"
        query = query.filter((Project.name.ilike(search_clean)) | (User.username.ilike(search_clean)))

    if stage and stage != "all":
        query = query.filter(Project.stage == stage)

    total = query.count()

    order_col = getattr(Project, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(asc(order_col))

    offset = (page - 1) * limit
    projects = query.offset(offset).limit(limit).all()

    # Pre-fetch module and task counts
    proj_ids = [p.id for p in projects]
    mod_counts = dict(
        db.query(ModuleContent.project_id, func.count(ModuleContent.id))
        .filter(ModuleContent.project_id.in_(proj_ids))
        .group_by(ModuleContent.project_id)
        .all()
    ) if proj_ids else {}

    task_counts = dict(
        db.query(RoadmapTask.project_id, func.count(RoadmapTask.id))
        .filter(RoadmapTask.project_id.in_(proj_ids))
        .group_by(RoadmapTask.project_id)
        .all()
    ) if proj_ids else {}

    results = []
    for p in projects:
        results.append({
            "id": p.id,
            "name": p.name,
            "owner_username": p.user.username if p.user else "Unknown",
            "owner_id": p.user_id,
            "stage": p.stage,
            "industry": p.industry,
            "active_module": p.active_module,
            "modules_count": mod_counts.get(p.id, 0),
            "tasks_count": task_counts.get(p.id, 0),
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat()
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": results
    }

@router.get("/{project_id}")
def get_project_detail(
    project_id: str,
    current_admin: User = Depends(require_permission("manage_projects")),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Module contents and versions summaries (do not leak full business plans unnecessarily)
    modules = db.query(ModuleContent).filter(ModuleContent.project_id == project_id).all()
    module_summaries = []
    for m in modules:
        version_count = db.query(func.count(ModuleVersion.id)).filter(ModuleVersion.module_content_id == m.id).scalar() or 0
        latest_version = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == m.id).order_by(desc(ModuleVersion.version_number)).first()
        module_summaries.append({
            "id": m.id,
            "module_type": m.module_type,
            "active_version_id": m.active_version_id,
            "version_count": version_count,
            "latest_version_name": latest_version.version_name if latest_version else None,
            "latest_version_number": latest_version.version_number if latest_version else 0,
            "updated_at": m.updated_at.isoformat()
        })

    # Task stats
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project_id).all()
    task_stats = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.status == "Pending"),
        "in_progress": sum(1 for t in tasks if t.status in ("In Progress", "Ongoing")),
        "finished": sum(1 for t in tasks if t.status == "Finished")
    }

    copilot_count = db.query(func.count(CopilotMessage.id)).filter(CopilotMessage.project_id == project_id).scalar() or 0

    recent_ai_ops = db.query(AIOperation).filter(
        AIOperation.project_id == project_id
    ).order_by(desc(AIOperation.created_at)).limit(10).all()

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "owner": {
                "id": project.user.id if project.user else None,
                "username": project.user.username if project.user else "Unknown",
                "email": project.user.email if project.user else None
            },
            "stage": project.stage,
            "industry": project.industry,
            "description": project.description,
            "active_module": project.active_module,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat()
        },
        "modules": module_summaries,
        "task_stats": task_stats,
        "copilot_messages_count": copilot_count,
        "recent_ai_operations": [
            {
                "id": op.id,
                "module_type": op.module_type,
                "operation_type": op.operation_type,
                "model_name": op.model_name,
                "status": op.status,
                "duration_ms": op.duration_ms,
                "created_at": op.created_at.isoformat()
            }
            for op in recent_ai_ops
        ]
    }

@router.post("/{project_id}/transfer")
def transfer_project_ownership(
    project_id: str,
    req: TransferOwnershipRequest,
    current_admin: User = Depends(require_permission("manage_projects")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    target_user = db.query(User).filter(User.username == req.new_owner_username.strip()).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{req.new_owner_username}' not found")

    if target_user.id == project.user_id:
        raise HTTPException(status_code=400, detail="Target user is already the owner of this project")

    previous_owner_id = project.user_id
    previous_owner_name = project.user.username if project.user else "Unknown"

    project.user_id = target_user.id
    project.updated_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="project_transfer_ownership",
        target_type="project",
        target_id=project.id,
        outcome="success",
        reason=f"Transferred from '{previous_owner_name}' to '{target_user.username}'",
        details={
            "project_name": project.name,
            "previous_owner_id": previous_owner_id,
            "new_owner_id": target_user.id
        }
    )

    return {
        "message": f"Project '{project.name}' successfully transferred to '{target_user.username}'.",
        "project_id": project.id,
        "new_owner_username": target_user.username
    }

@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    confirm_project_name: str = Query(..., description="Must match target project name exactly"),
    current_admin: User = Depends(require_permission("manage_projects")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if confirm_project_name.strip() != project.name:
        raise HTTPException(status_code=400, detail="Confirmation project name does not match target project")

    proj_name = project.name
    owner_name = project.user.username if project.user else "Unknown"

    try:
        db.delete(project)
        db.commit()

        record_audit_log(
            db,
            actor_id=current_admin.id,
            action="project_delete",
            target_type="project",
            target_id=project_id,
            outcome="success",
            reason=f"Permanently deleted project '{proj_name}' (owned by {owner_name})",
            details={"project_name": proj_name, "owner": owner_name}
        )

        return {"message": f"Project '{proj_name}' has been permanently deleted."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")
