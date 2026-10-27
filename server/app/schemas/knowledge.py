from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

KnowledgeItemType = Literal["fact", "assumption", "evidence", "decision", "experiment", "open_question"]
EpistemicStatusType = Literal["user_supplied", "hypothesis", "evidence_supported", "unknown", "not_applicable"]
KnowledgeStatusType = Literal["draft", "active", "validated", "invalidated", "resolved"]
RelationshipType = Literal["supports", "tests", "contradicts", "derives_from", "blocks"]

class KnowledgeItemBase(BaseModel):
    item_type: KnowledgeItemType = Field(..., description="fact, assumption, evidence, decision, experiment, open_question")
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    status: KnowledgeStatusType = Field(default="active", description="draft, active, validated, invalidated, resolved")
    epistemic_status: EpistemicStatusType = Field(default="hypothesis", description="user_supplied, hypothesis, evidence_supported, unknown, not_applicable")
    source_reference: Optional[str] = Field(None, max_length=1000)
    linked_module: Optional[str] = Field(None, max_length=64)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

class KnowledgeItemCreate(KnowledgeItemBase):
    pass

class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    content: Optional[str] = Field(None, min_length=1)
    status: Optional[KnowledgeStatusType] = None
    epistemic_status: Optional[EpistemicStatusType] = None
    source_reference: Optional[str] = Field(None, max_length=1000)
    linked_module: Optional[str] = Field(None, max_length=64)
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
    source_id: str = Field(..., min_length=1, max_length=64)
    target_id: str = Field(..., min_length=1, max_length=64)
    relationship: RelationshipType = Field(..., description="supports, tests, contradicts, derives_from, blocks")
