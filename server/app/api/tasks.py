from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, RoadmapTask
from app.schemas.task import (
    TaskCreateRequest, TaskUpdateRequest, TaskResponse, RoadmapSummaryResponse
)
from app.api.deps import get_user_project, verify_csrf

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["Roadmap Tasks"])

@router.get("", response_model=List[TaskResponse])
def list_tasks(
    timeline: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    query = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id)

    if timeline and timeline.lower() != "all":
        query = query.filter(RoadmapTask.timeline == timeline)
    if status and status.lower() != "all":
        query = query.filter(RoadmapTask.status == status)
    if search:
        query = query.filter(
            RoadmapTask.title.ilike(f"%{search}%") | RoadmapTask.description.ilike(f"%{search}%")
        )

    return query.order_by(RoadmapTask.order_index.asc(), RoadmapTask.created_at.asc()).all()

@router.get("/summary", response_model=RoadmapSummaryResponse)
def get_roadmap_summary(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status in ("Finished", "Completed"))
    overall_progress = int((completed / total) * 100) if total > 0 else 0

    m30_tasks = [t for t in tasks if "30" in t.timeline]
    m30_total = len(m30_tasks)
    m30_comp = sum(1 for t in m30_tasks if t.status in ("Finished", "Completed"))
    m30_prog = int((m30_comp / m30_total) * 100) if m30_total > 0 else 0

    m60_tasks = [t for t in tasks if "60" in t.timeline]
    m60_total = len(m60_tasks)
    m60_comp = sum(1 for t in m60_tasks if t.status in ("Finished", "Completed"))
    m60_prog = int((m60_comp / m60_total) * 100) if m60_total > 0 else 0

    m90_tasks = [t for t in tasks if "90" in t.timeline]
    m90_total = len(m90_tasks)
    m90_comp = sum(1 for t in m90_tasks if t.status in ("Finished", "Completed"))
    m90_prog = int((m90_comp / m90_total) * 100) if m90_total > 0 else 0

    return RoadmapSummaryResponse(
        milestone_30_progress=m30_prog,
        milestone_30_completed=m30_comp,
        milestone_30_total=m30_total,
        milestone_60_progress=m60_prog,
        milestone_60_completed=m60_comp,
        milestone_60_total=m60_total,
        milestone_90_progress=m90_prog,
        milestone_90_completed=m90_comp,
        milestone_90_total=m90_total,
        total_tasks=total,
        completed_tasks=completed,
        overall_progress=overall_progress
    )

from app.services.task_graph_validator import (
    get_project_task_lock,
    lock_project_for_task_mutation,
    project_first_lock,
    allocate_next_task_code,
    validate_candidate_task_graph,
    TaskGraphNode,
    get_authoritative_project_tasks
)
from sqlalchemy.orm.attributes import flag_modified

VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
VALID_STATUSES = {"Pending", "In Progress", "Ongoing", "Finished", "Completed"}


def _build_and_validate_candidate_graph(
    db: Session,
    project_id: str,
    target_task_id: Optional[str],
    candidate_task_code: str,
    candidate_start_date: str,
    candidate_end_date: str,
    candidate_dependencies: List[str],
    rewritten_dependents: Optional[dict] = None
) -> None:
    """Construct full candidate task graph for the project and validate atomically."""
    all_tasks = get_authoritative_project_tasks(db, project_id)
    nodes: List[TaskGraphNode] = []
    found_target = False

    for t in all_tasks:
        if t.id == target_task_id:
            found_target = True
            nodes.append(TaskGraphNode(
                task_code=candidate_task_code,
                start_date=candidate_start_date,
                end_date=candidate_end_date,
                dependencies=candidate_dependencies,
                task_id=t.id
            ))
        else:
            deps = rewritten_dependents.get(t.id, t.dependencies or []) if rewritten_dependents else (t.dependencies or [])
            nodes.append(TaskGraphNode(
                task_code=t.task_code,
                start_date=t.start_date,
                end_date=t.end_date,
                dependencies=deps,
                task_id=t.id
            ))

    if not found_target and target_task_id is None:
        nodes.append(TaskGraphNode(
            task_code=candidate_task_code,
            start_date=candidate_start_date,
            end_date=candidate_end_date,
            dependencies=candidate_dependencies
        ))

    validate_candidate_task_graph(nodes, project_id=project_id)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_task(
    req: TaskCreateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    with project_first_lock(db, project.id):

        # 1. Monotonic automatic code allocation if not explicitly specified
        raw_code = req.task_code.strip() if req.task_code else None
        if not raw_code:
            task_code = allocate_next_task_code(db, project.id)
        else:
            task_code = raw_code
            # Explicit duplicate code check
            dup = db.query(RoadmapTask).filter(
                RoadmapTask.project_id == project.id,
                RoadmapTask.task_code == task_code
            ).first()
            if dup:
                raise HTTPException(
                    status_code=400,
                    detail=f"Task code '{task_code}' already exists in this project."
                )

        # 2. Validate priority & status
        if req.priority and req.priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{req.priority}'. Allowed: {', '.join(VALID_PRIORITIES)}"
            )
        raw_status = req.status or "Pending"
        if raw_status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{req.status}'. Allowed: Pending, In Progress, Finished"
            )
        status_val = "In Progress" if raw_status in ("In Progress", "Ongoing") else raw_status

        # 3. Validate entire candidate graph: dates, missing refs, cycles, and prerequisite order
        _build_and_validate_candidate_graph(
            db=db,
            project_id=project.id,
            target_task_id=None,
            candidate_task_code=task_code,
            candidate_start_date=req.start_date,
            candidate_end_date=req.end_date,
            candidate_dependencies=req.dependencies or []
        )

        task = RoadmapTask(
            project_id=project.id,
            task_code=task_code,
            phase=req.phase,
            title=req.title,
            description=req.description,
            timeline=req.timeline,
            start_date=req.start_date,
            end_date=req.end_date,
            priority=req.priority,
            status=status_val,
            dependencies=req.dependencies or [],
            deliverables=req.deliverables,
            effort=req.effort,
            assigned_to=req.assigned_to or "Unassigned",
            assigned_role=req.assigned_role,
            department=req.department,
            steps=req.steps or [],
            is_overloaded=req.is_overloaded or False,
            is_ai_generated=False
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task


@router.put("/{task_id}", response_model=TaskResponse, dependencies=[Depends(verify_csrf)])
@router.patch("/{task_id}", response_model=TaskResponse, dependencies=[Depends(verify_csrf)])
def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    with project_first_lock(db, project.id):
        all_tasks = get_authoritative_project_tasks(db, project.id)
        task = next((t for t in all_tasks if t.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        old_task_code = task.task_code
        new_task_code = (req.task_code.strip() if req.task_code else None) or old_task_code
        is_rename = (new_task_code != old_task_code)

        if is_rename:
            dup = next((t for t in all_tasks if t.task_code == new_task_code and t.id != task_id), None)
            if dup:
                raise HTTPException(
                    status_code=400,
                    detail=f"Task code '{new_task_code}' already exists in this project."
                )

        new_start = req.start_date or task.start_date
        new_end = req.end_date or task.end_date

        if req.priority:
            if req.priority not in VALID_PRIORITIES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid priority '{req.priority}'. Allowed: {', '.join(VALID_PRIORITIES)}"
                )

        if req.status:
            if req.status not in VALID_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{req.status}'. Allowed: Pending, In Progress, Finished"
                )

        new_deps = req.dependencies if req.dependencies is not None else (task.dependencies or [])

        # Rewrite incoming dependencies for all tasks depending on old_task_code
        rewritten_dependents: dict = {}
        dependent_tasks: List[RoadmapTask] = []

        if is_rename:
            for t in all_tasks:
                if t.id != task.id and old_task_code in (t.dependencies or []):
                    rewritten = [new_task_code if d == old_task_code else d for d in (t.dependencies or [])]
                    rewritten_dependents[t.id] = rewritten
                    dependent_tasks.append(t)

        # Atomic candidate graph validation across the complete project graph
        _build_and_validate_candidate_graph(
            db=db,
            project_id=project.id,
            target_task_id=task.id,
            candidate_task_code=new_task_code,
            candidate_start_date=new_start,
            candidate_end_date=new_end,
            candidate_dependencies=new_deps,
            rewritten_dependents=rewritten_dependents
        )

        # Apply validated mutations
        task.task_code = new_task_code
        task.start_date = new_start
        task.end_date = new_end
        task.dependencies = new_deps

        if req.priority:
            task.priority = req.priority
        if req.status:
            task.status = "In Progress" if req.status in ("In Progress", "Ongoing") else req.status

        if req.phase is not None:
            task.phase = req.phase
        if req.title is not None:
            task.title = req.title
        if req.description is not None:
            task.description = req.description
        if req.timeline is not None:
            task.timeline = req.timeline
        if req.deliverables is not None:
            task.deliverables = req.deliverables
        if req.effort is not None:
            task.effort = req.effort
        if "assigned_to" in req.model_fields_set:
            task.assigned_to = req.assigned_to or "Unassigned"
        if "assigned_role" in req.model_fields_set:
            task.assigned_role = req.assigned_role
        if "department" in req.model_fields_set:
            task.department = req.department
        if "steps" in req.model_fields_set and req.steps is not None:
            task.steps = req.steps
        if req.is_overloaded is not None:
            task.is_overloaded = req.is_overloaded

        # Apply rewritten dependencies to incoming dependents atomically
        for dep_t in dependent_tasks:
            dep_t.dependencies = rewritten_dependents[dep_t.id]
            flag_modified(dep_t, "dependencies")

        db.commit()
        db.refresh(task)
        return task


@router.delete("/{task_id}", dependencies=[Depends(verify_csrf)])
def delete_task(
    task_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    with project_first_lock(db, project.id):
        all_tasks = get_authoritative_project_tasks(db, project.id)
        task = next((t for t in all_tasks if t.id == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Dependency safety check: prevent deleting if other tasks depend on this task's code
        dependents = [d for d in all_tasks if d.id != task.id]
        blocking = [d.task_code for d in dependents if task.task_code in (d.dependencies or [])]
        if blocking:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete task {task.task_code}: tasks {', '.join(blocking)} depend on it. Please update their dependencies first."
            )

        db.delete(task)
        db.commit()
        return {"message": f"Task {task.task_code} deleted successfully"}
