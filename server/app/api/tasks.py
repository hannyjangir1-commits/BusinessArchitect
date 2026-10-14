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
        status=req.status,
        dependencies=req.dependencies,
        deliverables=req.deliverables,
        effort=req.effort
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.put("/{task_id}", response_model=TaskResponse, dependencies=[Depends(verify_csrf)])
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

    if req.task_code is not None:
        task.task_code = req.task_code
    if req.phase is not None:
        task.phase = req.phase
    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.timeline is not None:
        task.timeline = req.timeline
    if req.start_date is not None:
        task.start_date = req.start_date
    if req.end_date is not None:
        task.end_date = req.end_date
    if req.priority is not None:
        task.priority = req.priority
    if req.status is not None:
        task.status = req.status
    if req.dependencies is not None:
        task.dependencies = req.dependencies
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
