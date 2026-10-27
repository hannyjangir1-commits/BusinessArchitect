from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    client_msg_id: Optional[str] = Field(None, max_length=100, description="Optional idempotent client-generated message identifier")

class CopilotMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CopilotHistoryPageResponse(BaseModel):
    messages: List[CopilotMessageResponse]
    has_more: bool
    before_cursor: Optional[str] = None
    total_count: int

class CopilotSendResponse(BaseModel):
    id: str
    role: str = "assistant"
    content: str
    created_at: datetime
    user_message: CopilotMessageResponse
    assistant_message: Optional[CopilotMessageResponse] = None
    operation_status: str = "completed"
    client_msg_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CopilotOperationStatusResponse(BaseModel):
    client_msg_id: str
    status: str
    user_message: Optional[CopilotMessageResponse] = None
    assistant_message: Optional[CopilotMessageResponse] = None
    error_detail: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CopilotProposalRequest(BaseModel):
    target_module: str = Field(..., pattern="^(bmc|lean_canvas|value_prop|market_research|tech_stack|idea_validator|detailed_roadmap|execution_roadmap)$")
    instruction: str = Field(..., min_length=3, max_length=4000)

class CopilotProposalResponse(BaseModel):
    id: Optional[str] = None
    target_module: str
    summary: str
    proposed_diff: dict
    affected_assumptions: List[str] = []
    affected_tasks: List[str] = []
    requires_confirmation: bool = True
    proposed_content: dict
    status: Optional[str] = "pending"
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CopilotApplyProposalResponse(BaseModel):
    success: bool
    message: str
    target_module: str
    proposal_id: str
    version_id: str
    version_number: int
    version_name: str
    data: dict

    model_config = ConfigDict(from_attributes=True)
