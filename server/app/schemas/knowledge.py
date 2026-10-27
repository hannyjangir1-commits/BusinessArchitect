from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class KnowledgeItemBase(BaseModel):
    item_type: str = Field(..., description="fact, assumption, evidence, decision, experiment, open_question")
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    status: str = Field(default="active", max_length=32)
    epistemic_status: str = Field(default="hypothesis", description="user_supplied, hypothesis, evidence_supported, unknown, not_applicable")
    source_reference: Optional[str] = None
    linked_module: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

class KnowledgeItemCreate(KnowledgeItemBase):
    pass

class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    content: Optional[str] = None
    status: Optional[str] = None
    epistemic_status: Optional[str] = None
    source_reference: Optional[str] = None
    linked_module: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class KnowledgeLinkResponse(BaseModel):
    id: str
    project_id: str
    source_id: str
    target_id: str
    relationship: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class KnowledgeItemResponse(KnowledgeItemBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
    outgoing_links: List[KnowledgeLinkResponse] = Field(default_factory=list)
    incoming_links: List[KnowledgeLinkResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class KnowledgeLinkCreate(BaseModel):
    source_id: str
    target_id: str
    relationship: str = Field(..., description="supports, tests, contradicts, derives_from, blocks")
