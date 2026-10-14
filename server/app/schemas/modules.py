from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- BMC Schemas ---
class BMCData(BaseModel):
    tagline: Optional[str] = "AI-Driven Enterprise Solution"
    customer_segments: List[str] = Field(..., min_length=1)
    value_propositions: List[str] = Field(..., min_length=1)
    channels: List[str] = Field(..., min_length=1)
    customer_relationships: List[str] = Field(..., min_length=1)
    revenue_streams: List[str] = Field(..., min_length=1)
    key_resources: List[str] = Field(..., min_length=1)
    key_activities: List[str] = Field(..., min_length=1)
    key_partnerships: List[str] = Field(..., min_length=1)
    cost_structure: List[str] = Field(..., min_length=1)

# --- Tech Stack Schemas ---
class TechItem(BaseModel):
    technology: str
    category: str  # Frontend, Backend, Database, Cloud/Hosting, Storage, Security, DevOps, Services
    purpose: str
    suitability: str
    trade_offs: Optional[str] = None
    migration_risk: Optional[str] = None

class TechStackData(BaseModel):
    summary: str
    architecture_pattern: str  # e.g., Microservices, Event-Driven, Modular Monolith
    recommendations: List[TechItem]

# --- Idea Validator Schemas ---
class ValidationRisk(BaseModel):
    risk: str
    severity: str  # High, Medium, Low
    mitigation: str

class ValidationExperiment(BaseModel):
    experiment: str
    metric: str
    target_criteria: str

class IdeaValidatorData(BaseModel):
    overall_viability_score: int = Field(default=85, ge=0, le=100)
    problem_clarity: str
    customer_fit: str
    value_proposition: str
    market_assumptions: List[str]
    differentiation: str
    feasibility: str
    risks: List[ValidationRisk]
    validation_experiments: List[ValidationExperiment]
    suggested_next_actions: List[str]

# --- Market Research Schemas ---
class CompetitorProfile(BaseModel):
    name: str
    strengths: List[str]
    weaknesses: List[str]
    pricing_model: str
    market_share_estimate: str

class MarketResearchData(BaseModel):
    provenance_note: str = "AI-grounded analytical market assessment based on current business context."
    target_market_size: str
    customer_needs: List[str]
    competitor_profiles: List[CompetitorProfile]
    competitive_positioning: str
    differentiation_factors: List[str]
    opportunities: List[str]
    threats: List[str]
    research_gaps: List[str]

# --- Versioning Schemas ---
class VersionItemResponse(BaseModel):
    id: str
    version_number: int
    version_name: str
    change_summary: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModuleDetailResponse(BaseModel):
    module_type: str
    active_version_id: Optional[str] = None
    active_version_name: Optional[str] = None
    active_version_number: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    versions: List[VersionItemResponse] = []

class VersionRenameRequest(BaseModel):
    version_name: str = Field(..., min_length=1, max_length=128)

class VersionConflictResolveRequest(BaseModel):
    replace_version_id: str  # The existing version to remove/replace to keep <= 5 versions
    new_data: Dict[str, Any]
    new_version_name: Optional[str] = None
    change_summary: Optional[str] = None

class SectionModifyRequest(BaseModel):
    instruction: str = Field(..., min_length=2)
