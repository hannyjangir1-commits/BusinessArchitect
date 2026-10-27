from typing import List, Optional, Dict, Any, Literal, Union
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

# --- Generation Brief Schemas (Two-Stage Pipeline) ---
class GenerationBrief(BaseModel):
    venture_summary: str = "Venture strategic synthesis"
    applicable_focus: List[str] = Field(default_factory=list)
    is_technical_project: bool = True
    technical_depth: str = "standard_digital"  # deep_technical, standard_digital, non_technical_business
    stage_considerations: str = "Stage-aligned development milestones"
    budget_constraints: Optional[str] = None
    timeline_constraints: Optional[str] = None
    team_capacity_considerations: Optional[str] = None
    key_assumptions: List[str] = Field(default_factory=list)
    information_gaps: List[str] = Field(default_factory=list)
    feasibility_flags: List[str] = Field(default_factory=list)
    custom_instructions: Optional[str] = None

# --- BMC & Business Model Framework Schemas ---
class CanvasItemState(BaseModel):
    text: str
    state: str = "hypothesis"  # user_supplied, hypothesis, evidence_supported, unknown, not_applicable
    reason: Optional[str] = None
    evidence_ref: Optional[str] = None
    assumption_id: Optional[str] = None

class BusinessModelPlanningRequest(BaseModel):
    framework_type: Literal["standard_bmc", "lean_canvas", "value_prop_canvas"] = "standard_bmc"
    target_outcome: Optional[str] = Field(default="", max_length=1000)
    notes: Optional[str] = Field(default="", max_length=2000)

class BMCData(BaseModel):
    framework_type: str = "standard_bmc"
    tagline: Optional[str] = "A practical solution for its target customers"
    customer_segments: List[str] = Field(min_length=1)
    value_propositions: List[str] = Field(min_length=1)
    channels: List[str] = Field(default_factory=list)
    customer_relationships: List[str] = Field(default_factory=list)
    revenue_streams: List[str] = Field(default_factory=list)
    key_resources: List[str] = Field(default_factory=list)
    key_activities: List[str] = Field(default_factory=list)
    key_partnerships: List[str] = Field(default_factory=list)
    cost_structure: List[str] = Field(default_factory=list)
    actionable_guidance: Optional[Dict[str, str]] = Field(default_factory=dict)
    assumptions: Optional[List[str]] = Field(default_factory=list)
    item_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class LeanCanvasData(BaseModel):
    framework_type: str = "lean_canvas"
    tagline: Optional[str] = None
    problem: List[str] = Field(default_factory=list)
    existing_alternatives: List[str] = Field(default_factory=list)
    solution: List[str] = Field(default_factory=list)
    key_metrics: List[str] = Field(default_factory=list)
    unique_value_proposition: List[str] = Field(default_factory=list)
    high_level_concept: Optional[str] = None
    unfair_advantage: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)
    customer_segments: List[str] = Field(default_factory=list)
    early_adopters: List[str] = Field(default_factory=list)
    cost_structure: List[str] = Field(default_factory=list)
    revenue_streams: List[str] = Field(default_factory=list)
    actionable_guidance: Optional[Dict[str, str]] = Field(default_factory=dict)
    assumptions: Optional[List[str]] = Field(default_factory=list)
    item_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ValuePropositionCanvasData(BaseModel):
    framework_type: str = "value_prop_canvas"
    customer_jobs: List[str] = Field(default_factory=list)
    customer_pains: List[str] = Field(default_factory=list)
    customer_gains: List[str] = Field(default_factory=list)
    pains: List[str] = Field(default_factory=list)
    gains: List[str] = Field(default_factory=list)
    products_and_services: List[str] = Field(default_factory=list)
    pain_relievers: List[str] = Field(default_factory=list)
    gain_creators: List[str] = Field(default_factory=list)
    fit_assessment: Optional[str] = None
    assumptions: Optional[List[str]] = Field(default_factory=list)
    item_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_pains_gains(cls, data: Any) -> Any:
        if isinstance(data, dict):
            pains = data.get("pains") or []
            cust_pains = data.get("customer_pains") or []
            if pains and not cust_pains:
                data["customer_pains"] = list(pains)
            elif cust_pains and not pains:
                data["pains"] = list(cust_pains)
            gains = data.get("gains") or []
            cust_gains = data.get("customer_gains") or []
            if gains and not cust_gains:
                data["customer_gains"] = list(gains)
            elif cust_gains and not gains:
                data["gains"] = list(cust_gains)
        return data

# --- Tech Stack Schemas ---
class TechItem(BaseModel):
    technology: str
    category: str  # Frontend, Backend, Database, Cloud/Hosting, Storage, Security, DevOps, Services, Business Operations, POS & Payments, etc.
    purpose: str
    suitability: str
    trade_offs: Optional[str] = None
    migration_risk: Optional[str] = None
    role_description: Optional[str] = None
    implementation_guidance: Optional[str] = None
    estimated_cost_tier: Optional[str] = "Low / Free Tier"  # Low, Moderate, High
    alternatives: Optional[List[str]] = Field(default_factory=list)
    revisit_triggers: Optional[List[str]] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.technology

class TechStackData(BaseModel):
    summary: str
    architecture_pattern: str  # e.g., Microservices, Event-Driven, Modular Monolith, Commercial Off-The-Shelf (COTS)
    recommendations: List[TechItem]
    existing_stack_evaluation: Optional[Dict[str, Any]] = Field(default_factory=dict)
    assumptions: Optional[List[str]] = Field(default_factory=list)
    planning_inputs: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TechStackPlanningRequest(BaseModel):
    solution_type: str = Field(default="", max_length=120)
    preferred_languages: List[str] = Field(default_factory=list, max_length=12)
    preferred_frameworks: List[str] = Field(default_factory=list, max_length=20)
    current_stack: str = Field(default="", max_length=2000)
    target_platforms: List[str] = Field(default_factory=list, max_length=10)
    deployment_preference: str = Field(default="", max_length=200)
    database_preference: str = Field(default="", max_length=200)
    expected_scale: str = Field(default="", max_length=200)
    data_sensitivity: str = Field(default="", max_length=200)
    compliance_requirements: List[str] = Field(default_factory=list, max_length=12)
    required_integrations: List[str] = Field(default_factory=list, max_length=20)
    budget_constraint: str = Field(default="", max_length=500)
    team_experience: str = Field(default="", max_length=1000)
    must_use: List[str] = Field(default_factory=list, max_length=20)
    avoid: List[str] = Field(default_factory=list, max_length=20)
    constraints: str = Field(default="", max_length=2000)

# --- Idea Validator Schemas ---
class ValidationRisk(BaseModel):
    risk: str
    severity: str  # High, Medium, Low
    mitigation: str

class ValidationExperiment(BaseModel):
    experiment: str
    metric: str
    target_criteria: str
    hypothesis: Optional[str] = None
    target_participants: Optional[str] = None
    method: Optional[str] = None
    sample_size: Optional[str] = None
    cost_estimate: Optional[str] = None
    success_threshold: Optional[str] = None
    failure_interpretation: Optional[str] = None
    evidence_to_collect: Optional[str] = None
    next_decision: Optional[str] = None

class ResearchSource(BaseModel):
    title: str
    url: str

class IdeaValidatorData(BaseModel):
    overall_viability_score: Optional[int] = Field(default=None, ge=0, le=100)
    problem_clarity: str
    customer_fit: str
    value_proposition: str
    market_assumptions: List[str]
    differentiation: str
    feasibility: str
    risks: List[ValidationRisk]
    validation_experiments: List[ValidationExperiment]
    suggested_next_actions: List[str]
    critical_assumptions: List[str] = Field(default_factory=list)
    available_evidence: List[str] = Field(default_factory=list)
    biggest_uncertainty: Optional[str] = None
    recommended_decision: Optional[str] = None  # continue, revise, pause, investigate
    budget_feasibility: Optional[str] = None
    scope_reduction_alternatives: Optional[List[str]] = Field(default_factory=list)
    score_factors: Optional[Dict[str, int]] = Field(default_factory=dict)
    evidence_note: Optional[str] = None
    source_references: List[ResearchSource] = Field(default_factory=list)

    @property
    def score(self) -> Optional[int]:
        return self.overall_viability_score

    @property
    def summary(self) -> str:
        return f"{self.problem_clarity} {self.feasibility}"

# --- Market Research Schemas ---
class CompetitorProfile(BaseModel):
    name: str
    strengths: List[str]
    weaknesses: List[str]
    pricing_model: str
    market_share_estimate: str
    sources: Optional[List[str]] = Field(default_factory=list)
    as_of_date: Optional[str] = None
    is_direct_competitor: Optional[bool] = True

class MarketResearchData(BaseModel):
    provenance_note: str = "Context-based market assessment; verify assumptions against current evidence."
    target_market_size: str
    customer_needs: List[str]
    competitor_profiles: List[CompetitorProfile]
    competitive_positioning: str
    differentiation_factors: List[str]
    opportunities: List[str]
    threats: List[str]
    research_gaps: List[str]
    late_entry_differentiation: Optional[str] = None
    budget_fit_analysis: Optional[str] = None
    source_references: List[ResearchSource] = Field(default_factory=list)

# --- Roadmap Schemas ---
class RoadmapPhase(BaseModel):
    name: str
    color: Optional[str] = "#10b981"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class RoadmapTaskItem(BaseModel):
    task_code: Optional[str] = None
    phase: str
    title: str
    description: Optional[str] = None
    timeline: Optional[str] = "30-day"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    priority: Optional[str] = "Medium"
    status: Optional[str] = "Pending"
    dependencies: Optional[List[str]] = []
    deliverables: Optional[str] = None
    effort: Optional[str] = None
    assigned_to: Optional[str] = "Unassigned"
    assigned_role: Optional[str] = None
    department: Optional[str] = None
    steps: Optional[List[str]] = Field(default_factory=list)
    is_overloaded: Optional[bool] = False

class RoadmapFeasibilityEvaluation(BaseModel):
    is_realistic: bool = True
    feasibility_issues: List[str] = Field(default_factory=list)
    recommended_alternatives: List[str] = Field(default_factory=list)
    capacity_summary: Optional[str] = None

class ExecutionRoadmapData(BaseModel):
    phases: Optional[List[RoadmapPhase]] = []
    tasks: List[RoadmapTaskItem] = Field(default_factory=list, max_length=30)
    feasibility_evaluation: Optional[RoadmapFeasibilityEvaluation] = None
    assumptions: Optional[List[str]] = Field(default_factory=list)

DetailedRoadmapData = ExecutionRoadmapData


class RoadmapChecklistItem(BaseModel):
    item: str = Field(..., min_length=1, max_length=180)
    status: Literal["Not started", "In progress", "Completed", "Not applicable"]

class TeamMemberInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    hours_per_week: Optional[int] = 40

class RoadmapPlanningRequest(BaseModel):
    start_date: date = Field(default_factory=date.today)
    horizon_weeks: int = Field(default=12, ge=1, le=104)
    checklist: List[RoadmapChecklistItem] = Field(default_factory=list, max_length=30)
    completed_work: str = Field(default="", max_length=2000)
    in_progress_work: str = Field(default="", max_length=2000)
    team_capacity: str = Field(default="", max_length=500)
    constraints: str = Field(default="", max_length=2000)
    target_outcome: str = Field(default="", max_length=1000)
    custom_items: List[str] = Field(default_factory=list, max_length=20)
    is_solo_developer: bool = False
    organization_size: Optional[str] = None
    departments: List[str] = Field(default_factory=list)
    team_members: List[TeamMemberInput] = Field(default_factory=list)
    reduce_mvp_scope: bool = False

# --- Versioning Schemas ---
class VersionItemResponse(BaseModel):
    id: str
    version_number: int
    version_name: str
    framework_type: Optional[str] = "standard_bmc"
    change_summary: Optional[str] = None
    is_active: bool
    created_at: datetime

    @field_validator("framework_type", mode="before")
    @classmethod
    def normalize_framework(cls, v: Optional[str]) -> Optional[str]:
        if v == "standard":
            return "standard_bmc"
        return v or "standard_bmc"

    model_config = ConfigDict(from_attributes=True)

class ModuleDetailResponse(BaseModel):
    module_type: str
    framework_type: Optional[str] = "standard_bmc"
    active_version_id: Optional[str] = None
    active_version_name: Optional[str] = None
    active_version_number: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    versions: List[VersionItemResponse] = []
    is_stale: bool = False
    stale_reason: Optional[str] = None
    stale_source_module: Optional[str] = None
    context_metadata: Optional[Dict[str, Any]] = None

    @field_validator("framework_type", mode="before")
    @classmethod
    def normalize_framework(cls, v: Optional[str]) -> Optional[str]:
        if v == "standard":
            return "standard_bmc"
        return v or "standard_bmc"

class VersionRenameRequest(BaseModel):
    version_name: str = Field(..., min_length=1, max_length=128)


class VersionConflictResolveRequest(BaseModel):
    replace_version_id: str  # The existing version to remove/replace to keep <= 5 versions
    new_data: Optional[Dict[str, Any]] = None
    instruction: Optional[str] = Field(None, max_length=4000)
    new_version_name: Optional[str] = None
    change_summary: Optional[str] = None

class SectionModifyRequest(BaseModel):
    instruction: str = Field(..., min_length=2, max_length=4000)
