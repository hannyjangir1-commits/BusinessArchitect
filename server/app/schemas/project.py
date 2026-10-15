from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    stage: str = Field(default="Idea / MVP")  # "Idea / MVP", "Post-launch", "Growth"
    description: Optional[str] = None
    industry: Optional[str] = None
    target_customers: Optional[str] = None
    goals: Optional[str] = None
    business_context: Optional[str] = None
    budget: Optional[str] = None
    existing_stack: Optional[Dict[str, List[str]]] = Field(default_factory=dict)

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    target_customers: Optional[str] = None
    goals: Optional[str] = None
    business_context: Optional[str] = None
    budget: Optional[str] = None
    existing_stack: Optional[Dict[str, List[str]]] = None
    active_module: Optional[str] = None
    create_copy: Optional[bool] = False  # Option B: Create separate project vs Option A: Replace

class ProjectResponse(BaseModel):
    id: str
    name: str
    stage: str
    description: Optional[str] = None
    industry: Optional[str] = None
    target_customers: Optional[str] = None
    goals: Optional[str] = None
    business_context: Optional[str] = None
    budget: Optional[str] = None
    existing_stack: Dict[str, Any] = Field(default_factory=dict)
    active_module: str
    tasks_count: int = 0
    completed_tasks_count: int = 0
    progress_percentage: int = 0
    generated_modules: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ActiveModuleUpdateRequest(BaseModel):
    active_module: str

class BulkDeleteProjectsRequest(BaseModel):
    project_ids: List[str] = Field(..., min_length=1)

class BulkDeleteProjectsResponse(BaseModel):
    deleted_count: int
    deleted_ids: List[str]
    message: str
