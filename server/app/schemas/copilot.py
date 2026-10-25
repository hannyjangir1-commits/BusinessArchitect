from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

class CopilotMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
