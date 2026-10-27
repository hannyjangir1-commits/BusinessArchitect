import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON, UniqueConstraint, Index, text, false, or_, and_
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from app.db.base import Base

def gen_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("usr_"))
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=True)
    preferences = Column(JSON, default=dict, server_default=text("'{}'"), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="user", nullable=False)  # "user", "super_admin", "operations_admin", "support_admin", "security_admin", "auditor"
    is_suspended = Column(Boolean, default=False, nullable=False)
    suspended_at = Column(DateTime, nullable=True)
    suspension_reason = Column(Text, nullable=True)
    last_active_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor")

class SessionTokenComparator(Comparator):
    def __eq__(self, other):
        if isinstance(other, str) and other:
            from app.core.security import hash_session_token
            digest = hash_session_token(other)
            return or_(self.__clause_element__() == other, Session.token_digest == digest)
        return self.__clause_element__() == other

    def __ne__(self, other):
        if isinstance(other, str) and other:
            from app.core.security import hash_session_token
            digest = hash_session_token(other)
            return or_(
                Session.token_digest != digest,
                and_(Session.token_digest.is_(None), self.__clause_element__() != other)
            )
        return self.__clause_element__() != other

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("ses_"))
    _session_token = Column("session_token", String(128), unique=True, nullable=True, index=True)
    token_digest = Column(String(64), unique=True, nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="sessions")

    @hybrid_property
    def session_token(self):
        return self._session_token

    @session_token.setter
    def session_token(self, value):
        self._session_token = value
        if value and not self.token_digest:
            from app.core.security import hash_session_token
            self.token_digest = hash_session_token(value)

    @session_token.comparator
    def session_token(cls):
        return SessionTokenComparator(cls._session_token)

    def __init__(self, **kwargs):
        if "session_token" in kwargs and kwargs["session_token"] and not kwargs.get("token_digest"):
            from app.core.security import hash_session_token
            kwargs["token_digest"] = hash_session_token(kwargs["session_token"])
        super().__init__(**kwargs)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("prj_"))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    stage = Column(String(32), nullable=False, default="Idea")
    description = Column(Text, nullable=True)
    industry = Column(String(64), nullable=True)
    target_customers = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    business_context = Column(Text, nullable=True)
    budget = Column(String(64), nullable=True)
    existing_stack = Column(JSON, nullable=True, default=dict)
    active_module = Column(String(64), default="overview", nullable=False)  # Per-project navigation memory
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="projects")
    modules = relationship("ModuleContent", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("RoadmapTask", back_populates="project", cascade="all, delete-orphan")
    copilot_messages = relationship("CopilotMessage", back_populates="project", cascade="all, delete-orphan")
    knowledge_items = relationship("ProjectKnowledgeItem", back_populates="project", cascade="all, delete-orphan")
    financial_worksheet = relationship("FinancialWorksheet", back_populates="project", uselist=False, cascade="all, delete-orphan")

class ModuleContent(Base):
    __tablename__ = "module_contents"
    __table_args__ = (
        UniqueConstraint("project_id", "module_type", name="uq_module_contents_project_module"),
    )

    id = Column(String(36), primary_key=True, default=lambda: gen_id("mod_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    module_type = Column(String(64), nullable=False)  # bmc, tech_stack, idea_validator, market_research, execution_roadmap, overview
    framework_type = Column(String(64), default="standard", server_default="standard", nullable=False)  # standard_bmc, lean_canvas, value_prop_canvas, custom_canvas
    active_version_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="modules")
    versions = relationship("ModuleVersion", back_populates="module_content", cascade="all, delete-orphan")

class ModuleVersion(Base):
    __tablename__ = "module_versions"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("ver_"))
    module_content_id = Column(String(36), ForeignKey("module_contents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)  # 1 to 5
    version_name = Column(String(128), nullable=False)  # Editable display name: "BMC V1", "Subscription Pivot", etc.
    framework_type = Column(String(64), default="standard", server_default="standard", nullable=False)
    data = Column(JSON, nullable=False)
    change_summary = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    module_content = relationship("ModuleContent", back_populates="versions")

class RoadmapTask(Base):
    __tablename__ = "roadmap_tasks"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("tsk_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_code = Column(String(32), nullable=False)  # TSK-01, TSK-02
    phase = Column(String(64), nullable=False)  # Planning & Research, System Design, Development, Testing & Deployment, Launch & Monitor
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    timeline = Column(String(32), default="30-day", nullable=False)  # 30-day, 60-day, 90-day
    start_date = Column(String(32), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(32), nullable=False)    # YYYY-MM-DD
    priority = Column(String(32), default="Medium", nullable=False)  # Critical, High, Medium, Low
    status = Column(String(32), default="Pending", nullable=False)   # Pending, In Progress, Finished
    dependencies = Column(JSON, default=list, nullable=False)       # List of task_codes ["TSK-01"]
    deliverables = Column(Text, nullable=True)
    effort = Column(String(64), nullable=True)
    assigned_to = Column(String(128), default="Unassigned", server_default="Unassigned", nullable=False)
    assigned_role = Column(String(128), nullable=True)
    department = Column(String(128), nullable=True)
    steps = Column(JSON, default=list, server_default=text("'[]'"), nullable=False)
    is_overloaded = Column(Boolean, default=False, server_default=false(), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    is_ai_generated = Column(Boolean, default=False, nullable=False)

    # Roadmap.sh enhancements
    branch_type = Column(String(32), default="core", server_default="core", nullable=False)  # core, parallel, optional, alternative, learning
    parent_outcome = Column(String(128), nullable=True)
    definition_of_done = Column(Text, nullable=True)
    acceptance_criteria = Column(JSON, default=list, server_default=text("'[]'"), nullable=False)
    edge_type = Column(String(32), default="prerequisite", server_default="prerequisite", nullable=False)  # prerequisite, parent_group, optional_branch, alternative, related_info
    roadmap_mode = Column(String(32), default="execution", server_default="execution", nullable=False)  # execution, learning

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "task_code", name="uq_roadmap_tasks_project_task_code"),
    )

    project = relationship("Project", back_populates="tasks")

class ProjectKnowledgeItem(Base):
    __tablename__ = "project_knowledge_items"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("kno_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(32), nullable=False, index=True)  # fact, assumption, evidence, decision, experiment, open_question
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(32), default="active", server_default="active", nullable=False)  # draft, active, validated, invalidated, resolved
    epistemic_status = Column(String(32), default="hypothesis", server_default="hypothesis", nullable=False)  # user_supplied, hypothesis, evidence_supported, unknown, not_applicable
    source_reference = Column(Text, nullable=True)
    linked_module = Column(String(64), nullable=True)
    metadata_json = Column(JSON, default=dict, server_default=text("'{}'"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="knowledge_items")

class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("knl_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("project_knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("project_knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship = Column(String(32), nullable=False)  # supports, tests, contradicts, derives_from, blocks
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class FinancialWorksheet(Base):
    __tablename__ = "financial_worksheets"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("fin_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    currency = Column(String(8), default="USD", server_default="USD", nullable=False)
    startup_costs = Column(JSON, default=list, server_default=text("'[]'"), nullable=False)  # [{ category, item, amount, is_confirmed }]
    fixed_costs = Column(JSON, default=list, server_default=text("'[]'"), nullable=False)    # [{ category, item, monthly_amount, frequency }]
    variable_costs = Column(JSON, default=list, server_default=text("'[]'"), nullable=False) # [{ item, unit_cost, notes }]
    revenue_model = Column(JSON, default=dict, server_default=text("'{}'"), nullable=False)   # { model_type, price_per_unit, expected_volume_monthly }
    cash_available = Column(Float, default=0.0, server_default="0.0", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="financial_worksheet")

class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("msg_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="copilot_messages")

class CopilotOperation(Base):
    __tablename__ = "copilot_operations"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("cop_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_msg_id = Column(String(128), nullable=False)
    message_hash = Column(String(64), nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, completed, failed
    user_message_id = Column(String(36), ForeignKey("copilot_messages.id", ondelete="SET NULL"), nullable=True)
    assistant_message_id = Column(String(36), ForeignKey("copilot_messages.id", ondelete="SET NULL"), nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "client_msg_id", name="uq_copilot_operations_project_client_msg_id"),
    )

class AIOperation(Base):
    __tablename__ = "ai_operations"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("aio_"))
    request_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    module_type = Column(String(64), nullable=False, index=True)  # bmc, tech_stack, idea_validator, market_research, execution_roadmap, copilot
    operation_type = Column(String(64), nullable=False)           # generate, modify, chat
    model_name = Column(String(64), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, index=True)       # success, failed, timeout, retried
    retry_count = Column(Integer, default=0, nullable=False)
    error_category = Column(String(64), nullable=True, index=True) # quota, timeout, parse_error, network, validation, api_error
    error_message = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    structured_validation_passed = Column(Boolean, default=True, nullable=False)
    persistence_status = Column(String(32), default="persisted", nullable=False)  # persisted, failed, unattempted
    is_retryable = Column(Boolean, default=False, nullable=False)
    retry_of_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("evt_"))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    event_name = Column(String(64), nullable=False, index=True)
    event_category = Column(String(64), default="application", nullable=False)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("sec_"))
    event_type = Column(String(64), nullable=False, index=True)  # login_success, login_failure, unauthorized_access, csrf_rejected, session_revocation, password_change, account_suspension
    severity = Column(String(32), default="info", nullable=False)  # info, low, medium, high, critical
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(256), nullable=True)
    request_path = Column(String(256), nullable=True)
    details = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("aud_"))
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)  # user_suspend, user_reactivate, user_delete, config_update, system_repair, ai_retry, maintenance_toggle, session_revoked
    target_type = Column(String(64), nullable=False)         # user, project, system_setting, ai_operation, data_repair, session
    target_id = Column(String(64), nullable=True)
    outcome = Column(String(32), default="success", nullable=False)  # success, failed, denied
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    actor = relationship("User", back_populates="audit_logs")

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("set_"))
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(32), default="string", nullable=False)  # string, int, float, boolean, json
    category = Column(String(64), default="general", nullable=False)   # ai, security, maintenance, alerts, retention
    description = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False, nullable=False)
    updated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class AuthRateLimitEvent(Base):
    __tablename__ = "auth_rate_limit_events"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("lim_"))
    scope = Column(String(32), nullable=False)  # login_ip, login_account, admin_login_ip, admin_login_account, register_ip
    key_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_auth_rate_limit_scope_key_created", "scope", "key_hash", "created_at"),
        Index("ix_auth_rate_limit_created_at", "created_at"),
    )
