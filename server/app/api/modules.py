import time
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask
from app.schemas.modules import (
    ModuleDetailResponse, VersionItemResponse, VersionRenameRequest,
    VersionConflictResolveRequest, SectionModifyRequest,
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData,
    ExecutionRoadmapData, RoadmapPlanningRequest
)
from app.services.version_service import VersionService
from app.services.readiness_service import ReadinessValidationService
from app.services.pdf_service import PDFService
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.telemetry import record_ai_operation, record_analytics_event
from app.core.business_stage import normalize_business_stage
from app.core.module_types import normalize_module_type

router = APIRouter(prefix="/projects/{project_id}/modules", tags=["Modules & Version Control"])

ALLOWED_CHAT_MODULES = {"overview", "bmc", "tech_stack", "execution_roadmap", "detailed_roadmap"}
DISALLOWED_CHAT_MODULES = {"idea_validator", "market_research"}
DELETABLE_MODULE_TYPES = {"bmc", "tech_stack", "idea_validator", "market_research", "execution_roadmap"}

def _validate_module_data(module_type: str, data: Dict[str, Any]):
    if not isinstance(data, dict):
        raise ValueError("Module data must be a structured dictionary")
    if module_type == "bmc":
        BMCData.model_validate(data)
    elif module_type == "tech_stack":
        TechStackData.model_validate(data)
    elif module_type == "idea_validator":
        IdeaValidatorData.model_validate(data)
    elif module_type == "market_research":
        MarketResearchData.model_validate(data)
    elif module_type in ("execution_roadmap", "detailed_roadmap"):
        ExecutionRoadmapData.model_validate(data)

def _reconcile_roadmap_tasks(db: Session, project: Project, tasks_data: List[Dict[str, Any]]):
    existing_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    existing_by_code = {t.task_code: t for t in existing_tasks}

    base_date_str = project.created_at.strftime("%Y-%m-%d") if project.created_at else "2026-10-01"
    active_codes = set()

    for idx, t in enumerate(tasks_data):
        code = t.get("task_code") or f"TSK-{str(idx+1).zfill(2)}"
        active_codes.add(code)
        s_date = t.get("start_date") or base_date_str
        e_date = t.get("end_date") or s_date
        if e_date < s_date:
            e_date = s_date

        if code in existing_by_code:
            cur = existing_by_code[code]
            # Preserve user edits if in progress or finished
            if cur.status not in ("In Progress", "Ongoing", "Finished"):
                raw_st = t.get("status", "Pending")
                cur.status = "In Progress" if raw_st in ("In Progress", "Ongoing") else raw_st
            cur.phase = t.get("phase", cur.phase)
            cur.title = t.get("title", cur.title)
            cur.description = t.get("description", cur.description)
            cur.timeline = t.get("timeline", cur.timeline)
            cur.start_date = s_date
            cur.end_date = e_date
            cur.priority = t.get("priority", cur.priority)
            cur.dependencies = t.get("dependencies", cur.dependencies)
            cur.deliverables = t.get("deliverables", cur.deliverables)
            cur.effort = t.get("effort", cur.effort)
            cur.assigned_to = t.get("assigned_to", cur.assigned_to or "Unassigned")
            cur.assigned_role = t.get("assigned_role", cur.assigned_role)
            cur.department = t.get("department", cur.department)
            cur.steps = t.get("steps", cur.steps or [])
            cur.is_overloaded = t.get("is_overloaded", cur.is_overloaded or False)
            cur.order_index = idx
        else:
            raw_st = t.get("status", "Pending")
            st_val = "In Progress" if raw_st in ("In Progress", "Ongoing") else raw_st
            new_task = RoadmapTask(
                project_id=project.id,
                task_code=code,
                phase=t.get("phase", "Planning & Research"),
                title=t.get("title", f"Task {idx+1}"),
                description=t.get("description", ""),
                timeline=t.get("timeline", "30-day"),
                start_date=s_date,
                end_date=e_date,
                priority=t.get("priority", "Medium"),
                status=st_val,
                dependencies=t.get("dependencies", []),
                deliverables=t.get("deliverables", ""),
                effort=t.get("effort", "1 week"),
                assigned_to=t.get("assigned_to", "Unassigned"),
                assigned_role=t.get("assigned_role"),
                department=t.get("department"),
                steps=t.get("steps", []),
                is_overloaded=t.get("is_overloaded", False),
                order_index=idx,
                is_ai_generated=True
            )
            db.add(new_task)

    # Obsolete AI-generated tasks removal:
    # Delete tasks if they were AI-generated and are not in the active roadmap JSON.
    # Preserve manual user-created tasks (is_ai_generated == False).
    for cur in existing_tasks:
        if cur.task_code not in active_codes and cur.is_ai_generated and cur.status not in ("Finished", "Completed"):
            db.delete(cur)

    db.flush()

def _get_project_dict(project: Project) -> Dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "stage": normalize_business_stage(project.stage),
        "description": project.description,
        "industry": project.industry,
        "target_customers": project.target_customers,
        "goals": project.goals,
        "business_context": project.business_context,
        "budget": project.budget,
        "existing_stack": project.existing_stack or {}
    }


def _parse_roadmap_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _matches_planning_items(task: Dict[str, Any], items: List[str]) -> bool:
    ignored = {"the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "have", "has", "been", "already", "complete", "completed", "defined", "work", "task"}
    task_text = f"{task.get('title', '')} {task.get('description', '')}".lower()
    task_terms = set(re.findall(r"[a-z0-9]+", task_text)) - ignored
    if not task_terms:
        return False
    for item in items:
        item_text = str(item).strip().lower()
        item_terms = set(re.findall(r"[a-z0-9]+", item_text)) - ignored
        if item_text and (item_text in task_text or task_text.strip() in item_text):
            return True
        overlap = len(task_terms & item_terms)
        if len(item_terms) >= 2 and overlap >= 2 and overlap / len(item_terms) >= 0.65:
            return True
    return False


def _normalize_roadmap_schedule(data: Dict[str, Any], planning: RoadmapPlanningRequest) -> Dict[str, Any]:
    """Repair malformed dates and shift unfinished work to the requested/current date."""
    result = dict(data)
    today = date.today()
    baseline = max(planning.start_date, today)
    tasks = [dict(task) for task in result.get("tasks", []) if isinstance(task, dict)]
    completed_items = [item.item for item in planning.checklist if item.status == "Completed"]
    completed_items.extend(part.strip() for part in re.split(r"[\n;]+", planning.completed_work) if part.strip())
    in_progress_items = [item.item for item in planning.checklist if item.status == "In progress"]
    in_progress_items.extend(part.strip() for part in re.split(r"[\n;]+", planning.in_progress_work) if part.strip())
    cursor = baseline

    for index, task in enumerate(tasks):
        task["task_code"] = task.get("task_code") or f"TSK-{index + 1:02d}"
        task["phase"] = str(task.get("phase") or "Execution").strip() or "Execution"
        raw_status = str(task.get("status") or "Pending").strip().lower()
        if raw_status in {"in progress", "ongoing", "underway"} and _matches_planning_items(task, in_progress_items):
            task["status"] = "In Progress"
        elif raw_status in {"finished", "completed", "done"} and _matches_planning_items(task, completed_items):
            task["status"] = "Finished"
        else:
            task["status"] = "Pending"
        start = _parse_roadmap_date(task.get("start_date")) or cursor
        end = _parse_roadmap_date(task.get("end_date")) or (start + timedelta(days=6))
        if end < start:
            end = start + timedelta(days=6)
        task["start_date"] = start.isoformat()
        task["end_date"] = end.isoformat()
        cursor = max(cursor, end + timedelta(days=1))

    unfinished_starts = [
        _parse_roadmap_date(task["start_date"])
        for task in tasks
        if str(task.get("status", "Pending")).strip().lower() not in {"finished", "completed"}
    ]
    valid_starts = [value for value in unfinished_starts if value]
    shift_days = max(0, (baseline - min(valid_starts)).days) if valid_starts else 0

    for task in tasks:
        is_finished = str(task.get("status", "Pending")).strip().lower() in {"finished", "completed"}
        if not is_finished and shift_days:
            start = _parse_roadmap_date(task["start_date"]) + timedelta(days=shift_days)
            end = _parse_roadmap_date(task["end_date"]) + timedelta(days=shift_days)
            task["start_date"] = start.isoformat()
            task["end_date"] = end.isoformat()

    colors = ["#78906c", "#9a815c", "#b09a68", "#687f5d", "#b77d68", "#bb816a"]
    raw_phases = {phase.get("name"): phase for phase in (result.get("phases") or []) if isinstance(phase, dict)}
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for task in tasks:
        grouped.setdefault(task["phase"], []).append(task)

    phases = []
    for index, (name, phase_tasks) in enumerate(grouped.items()):
        first = raw_phases.get(name, {})
        phases.append({
            "name": name,
            "color": first.get("color") or colors[index % len(colors)],
            "start_date": min(task["start_date"] for task in phase_tasks),
            "end_date": max(task["end_date"] for task in phase_tasks),
            "description": first.get("description") or f"Work grouped under {name}.",
        })

    _detect_and_break_dependency_cycles(tasks)
    result["tasks"] = tasks
    result["phases"] = phases
    return result

def _detect_and_break_dependency_cycles(tasks: List[Dict[str, Any]]) -> None:
    """Detect circular dependencies (e.g. A -> B and B -> A) and remove offending back-edges."""
    adj: Dict[str, List[str]] = {}
    for t in tasks:
        code = t.get("task_code")
        if code:
            deps = t.get("dependencies") or []
            adj[code] = [d for d in deps if isinstance(d, str)]

    visited: Dict[str, int] = {}

    def dfs(node: str, path: List[str]):
        visited[node] = 1
        path.append(node)
        for neighbor in list(adj.get(node, [])):
            if visited.get(neighbor) == 1:
                # Cycle detected: remove back-edge
                if neighbor in adj[node]:
                    adj[node].remove(neighbor)
                for t in tasks:
                    if t.get("task_code") == node:
                        t_deps = t.get("dependencies", [])
                        if neighbor in t_deps:
                            t_deps.remove(neighbor)
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor, path)
        path.pop()
        visited[node] = 2

    for code in list(adj.keys()):
        if visited.get(code, 0) == 0:
            dfs(code, [])
    return tasks

def _gather_cross_module_context(db: Session, project_id: str) -> Dict[str, Any]:
    context = {}
    modules = db.query(ModuleContent).filter(
        ModuleContent.project_id == project_id
    ).order_by(ModuleContent.updated_at.desc()).all()
    for m in modules:
        if m.active_version_id:
            ver = db.query(ModuleVersion).filter(ModuleVersion.id == m.active_version_id).first()
            if ver and ver.data:
                context.setdefault(normalize_module_type(m.module_type), ver.data)
    return context


def _merge_legacy_roadmap_history(
    db: Session,
    canonical_module: ModuleContent,
    legacy_module: ModuleContent,
) -> None:
    """Move legacy roadmap snapshots into the unified record without dropping history."""
    canonical_versions = VersionService.get_versions(db, canonical_module.id)
    legacy_versions = VersionService.get_versions(db, legacy_module.id)

    canonical_active = next(
        (version for version in canonical_versions if version.id == canonical_module.active_version_id),
        None,
    ) or next((version for version in canonical_versions if version.is_active), None)
    if canonical_active is None and canonical_versions:
        canonical_active = canonical_versions[-1]

    legacy_active = next(
        (version for version in legacy_versions if version.id == legacy_module.active_version_id),
        None,
    ) or next((version for version in legacy_versions if version.is_active), None)
    if canonical_active is None and legacy_active is None and legacy_versions:
        legacy_active = legacy_versions[-1]

    active_version_id = canonical_active.id if canonical_active else (legacy_active.id if legacy_active else None)
    next_number = max((version.version_number for version in canonical_versions), default=0) + 1

    for offset, version in enumerate(legacy_versions):
        version.module_content_id = canonical_module.id
        version.version_number = next_number + offset
        version.is_active = version.id == active_version_id

    for version in canonical_versions:
        version.is_active = version.id == active_version_id

    canonical_module.active_version_id = active_version_id
    # Flush the foreign-key moves before deleting the now-empty legacy parent;
    # its ORM delete-orphan cascade must not remove the preserved snapshots.
    db.flush()
    db.delete(legacy_module)
    db.flush()


def _get_or_create_canonical_module(db: Session, project_id: str, module_type: str) -> ModuleContent:
    """Reuse a legacy roadmap record on first write, preserving its full history."""
    canonical_type = normalize_module_type(module_type)
    module = db.query(ModuleContent).filter(
        ModuleContent.project_id == project_id,
        ModuleContent.module_type == canonical_type
    ).first()
    if module:
        if canonical_type == "execution_roadmap":
            legacy_module = db.query(ModuleContent).filter(
                ModuleContent.project_id == project_id,
                ModuleContent.module_type == "detailed_roadmap"
            ).first()
            if legacy_module:
                _merge_legacy_roadmap_history(db, module, legacy_module)
        return module

    if canonical_type == "execution_roadmap":
        legacy_module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project_id,
            ModuleContent.module_type == "detailed_roadmap"
        ).first()
        if legacy_module:
            legacy_module.module_type = canonical_type
            db.flush()
            return legacy_module

    return VersionService.get_or_create_module(db, project_id, canonical_type)

@router.get("/{module_type}", response_model=ModuleDetailResponse)
def get_module(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    module = db.query(ModuleContent).filter(
        ModuleContent.project_id == project.id,
        ModuleContent.module_type == module_type
    ).first()

    # Old projects may contain only the former module, or both former and
    # unified rows. Reads of a legacy-only project remain side-effect free;
    # when both rows exist, merge their version history so it remains visible.
    if not module and module_type == "execution_roadmap":
        module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project.id,
            ModuleContent.module_type == "detailed_roadmap"
        ).first()
    elif module and module_type == "execution_roadmap":
        legacy_module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project.id,
            ModuleContent.module_type == "detailed_roadmap"
        ).first()
        if legacy_module:
            _merge_legacy_roadmap_history(db, module, legacy_module)
            db.commit()

    if not module:
        return ModuleDetailResponse(
            module_type=module_type,
            active_version_id=None,
            active_version_name=None,
            active_version_number=None,
            data=None,
            versions=[]
        )

    versions = VersionService.get_versions(db, module.id)

    active_ver = None
    if module.active_version_id:
        active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
    if not active_ver and versions:
        active_ver = versions[-1]
        module.active_version_id = active_ver.id
        db.commit()

    is_stale = False
    stale_reason = None
    stale_source_module = None

    if active_ver:
        if module_type in ("execution_roadmap", "detailed_roadmap"):
            ts_mod = db.query(ModuleContent).filter(
                ModuleContent.project_id == project.id,
                ModuleContent.module_type == "tech_stack"
            ).first()
            if ts_mod and ts_mod.active_version_id:
                ts_ver = db.query(ModuleVersion).filter(ModuleVersion.id == ts_mod.active_version_id).first()
                if ts_ver and ts_ver.created_at > active_ver.created_at:
                    is_stale = True
                    stale_reason = f"Tech Stack was updated on {ts_ver.created_at.strftime('%Y-%m-%d %H:%M')}. Would you like to refresh your Roadmap to align with the latest architecture?"
                    stale_source_module = "tech_stack"

        elif module_type in ("idea_validator", "market_research"):
            bmc_mod = db.query(ModuleContent).filter(
                ModuleContent.project_id == project.id,
                ModuleContent.module_type == "bmc"
            ).first()
            if bmc_mod and bmc_mod.active_version_id:
                bmc_ver = db.query(ModuleVersion).filter(ModuleVersion.id == bmc_mod.active_version_id).first()
                if bmc_ver and bmc_ver.created_at > active_ver.created_at:
                    is_stale = True
                    stale_reason = f"Business Model Canvas was updated on {bmc_ver.created_at.strftime('%Y-%m-%d %H:%M')}. Refresh {module_type.replace('_', ' ').title()} to incorporate revised customer segments and value propositions?"
                    stale_source_module = "bmc"

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=active_ver.id if active_ver else None,
        active_version_name=active_ver.version_name if active_ver else None,
        active_version_number=active_ver.version_number if active_ver else None,
        data=active_ver.data if active_ver else None,
        versions=[VersionItemResponse.model_validate(v) for v in versions],
        is_stale=is_stale,
        stale_reason=stale_reason,
        stale_source_module=stale_source_module,
        context_metadata=active_ver.data.get("context_metadata") if (active_ver and isinstance(active_ver.data, dict)) else None
    )

@router.delete("/{module_type}", dependencies=[Depends(verify_csrf)])
def delete_module(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Delete one generated module and its saved versions for the owning project."""
    canonical_type = normalize_module_type(module_type)
    if canonical_type not in DELETABLE_MODULE_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated module not found")

    stored_types = [canonical_type]
    if canonical_type == "execution_roadmap":
        # Remove both the current canonical row and any untouched legacy row.
        stored_types.append("detailed_roadmap")

    try:
        modules = db.query(ModuleContent).filter(
            ModuleContent.project_id == project.id,
            ModuleContent.module_type.in_(stored_types)
        ).all()
        for module in modules:
            db.delete(module)

        deleted_tasks = 0
        if canonical_type == "execution_roadmap":
            deleted_tasks = db.query(RoadmapTask).filter(
                RoadmapTask.project_id == project.id
            ).delete(synchronize_session=False)

        if modules or deleted_tasks:
            # Child-row deletion is not an ORM update to Project, so its
            # onupdate hook will not run unless we explicitly touch the row.
            project.updated_at = datetime.now(timezone.utc)

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete {canonical_type.replace('_', ' ')}"
        )

    return {
        "message": f"{canonical_type.replace('_', ' ').title()} deleted successfully",
        "module_type": canonical_type,
        "deleted_records": len(modules),
        "deleted_tasks": deleted_tasks
    }

@router.post("/{module_type}/generate", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def generate_module(
    module_type: str,
    planning_inputs: RoadmapPlanningRequest | None = None,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    # Enforce input readiness validation before invoking AI service
    is_ready, missing_fields, error_msgs = ReadinessValidationService.validate_project_readiness(project, module_type)
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "READINESS_VALIDATION_FAILED",
                "message": "Project details are insufficient or invalid for blueprint generation.",
                "missing_fields": missing_fields,
                "reasons": error_msgs,
                "action_required": "Please update your project parameters in the Overview module before generating."
            }
        )

    proj_info = _get_project_dict(project)
    module = _get_or_create_canonical_module(db, project.id, module_type)
    cross_ctx = _gather_cross_module_context(db, project.id)
    t0 = time.time()

    try:
        planning_dict = None
        if module_type in ("execution_roadmap", "detailed_roadmap"):
            planning = planning_inputs or RoadmapPlanningRequest()
            planning_dict = planning.model_dump(mode="json")

        # Stage 1: Build server-side generation brief
        brief = ai_service.build_generation_brief(
            proj_info,
            module_type,
            cross_module_context=cross_ctx,
            planning_inputs=planning_dict
        )

        # Stage 2: Tailored module synthesis
        if module_type == "bmc":
            generated = ai_service.generate_bmc(proj_info, brief, cross_module_context=cross_ctx)
            data_dict = generated.model_dump()
        elif module_type == "tech_stack":
            generated = ai_service.generate_tech_stack(proj_info, brief, cross_module_context=cross_ctx)
            data_dict = generated.model_dump()
        elif module_type == "idea_validator":
            generated = ai_service.generate_idea_validator(proj_info, brief, cross_module_context=cross_ctx)
            data_dict = generated.model_dump()
        elif module_type == "market_research":
            generated = ai_service.generate_market_research(proj_info, brief, cross_module_context=cross_ctx)
            data_dict = generated.model_dump()
        elif module_type in ("execution_roadmap", "detailed_roadmap"):
            roadmap_raw = ai_service.generate_roadmap(proj_info, planning_dict, brief, cross_module_context=cross_ctx)
            data_dict = _normalize_roadmap_schedule(roadmap_raw, planning)
            data_dict["planning_inputs"] = planning_dict
            if "feasibility_evaluation" in roadmap_raw and "feasibility_evaluation" not in data_dict:
                data_dict["feasibility_evaluation"] = roadmap_raw["feasibility_evaluation"]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported module type: {module_type}")

        # Provenance: Attach context metadata
        data_dict["context_metadata"] = {
            "stage": proj_info.get("stage"),
            "industry": proj_info.get("industry"),
            "budget": proj_info.get("budget"),
            "technical_depth": brief.technical_depth,
            "brief_summary": brief.venture_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cross_modules_used": [k for k in cross_ctx.keys() if k != module_type]
        }

        # Validate module payload against schema before persistence (F-09)
        _validate_module_data(module_type, data_dict)

        # Save new version and reconcile roadmap tasks in single atomic transaction (F-08)
        new_ver = VersionService.save_new_version(
            db=db,
            module=module,
            data=data_dict,
            change_summary="Initial blueprint generation",
            commit=False
        )

        if module_type in ("execution_roadmap", "detailed_roadmap"):
            tasks_data = data_dict.get("tasks", [])
            _reconcile_roadmap_tasks(db, project, tasks_data)

        db.commit()
        db.refresh(new_ver)

        dur_ms = int((time.time() - t0) * 1000)
        record_ai_operation(
            db,
            user_id=project.user_id,
            project_id=project.id,
            module_type=module_type,
            operation_type="generate",
            model_name=settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="success",
            structured_validation_passed=True,
            persistence_status="persisted"
        )
        record_analytics_event(
            db,
            user_id=project.user_id,
            project_id=project.id,
            event_name=f"{module_type}_generated"
        )

        versions = VersionService.get_versions(db, module.id)
        return ModuleDetailResponse(
            module_type=module_type,
            active_version_id=new_ver.id,
            active_version_name=new_ver.version_name,
            active_version_number=new_ver.version_number,
            data=new_ver.data,
            versions=[VersionItemResponse.model_validate(v) for v in versions],
            is_stale=False,
            context_metadata=data_dict["context_metadata"]
        )

    except HTTPException:
        raise
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        terminal_provider_error = ai_service._terminal_provider_error_message(e)
        err_msg = terminal_provider_error or str(e)
        err_cat = "provider_error" if terminal_provider_error else ("timeout" if "timeout" in err_msg.lower() else ("parse_error" if "json" in err_msg.lower() or "validation" in err_msg.lower() else "api_error"))
        record_ai_operation(
            db,
            user_id=project.user_id,
            project_id=project.id,
            module_type=module_type,
            operation_type="generate",
            model_name=settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="timeout" if "timeout" in err_msg.lower() else "failed",
            error_category=err_cat,
            error_message=err_msg,
            structured_validation_passed=False,
            persistence_status="failed",
            is_retryable=terminal_provider_error is None
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {err_msg}"
        )

@router.post("/{module_type}/accept-update", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def accept_module_update(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Explicitly refresh a stale module using latest cross-module context without mutating other modules."""
    return generate_module(module_type=module_type, planning_inputs=None, project=project, db=db)

@router.post("/{module_type}/modify", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def modify_module_with_ai(
    module_type: str,
    req: SectionModifyRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    """
    Section-specific AI modification chat.
    Validates that modification is allowed on this module.
    Preserves existing content, applies requested edits, creates a new version.
    """
    if module_type in DISALLOWED_CHAT_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Section-specific AI modification chat is disabled for {module_type.replace('_', ' ').title()} as per system rules."
        )

    module = _get_or_create_canonical_module(db, project.id, module_type)
    if not module.active_version_id:
        raise HTTPException(
            status_code=400,
            detail="Module has no active version to modify. Please generate content first."
        )

    active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
    if not active_ver:
        raise HTTPException(status_code=404, detail="Active version data not found")

    versions = VersionService.get_versions(db, module.id)
    if len(versions) >= 5:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "VERSION_LIMIT_EXCEEDED",
                "message": "This section already has the maximum of 5 saved versions. Choose a version to replace or delete.",
                "existing_versions": [
                    {
                        "id": v.id,
                        "version_number": v.version_number,
                        "version_name": v.version_name,
                        "change_summary": v.change_summary,
                        "is_active": v.is_active,
                        "created_at": v.created_at.isoformat()
                    }
                    for v in versions
                ]
            }
        )

    t0 = time.time()
    try:
        new_data, change_summary = ai_service.modify_section(
            module_type=module_type,
            current_data=active_ver.data,
            instruction=req.instruction
        )
        if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
            saved_inputs = (active_ver.data or {}).get("planning_inputs", {}) if isinstance(active_ver.data, dict) else {}
            planning = RoadmapPlanningRequest.model_validate(saved_inputs or {})
            new_data = _normalize_roadmap_schedule(new_data, planning)
            new_data["planning_inputs"] = planning.model_dump(mode="json")
        # Validate modified data against schema before persistence (F-09)
        _validate_module_data(module_type, new_data)

        # Save new version and reconcile roadmap tasks in single atomic transaction (F-08)
        new_ver = VersionService.save_new_version(
            db=db,
            module=module,
            data=new_data,
            change_summary=change_summary,
            commit=False
        )

        # Reconcile roadmap tasks if roadmap
        if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
            tasks_data = new_data.get("tasks", [])
            _reconcile_roadmap_tasks(db, project, tasks_data)

        db.commit()
        db.refresh(new_ver)

        dur_ms = int((time.time() - t0) * 1000)
        record_ai_operation(
            db,
            user_id=project.user_id,
            project_id=project.id,
            module_type=module_type,
            operation_type="modify",
            model_name=settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="success",
            structured_validation_passed=True,
            persistence_status="persisted"
        )
        record_analytics_event(
            db,
            user_id=project.user_id,
            project_id=project.id,
            event_name=f"{module_type}_modified"
        )

        versions = VersionService.get_versions(db, module.id)
        return ModuleDetailResponse(
            module_type=module_type,
            active_version_id=new_ver.id,
            active_version_name=new_ver.version_name,
            active_version_number=new_ver.version_number,
            data=new_ver.data,
            versions=[VersionItemResponse.model_validate(v) for v in versions]
        )
    except HTTPException:
        raise
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        terminal_provider_error = ai_service._terminal_provider_error_message(e)
        err_msg = terminal_provider_error or str(e)
        err_cat = "provider_error" if terminal_provider_error else ("timeout" if "timeout" in err_msg.lower() else "api_error")
        record_ai_operation(
            db,
            user_id=project.user_id,
            project_id=project.id,
            module_type=module_type,
            operation_type="modify",
            model_name=settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="timeout" if "timeout" in err_msg.lower() else "failed",
            error_category=err_cat,
            error_message=err_msg,
            structured_validation_passed=False,
            persistence_status="failed",
            is_retryable=terminal_provider_error is None
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Module update failed: {err_msg}"
        )

@router.post("/{module_type}/resolve-conflict", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def resolve_version_conflict(
    module_type: str,
    req: VersionConflictResolveRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    """User-confirmed replacement of an existing version when the 5-version limit is reached."""
    module = _get_or_create_canonical_module(db, project.id, module_type)

    target_ver = db.query(ModuleVersion).filter(
        ModuleVersion.id == req.replace_version_id,
        ModuleVersion.module_content_id == module.id
    ).first()
    if not target_ver:
        raise HTTPException(status_code=404, detail="Target version to replace not found in this module")

    new_data = req.new_data
    change_summary = req.change_summary

    # If pending instruction provided, apply it via Gemini AI and validate
    if req.instruction:
        active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
        if not active_ver:
            raise HTTPException(status_code=400, detail="No active version data found to apply modification")

        t0 = time.time()
        try:
            modified_data, summary = ai_service.modify_section(
                module_type=module_type,
                current_data=active_ver.data,
                instruction=req.instruction
            )
            _validate_module_data(module_type, modified_data)
            new_data = modified_data
            change_summary = summary or req.change_summary or f"Applied instruction: {req.instruction[:60]}"

            dur_ms = int((time.time() - t0) * 1000)
            record_ai_operation(
                db,
                user_id=project.user_id,
                project_id=project.id,
                module_type=module_type,
                operation_type="modify",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="success",
                structured_validation_passed=True,
                persistence_status="persisted"
            )
        except Exception as e:
            dur_ms = int((time.time() - t0) * 1000)
            terminal_provider_error = ai_service._terminal_provider_error_message(e)
            err_msg = terminal_provider_error or str(e)
            record_ai_operation(
                db,
                user_id=project.user_id,
                project_id=project.id,
                module_type=module_type,
                operation_type="modify",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="failed",
                error_category="provider_error" if terminal_provider_error else ("validation_error" if "validation" in err_msg.lower() else "api_error"),
                error_message=err_msg,
                structured_validation_passed=False,
                persistence_status="failed",
                is_retryable=terminal_provider_error is None
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Module update during conflict resolution failed: {err_msg}"
            )

    if not new_data:
        raise HTTPException(status_code=400, detail="Missing new data or modification instruction for version replacement")

    # Validate replacement payload before persistence (F-09)
    try:
        _validate_module_data(module_type, new_data)
    except Exception as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation failed for {module_type}: {str(ve)}"
        )

    replaced_ver = VersionService.resolve_conflict_and_replace(
        db=db,
        module=module,
        replace_version_id=req.replace_version_id,
        new_data=new_data,
        new_name=req.new_version_name,
        change_summary=change_summary,
        commit=False
    )

    if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
        tasks_data = new_data.get("tasks", [])
        if tasks_data:
            _reconcile_roadmap_tasks(db, project, tasks_data)

    db.commit()
    db.refresh(replaced_ver)

    versions = VersionService.get_versions(db, module.id)
    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=replaced_ver.id,
        active_version_name=replaced_ver.version_name,
        active_version_number=replaced_ver.version_number,
        data=replaced_ver.data,
        versions=[VersionItemResponse.model_validate(v) for v in versions]
    )

@router.patch("/{module_type}/versions/{version_id}/rename", dependencies=[Depends(verify_csrf)])
@router.patch("/{module_type}/versions/{version_id}", dependencies=[Depends(verify_csrf)])
def rename_version(
    module_type: str,
    version_id: str,
    req: VersionRenameRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    module = _get_or_create_canonical_module(db, project.id, module_type)
    renamed = VersionService.rename_version(db, module, version_id, req.version_name)
    return {"message": "Version renamed successfully", "version_name": renamed.version_name}

@router.delete("/{module_type}/versions/{version_id}", dependencies=[Depends(verify_csrf)])
def delete_version(
    module_type: str,
    version_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    module = _get_or_create_canonical_module(db, project.id, module_type)
    VersionService.delete_version(db, module, version_id)
    if module_type == "execution_roadmap":
        active_version = db.query(ModuleVersion).filter(
            ModuleVersion.id == module.active_version_id,
            ModuleVersion.module_content_id == module.id
        ).first()
        tasks_data = active_version.data.get("tasks", []) if active_version and isinstance(active_version.data, dict) else []
        _reconcile_roadmap_tasks(db, project, tasks_data)
        db.commit()
    return {"message": "Version successfully deleted"}

@router.post("/{module_type}/versions/{version_id}/restore", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def restore_version(
    module_type: str,
    version_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    module = _get_or_create_canonical_module(db, project.id, module_type)
    new_ver = VersionService.restore_version(db, module, version_id, commit=False)

    if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_ver.data, dict):
        tasks_data = new_ver.data.get("tasks", [])
        _reconcile_roadmap_tasks(db, project, tasks_data)

    db.commit()
    db.refresh(new_ver)
    versions = VersionService.get_versions(db, module.id)

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=new_ver.id,
        active_version_name=new_ver.version_name,
        active_version_number=new_ver.version_number,
        data=new_ver.data,
        versions=[VersionItemResponse.model_validate(v) for v in versions]
    )

@router.get("/{module_type}/export/pdf")
def export_module_pdf_alias(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Exports a dedicated PDF for a single specified module."""
    module_type = normalize_module_type(module_type)
    proj_dict = _get_project_dict(project)
    module = _get_or_create_canonical_module(db, project.id, module_type)

    if not module or not module.active_version_id:
        # If overview or default, generate fallback data
        if module_type == "overview":
            mod_data = {"description": project.description, "goals": project.goals, "stage": normalize_business_stage(project.stage)}
        else:
            raise HTTPException(status_code=404, detail="No active version found for this module to export")
    else:
        ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
        if not ver:
            raise HTTPException(status_code=404, detail="Active version content not found")
        mod_data = ver.data

    try:
        pdf_bytes = PDFService.generate_single_module_pdf(proj_dict, module_type, mod_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{project.name}_{module_type}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export module PDF: {str(e)}")

