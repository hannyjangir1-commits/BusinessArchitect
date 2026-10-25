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
