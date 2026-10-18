from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class TaskCreateRequest(BaseModel):
    task_code: Optional[str] = None
    phase: str = Field(default="Planning & Research")
    title: str = Field(..., min_length=2, max_length=256)
    description: Optional[str] = None
    timeline: str = Field(default="30-day")  # 30-day, 60-day, 90-day
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    priority: str = Field(default="Medium")  # Critical, High, Medium, Low
    status: str = Field(default="Pending")   # Pending, In Progress, Finished
    dependencies: List[str] = Field(default_factory=list)
    deliverables: Optional[str] = None
    effort: Optional[str] = None
    assigned_to: Optional[str] = "Unassigned"
    assigned_role: Optional[str] = None
    department: Optional[str] = None
    steps: Optional[List[str]] = Field(default_factory=list)
    is_overloaded: Optional[bool] = False

class TaskUpdateRequest(BaseModel):
    task_code: Optional[str] = None
    phase: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    timeline: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    dependencies: Optional[List[str]] = None
    deliverables: Optional[str] = None
    effort: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_role: Optional[str] = None
    department: Optional[str] = None
    steps: Optional[List[str]] = None
    is_overloaded: Optional[bool] = None

class TaskResponse(BaseModel):
    id: str
    project_id: str
    task_code: str
    phase: str
    title: str
    description: Optional[str] = None
    timeline: str
    start_date: str
    end_date: str
    priority: str
    status: str
    dependencies: List[str] = []
    deliverables: Optional[str] = None
    effort: Optional[str] = None
    assigned_to: Optional[str] = "Unassigned"
    assigned_role: Optional[str] = None
    department: Optional[str] = None
    steps: Optional[List[str]] = Field(default_factory=list)
    is_overloaded: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoadmapSummaryResponse(BaseModel):
    milestone_30_progress: int
    milestone_30_completed: int
    milestone_30_total: int
    milestone_60_progress: int
    milestone_60_completed: int
    milestone_60_total: int
    milestone_90_progress: int
    milestone_90_completed: int
    milestone_90_total: int
    total_tasks: int
    completed_tasks: int
    overall_progress: int
