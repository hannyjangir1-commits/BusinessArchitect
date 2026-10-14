from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import User, Project, RoadmapTask, ModuleContent, ModuleVersion
from app.schemas.project import (
    ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse, ActiveModuleUpdateRequest
)
from app.api.deps import get_current_user, get_user_project, verify_csrf
from app.core.telemetry import record_analytics_event

router = APIRouter(prefix="/projects", tags=["Projects"])

def _format_project_response(project: Project, db: Session) -> ProjectResponse:
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    tasks_count = len(tasks)
    completed_count = sum(1 for t in tasks if t.status in ("Finished", "Completed"))
    progress_percentage = int((completed_count / tasks_count) * 100) if tasks_count > 0 else 0

    return ProjectResponse(
        id=project.id,
        name=project.name,
        stage=project.stage,
        description=project.description,
        industry=project.industry,
        target_customers=project.target_customers,
        goals=project.goals,
        business_context=project.business_context,
        budget=project.budget,
        existing_stack=project.existing_stack or {},
        active_module=project.active_module or "overview",
        tasks_count=tasks_count,
        completed_tasks_count=completed_count,
        progress_percentage=progress_percentage,
        created_at=project.created_at,
        updated_at=project.updated_at
    )

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.updated_at.desc()).all()

    return [_format_project_response(p, db) for p in projects]

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_project(
    req: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = Project(
        user_id=current_user.id,
        name=req.name,
        stage=req.stage,
        description=req.description,
        industry=req.industry,
        target_customers=req.target_customers,
        goals=req.goals,
        business_context=req.business_context,
        budget=req.budget,
        existing_stack=req.existing_stack or {},
        active_module="overview"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    record_analytics_event(db, user_id=current_user.id, project_id=project.id, event_name="project_created")

    return _format_project_response(project, db)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    return _format_project_response(project, db)

@router.put("/{project_id}", response_model=ProjectResponse, dependencies=[Depends(verify_csrf)])
def update_project(
    req: ProjectUpdateRequest,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Option B: Create separate copy
    if req.create_copy:
        new_project = Project(
            user_id=current_user.id,
            name=req.name or f"{project.name} (Copy)",
            stage=req.stage or project.stage,
            description=req.description or project.description,
            industry=req.industry or project.industry,
            target_customers=req.target_customers or project.target_customers,
            goals=req.goals or project.goals,
            business_context=req.business_context or project.business_context,
            budget=req.budget or project.budget,
            existing_stack=req.existing_stack if req.existing_stack is not None else project.existing_stack,
            active_module="overview"
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return _format_project_response(new_project, db)

    # Option A: Replace existing in-place
    if req.name is not None:
        project.name = req.name
    if req.stage is not None:
        project.stage = req.stage
    if req.description is not None:
        project.description = req.description
    if req.industry is not None:
        project.industry = req.industry
    if req.target_customers is not None:
        project.target_customers = req.target_customers
    if req.goals is not None:
        project.goals = req.goals
    if req.business_context is not None:
        project.business_context = req.business_context
    if req.budget is not None:
        project.budget = req.budget
    if req.existing_stack is not None:
        project.existing_stack = req.existing_stack
    if req.active_module is not None:
        project.active_module = req.active_module

    db.commit()
    db.refresh(project)
    return _format_project_response(project, db)

@router.patch("/{project_id}/active-module", dependencies=[Depends(verify_csrf)])
def update_active_module(
    req: ActiveModuleUpdateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Persists the active navigation tab per-project in the database."""
    project.active_module = req.active_module
    db.commit()
    return {"message": "Active module navigation saved", "active_module": req.active_module}

@router.delete("/{project_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_csrf)])
def delete_project(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    db.delete(project)
    db.commit()
    return {"message": f"Project '{project.name}' successfully deleted."}
