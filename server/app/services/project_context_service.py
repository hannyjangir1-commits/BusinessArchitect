"""Read-only, project-bounded snapshots for generation, assistants, and exports."""
import copy
import hashlib
import json
from typing import Any
from sqlalchemy.orm import Session
from app.core.module_types import normalize_module_type
from app.models.all_models import ModuleContent, ModuleVersion, Project, RoadmapTask, ProjectKnowledgeItem


def project_fingerprint(project: Project) -> str:
    fields = ("name", "stage", "description", "industry", "target_customers", "goals", "business_context", "budget", "existing_stack")
    payload = {field: getattr(project, field) for field in fields}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def find_module(db: Session, project_id: str, module_type: str) -> ModuleContent | None:
    canonical = normalize_module_type(module_type)
    names = [canonical, "detailed_roadmap"] if canonical == "execution_roadmap" else [canonical]
    candidates = db.query(ModuleContent).filter(
        ModuleContent.project_id == project_id, ModuleContent.module_type.in_(names)
    ).all()
    return next((m for m in candidates if m.module_type == canonical), None) or next(iter(candidates), None)


def active_version(db: Session, module: ModuleContent | None) -> ModuleVersion | None:
    if module is None:
        return None
    versions = db.query(ModuleVersion).filter(ModuleVersion.module_content_id == module.id)
    # A malformed pointer cannot pull content from a different module/project.
    if module.active_version_id:
        version = versions.filter(ModuleVersion.id == module.active_version_id).first()
        if version is not None:
            return version
    return versions.order_by(ModuleVersion.is_active.desc(), ModuleVersion.version_number.desc()).first()


def current_module_data(db: Session, module: ModuleContent, version: ModuleVersion) -> dict[str, Any]:
    data = copy.deepcopy(version.data) if isinstance(version.data, dict) else {}
    if normalize_module_type(module.module_type) != "execution_roadmap":
        return data
    # The task table owns current execution edits; immutable snapshots retain the
    # original plan. Readers/exporters must see today's tasks rather than stale JSON.
    tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == module.project_id).order_by(
        RoadmapTask.order_index.asc(), RoadmapTask.created_at.asc()
    ).all()
    fields = (
        "task_code", "phase", "title", "description", "timeline", "start_date", "end_date",
        "priority", "status", "dependencies", "deliverables", "effort", "assigned_to",
        "assigned_role", "department", "steps", "is_overloaded",
        "branch_type", "parent_outcome", "definition_of_done", "acceptance_criteria",
        "edge_type", "roadmap_mode",
    )
    data["tasks"] = [{field: copy.deepcopy(getattr(task, field)) for field in fields} for task in tasks]
    phases = {phase.get("name"): dict(phase) for phase in data.get("phases", []) if isinstance(phase, dict)}
    groups: dict[str, list] = {}
    for task in tasks:
        groups.setdefault(task.phase, []).append(task)
    data["phases"] = [dict(
        phases.get(name, {}), name=name,
        start_date=min(task.start_date for task in group),
        end_date=max(task.end_date for task in group)
    ) for name, group in groups.items()]
    return data


def read_project_context(db: Session, project_id: str, exclude_module: str | None = None):
    """Return copied recommendations plus their source identity, never ORM rows."""
    context: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    modules = db.query(ModuleContent).filter(ModuleContent.project_id == project_id).order_by(
        ModuleContent.updated_at.desc()
    ).all()
    # Prefer the canonical row if a legacy roadmap row still coexists.
    modules.sort(key=lambda m: m.module_type != normalize_module_type(m.module_type))
    for module in modules:
        canonical = normalize_module_type(module.module_type)
        if canonical in context or canonical == exclude_module:
            continue
        version = active_version(db, module)
        if version is None:
            continue
        data = current_module_data(db, module, version)
        # Hidden generation instructions and nested provenance do not become
        # prompt context for another module or user-facing export content.
        for key in ("context_metadata", "generation_brief", "constructed_prompt", "system_prompt", "custom_instructions"):
            data.pop(key, None)
        context[canonical] = data
        sources.append({
            "project_id": project_id, "module_type": canonical,
            "module_content_id": module.id, "version_id": version.id,
            "version_number": version.version_number, "version_name": version.version_name,
            "generated_at": version.created_at.isoformat(), "access": "read_only",
            "origin": "generated_recommendation",
            "content_fingerprint": hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(),
        })

    # Include active project knowledge items if present
    knowledge_items = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.project_id == project_id,
        ProjectKnowledgeItem.status == "active",
    ).order_by(ProjectKnowledgeItem.created_at.asc()).all()
    if knowledge_items:
        k_data = [
            {
                "id": item.id,
                "item_type": item.item_type,
                "title": item.title,
                "content": item.content,
                "status": item.status,
                "epistemic_status": item.epistemic_status,
                "source_reference": item.source_reference,
                "linked_module": item.linked_module,
                "metadata_json": copy.deepcopy(item.metadata_json) if isinstance(item.metadata_json, dict) else {},
            }
            for item in knowledge_items
        ]
        context["knowledge_base"] = k_data
        sources.append({
            "project_id": project_id,
            "module_type": "knowledge_base",
            "access": "read_only",
            "origin": "project_knowledge_items",
            "count": len(k_data),
            "content_fingerprint": hashlib.sha256(json.dumps(k_data, sort_keys=True, default=str).encode()).hexdigest(),
        })

    return context, sources
