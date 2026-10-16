import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.base import Base

def gen_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("usr_"))
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
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

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("ses_"))
    session_token = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="sessions")

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("prj_"))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    stage = Column(String(32), nullable=False, default="Idea / MVP")  # "Idea / MVP", "Post-launch", "Growth"
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

class ModuleContent(Base):
    __tablename__ = "module_contents"
    __table_args__ = (
        UniqueConstraint("project_id", "module_type", name="uq_module_contents_project_module"),
    )

    id = Column(String(36), primary_key=True, default=lambda: gen_id("mod_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    module_type = Column(String(64), nullable=False)  # bmc, tech_stack, idea_validator, market_research, execution_roadmap, overview
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
    order_index = Column(Integer, default=0, nullable=False)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="tasks")

class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id = Column(String(36), primary_key=True, default=lambda: gen_id("msg_"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="copilot_messages")

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
