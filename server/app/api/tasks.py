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

from datetime import datetime

VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
VALID_STATUSES = {"Pending", "In Progress", "Ongoing", "Finished", "Completed"}

def _validate_dates(start_date: str, end_date: str):
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD."
        )
    if e < s:
        raise HTTPException(
            status_code=400,
            detail=f"End date ({end_date}) cannot be earlier than start date ({start_date})."
        )

def _validate_task_dependencies(
    db: Session,
    project_id: str,
    task_code: str,
    dependencies: List[str],
    current_task_id: Optional[str] = None
):
    if task_code in dependencies:
        raise HTTPException(
            status_code=400,
            detail=f"Self-dependency error: task {task_code} cannot depend on itself."
        )

    # Get all project tasks
    all_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project_id).all()
    code_set = {t.task_code for t in all_tasks if t.id != current_task_id}
    code_set.add(task_code)

    # Check non-existent dependencies
    for dep in dependencies:
        if dep not in code_set:
            raise HTTPException(
                status_code=400,
                detail=f"Dependency reference '{dep}' does not exist in this project."
            )

    # Build dependency graph to detect circular chains
    graph: dict = {}
    for t in all_tasks:
        if t.id == current_task_id:
            graph[task_code] = dependencies
        else:
            graph[t.task_code] = t.dependencies or []
    if task_code not in graph:
        graph[task_code] = dependencies

    visited: dict = {}  # 0 = unvisited, 1 = visiting, 2 = visited
    cycle_chain: list = []

    def dfs(node: str, path: list) -> bool:
        visited[node] = 1
        for neighbor in graph.get(node, []):
            if visited.get(neighbor) == 1:
                cycle_chain.extend(path + [node, neighbor])
                return True
            if visited.get(neighbor, 0) == 0:
                if dfs(neighbor, path + [node]):
                    return True
        visited[node] = 2
        return False

    for node in graph:
        if visited.get(node, 0) == 0:
            if dfs(node, []):
                raise HTTPException(
                    status_code=400,
                    detail=f"Circular dependency detected: {' -> '.join(cycle_chain)}"
                )

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_task(
    req: TaskCreateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    # Auto-generate task code if not provided
    task_code = req.task_code
    if not task_code:
        count = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).count()
        task_code = f"TSK-{str(count + 1).zfill(2)}"
    else:
        # Check duplicate task code in the same project
        dup = db.query(RoadmapTask).filter(
            RoadmapTask.project_id == project.id,
            RoadmapTask.task_code == task_code
        ).first()
        if dup:
            raise HTTPException(
                status_code=400,
                detail=f"Task code '{task_code}' already exists in this project."
            )

    # Validate priority & status
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

    # Validate dates
    _validate_dates(req.start_date, req.end_date)

    # Validate dependencies & cycle detection
    _validate_task_dependencies(db, project.id, task_code, req.dependencies or [])

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
    task = db.query(RoadmapTask).filter(
        RoadmapTask.id == task_id,
        RoadmapTask.project_id == project.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_task_code = req.task_code or task.task_code
    if req.task_code and req.task_code != task.task_code:
        dup = db.query(RoadmapTask).filter(
            RoadmapTask.project_id == project.id,
            RoadmapTask.task_code == req.task_code,
            RoadmapTask.id != task_id
        ).first()
        if dup:
            raise HTTPException(
                status_code=400,
                detail=f"Task code '{req.task_code}' already exists in this project."
            )

    new_start = req.start_date or task.start_date
    new_end = req.end_date or task.end_date
    _validate_dates(new_start, new_end)

    if req.priority:
        if req.priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority '{req.priority}'. Allowed: {', '.join(VALID_PRIORITIES)}"
            )
        task.priority = req.priority

    if req.status:
        if req.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{req.status}'. Allowed: Pending, In Progress, Finished"
            )
        status_val = "In Progress" if req.status in ("In Progress", "Ongoing") else req.status
        task.status = status_val

    new_deps = req.dependencies if req.dependencies is not None else (task.dependencies or [])
    _validate_task_dependencies(db, project.id, new_task_code, new_deps, current_task_id=task.id)

    task.task_code = new_task_code
    task.start_date = new_start
    task.end_date = new_end
    task.dependencies = new_deps

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

    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}", dependencies=[Depends(verify_csrf)])
def delete_task(
    task_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    task = db.query(RoadmapTask).filter(
        RoadmapTask.id == task_id,
        RoadmapTask.project_id == project.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Dependency safety check: prevent deleting if other tasks depend on this task's code
    dependents = db.query(RoadmapTask).filter(
        RoadmapTask.project_id == project.id,
        RoadmapTask.id != task.id
    ).all()

    blocking = [d.task_code for d in dependents if task.task_code in (d.dependencies or [])]
    if blocking:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete task {task.task_code}: tasks {', '.join(blocking)} depend on it. Please update their dependencies first."
        )

    db.delete(task)
    db.commit()
    return {"message": f"Task {task.task_code} deleted successfully"}
