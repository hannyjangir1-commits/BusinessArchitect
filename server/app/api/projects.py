import copy
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import User, Project, RoadmapTask, ModuleContent, ModuleVersion, CopilotMessage
from app.schemas.project import (
    ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse, ActiveModuleUpdateRequest,
    BulkDeleteProjectsRequest, BulkDeleteProjectsResponse
)
from app.api.deps import get_current_user, get_user_project, verify_csrf
from app.core.telemetry import record_analytics_event
from app.core.business_stage import normalize_business_stage
from app.core.module_types import normalize_module_type
from app.services.transaction_service import lock_record

router = APIRouter(prefix="/projects", tags=["Projects"])

def _project_completeness(project: Project) -> tuple[int, list[str]]:
    checks = {
        "Project description": project.description,
        "Industry": project.industry,
        "Target customers": project.target_customers,
        "Goals": project.goals,
        "Budget": project.budget,
    }
    missing = [label for label, value in checks.items() if not isinstance(value, str) or len(value.strip()) < 3]
    return round((len(checks) - len(missing)) / len(checks) * 100), missing

def _format_project_response(project: Project, db: Session) -> ProjectResponse:
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    tasks_count = len(tasks)
    completed_count = sum(1 for t in tasks if t.status in ("Finished", "Completed"))
    progress_percentage = int((completed_count / tasks_count) * 100) if tasks_count > 0 else 0

    # Determine genuinely generated modules for this specific project
    modules = db.query(ModuleContent).filter(ModuleContent.project_id == project.id).all()
    gen_mods = list(dict.fromkeys(
        normalize_module_type(m.module_type)
        for m in modules
        if m.active_version_id is not None
    ))
    if tasks_count > 0:
        if "execution_roadmap" not in gen_mods:
            gen_mods.append("execution_roadmap")

    completeness_percentage, completeness_missing = _project_completeness(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        stage=normalize_business_stage(project.stage),
        description=project.description,
        industry=project.industry,
        target_customers=project.target_customers,
        goals=project.goals,
        business_context=project.business_context,
        budget=project.budget,
        existing_stack=project.existing_stack or {},
        active_module=normalize_module_type(project.active_module),
        tasks_count=tasks_count,
        completed_tasks_count=completed_count,
        progress_percentage=progress_percentage,
        completeness_percentage=completeness_percentage,
        completeness_missing=completeness_missing,
        generated_modules=gen_mods,
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

MAX_PROJECTS_PER_USER = 10

def _check_and_lock_user_project_limit(db: Session, user_id: str):
    """
    Checks user's existing project count with row locking on the User record
    to strictly serialize concurrent project creation requests.
    Raises 400 Bad Request if project limit (10) has been reached.
    """
    # Lock the user record to prevent race conditions during concurrent project creations
    lock_record(db, User, user_id)
    project_count = db.query(func.count(Project.id)).filter(Project.user_id == user_id).scalar() or 0
    if project_count >= MAX_PROJECTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PROJECT_LIMIT_EXCEEDED: You have reached the maximum allowed limit of {MAX_PROJECTS_PER_USER} projects. Please delete an existing project before creating a new one."
        )

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_project(
    req: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Enforce concurrency-safe 10 project limit per user
    _check_and_lock_user_project_limit(db, current_user.id)

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
    # Option B: Create separate copy (Fork project work)
    if req.create_copy:
        # Enforce project limit if user chooses to create a copy
        _check_and_lock_user_project_limit(db, current_user.id)

        try:
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
                existing_stack=req.existing_stack if req.existing_stack is not None else (copy.deepcopy(project.existing_stack) if project.existing_stack else {}),
                active_module=normalize_module_type(project.active_module)
            )
            db.add(new_project)
            db.flush()

            # 1. Clone module history under canonical names. Older projects may
            # contain both roadmap module rows; keep their histories together
            # under the one unified roadmap record in the copy.
            source_modules = db.query(ModuleContent).filter(ModuleContent.project_id == project.id).all()
            module_groups = {}
            for source_module in source_modules:
                canonical_type = normalize_module_type(source_module.module_type)
                module_groups.setdefault(canonical_type, []).append(source_module)

            for canonical_type, grouped_modules in module_groups.items():
                new_module = ModuleContent(
                    project_id=new_project.id,
                    module_type=canonical_type,
                    active_version_id=None
                )
                db.add(new_module)
                db.flush()

                versions_to_clone = []
                active_source_module = max(
                    grouped_modules,
                    key=lambda candidate: (
                        str(candidate.updated_at or candidate.created_at),
                        candidate.module_type == canonical_type,
                    ),
                )
                active_source_versions = db.query(ModuleVersion).filter(
                    ModuleVersion.module_content_id == active_source_module.id
                ).order_by(ModuleVersion.version_number.asc()).all()
                active_source_version_id = active_source_module.active_version_id or next(
                    (version.id for version in reversed(active_source_versions) if version.is_active),
                    None,
                )

                for source_module in grouped_modules:
                    source_versions = db.query(ModuleVersion).filter(
                        ModuleVersion.module_content_id == source_module.id
                    ).order_by(ModuleVersion.created_at.asc(), ModuleVersion.version_number.asc()).all()
                    versions_to_clone.extend((source_module, version) for version in source_versions)

                versions_to_clone.sort(
                    key=lambda pair: (str(pair[1].created_at), pair[0].module_type == canonical_type, pair[1].version_number)
                )
                active_version_id = None
                for index, (source_module, source_version) in enumerate(versions_to_clone, start=1):
                    is_active = (
                        source_module.id == active_source_module.id
                        and source_version.id == active_source_version_id
                    )
                    new_ver = ModuleVersion(
                        module_content_id=new_module.id,
                        version_number=index,
                        version_name=source_version.version_name,
                        data=copy.deepcopy(source_version.data),
                        change_summary=source_version.change_summary,
                        is_active=is_active,
                        created_at=source_version.created_at,
                    )
                    db.add(new_ver)
                    db.flush()
                    if is_active:
                        active_version_id = new_ver.id

                new_module.active_version_id = active_version_id

            # 2. Clone RoadmapTask rows
            source_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).order_by(RoadmapTask.order_index.asc()).all()
            for st in source_tasks:
                new_task = RoadmapTask(
                    project_id=new_project.id,
                    task_code=st.task_code,
                    phase=st.phase,
                    title=st.title,
                    description=st.description,
                    timeline=st.timeline,
                    start_date=st.start_date,
                    end_date=st.end_date,
                    priority=st.priority,
                    status=st.status,
                    dependencies=list(st.dependencies or []),
                    deliverables=st.deliverables,
                    effort=st.effort,
                    assigned_to=st.assigned_to,
                    assigned_role=st.assigned_role,
                    department=st.department,
                    steps=list(st.steps or []),
                    is_overloaded=st.is_overloaded,
                    order_index=st.order_index,
                    is_ai_generated=st.is_ai_generated
                )
                db.add(new_task)

            # 3. Clone CopilotMessage rows
            source_messages = db.query(CopilotMessage).filter(CopilotMessage.project_id == project.id).order_by(CopilotMessage.created_at.asc()).all()
            for smsg in source_messages:
                new_msg = CopilotMessage(
                    project_id=new_project.id,
                    role=smsg.role,
                    content=smsg.content
                )
                db.add(new_msg)

            db.commit()
            db.refresh(new_project)
            return _format_project_response(new_project, db)
        except Exception:
            db.rollback()
            raise

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
        project.active_module = normalize_module_type(req.active_module)

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
    project.active_module = normalize_module_type(req.active_module)
    db.commit()
    return {"message": "Active module navigation saved", "active_module": project.active_module}

@router.post("/bulk-delete", response_model=BulkDeleteProjectsResponse, dependencies=[Depends(verify_csrf)])
def bulk_delete_projects(
    req: BulkDeleteProjectsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk deletes multiple projects owned by the authenticated user in an atomic transaction.
    Cascades to all associated module contents, versions, roadmap tasks, and copilot messages.
    """
    # Clean unique list of IDs
    unique_ids = list(dict.fromkeys(req.project_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="No project IDs provided for deletion")

    # Find projects matching requested IDs and owned by the current user
    projects_to_delete = db.query(Project).filter(
        Project.id.in_(unique_ids),
        Project.user_id == current_user.id
    ).all()

    if len(projects_to_delete) != len(unique_ids):
        found_ids = {p.id for p in projects_to_delete}
        missing_ids = [pid for pid in unique_ids if pid not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"One or more projects not found or unauthorized: {missing_ids}"
        )

    deleted_ids = []
    try:
        for proj in projects_to_delete:
            deleted_ids.append(proj.id)
            db.delete(proj)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete projects: {str(e)}"
        )

    return BulkDeleteProjectsResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
        message=f"Successfully deleted {len(deleted_ids)} project(s)."
    )

@router.delete("/{project_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_csrf)])
def delete_project(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    db.delete(project)
    db.commit()
    return {"message": f"Project '{project.name}' successfully deleted."}
