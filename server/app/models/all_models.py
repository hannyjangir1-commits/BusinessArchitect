import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
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
    terms_accepted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

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
