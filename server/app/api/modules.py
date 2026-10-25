import time
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.db.session import get_db, SessionLocal
from app.core.config import settings
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask, User
from app.schemas.modules import (
    ModuleDetailResponse, VersionItemResponse, VersionRenameRequest,
    VersionConflictResolveRequest, SectionModifyRequest,
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData,
    ExecutionRoadmapData, RoadmapPlanningRequest, TechStackPlanningRequest
)
from app.services.version_service import VersionService
from app.services.readiness_service import ReadinessValidationService
from app.services.pdf_service import PDFService
from app.services.project_context_service import active_version, current_module_data, find_module, project_fingerprint, read_project_context
from app.services.transaction_service import lock_record
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.telemetry import record_ai_operation, record_analytics_event
from app.core.business_stage import normalize_business_stage
from app.core.module_types import normalize_module_type
from app.core.exports import format_content_disposition
from app.services.task_graph_validator import project_first_lock
from app.core.ai_limiter import check_ai_rate_limit

router = APIRouter(prefix="/projects/{project_id}/modules", tags=["Modules & Version Control"])

ALLOWED_CHAT_MODULES = {"overview", "bmc", "tech_stack", "execution_roadmap", "detailed_roadmap"}
DISALLOWED_CHAT_MODULES = {"idea_validator", "market_research"}
DELETABLE_MODULE_TYPES = {"bmc", "tech_stack", "idea_validator", "market_research", "execution_roadmap"}

from app.services.roadmap_service import RoadmapDomainService
from app.services.module_orchestration_service import ModuleOrchestrationService

# Facade aliases for internal and external module callers
_validate_module_data = ModuleOrchestrationService.validate_module_payload
_reconcile_roadmap_tasks = RoadmapDomainService.reconcile_roadmap_tasks
_normalize_roadmap_schedule = RoadmapDomainService.normalize_roadmap_schedule
_detect_and_break_dependency_cycles = RoadmapDomainService.detect_and_break_dependency_cycles
_parse_roadmap_date = RoadmapDomainService.parse_roadmap_date
_matches_planning_items = RoadmapDomainService.matches_planning_items

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

def _gather_cross_module_context(db: Session, project_id: str) -> Dict[str, Any]:
    return read_project_context(db, project_id)[0]


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
        version.is_active = (version.id == active_version_id)
        flag_modified(version, "is_active")

    for version in canonical_versions:
        version.is_active = (version.id == active_version_id)
        flag_modified(version, "is_active")

    canonical_module.active_version_id = active_version_id
    # Flush the foreign-key moves before deleting the now-empty legacy parent;
    # its ORM delete-orphan cascade must not remove the preserved snapshots.
    db.flush()
    db.delete(legacy_module)
    db.flush()

    if active_version_id and canonical_module.module_type in ("execution_roadmap", "detailed_roadmap"):
        VersionService.sync_roadmap_working_tasks_to_active_version(db, canonical_module)


def _get_or_create_canonical_module(db: Session, project_id: str, module_type: str) -> ModuleContent:
    """Reuse a legacy roadmap record on first write, preserving its full history."""
    canonical_type = normalize_module_type(module_type)
    if canonical_type not in DELETABLE_MODULE_TYPES and canonical_type != "overview":
        raise HTTPException(status_code=404, detail="Unknown module")
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
                with project_first_lock(db, project_id, module.id):
                    _merge_legacy_roadmap_history(db, module, legacy_module)
        return module

    if canonical_type == "execution_roadmap":
        legacy_module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project_id,
            ModuleContent.module_type == "detailed_roadmap"
        ).first()
        if legacy_module:
            legacy_module.module_type = canonical_type
            db.commit()
            db.refresh(legacy_module)
            return legacy_module

    return VersionService.get_or_create_module(db, project_id, canonical_type)

@router.get("/{module_type}", response_model=ModuleDetailResponse)
def get_module(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    if module_type not in DELETABLE_MODULE_TYPES and module_type != "overview":
        raise HTTPException(status_code=404, detail="Unknown module")
    from app.core.diagnostics import record_stage

    with record_stage("module_query"):
        module = db.query(ModuleContent).filter(
            ModuleContent.project_id == project.id,
            ModuleContent.module_type == module_type
        ).first()

        # Reads never migrate or repair records. Legacy history is combined for
        # display, and is moved only during an authorized write.
        legacy_module = None
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

    if not module:
        return ModuleDetailResponse(
            module_type=module_type,
            active_version_id=None,
            active_version_name=None,
            active_version_number=None,
            data=None,
            versions=[]
        )

    with record_stage("version_metadata_query"):
        versions = VersionService.get_version_metadata(db, module.id)
        if legacy_module and legacy_module.id != module.id:
            versions += VersionService.get_version_metadata(db, legacy_module.id)
        active_ver = active_version(db, module)

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
                ts_ver = active_version(db, ts_mod)
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
                bmc_ver = active_version(db, bmc_mod)
                if bmc_ver and bmc_ver.created_at > active_ver.created_at:
                    is_stale = True
                    stale_reason = f"Business Model Canvas was updated on {bmc_ver.created_at.strftime('%Y-%m-%d %H:%M')}. Refresh {module_type.replace('_', ' ').title()} to incorporate revised customer segments and value propositions?"
                    stale_source_module = "bmc"

    if active_ver and isinstance(active_ver.data, dict):
        saved_metadata = active_ver.data.get("context_metadata") or {}
        if saved_metadata.get("project_fingerprint") and saved_metadata["project_fingerprint"] != project_fingerprint(project):
            is_stale, stale_source_module = True, "overview"
            stale_reason = "Project details have changed since this version was created. Refresh this section to use the current scope and constraints."
        else:
            _, current_sources = read_project_context(db, project.id, exclude_module=module_type)
            current_by_module = {source["module_type"]: source for source in current_sources}
            for source in saved_metadata.get("source_versions", []):
                current = current_by_module.get(source.get("module_type"))
                if not current or current.get("content_fingerprint") != source.get("content_fingerprint"):
                    is_stale, stale_source_module = True, source.get("module_type")
                    stale_reason = "A source section has changed or was deleted. Review and refresh this section when you are ready."
                    break

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=active_ver.id if active_ver else None,
        active_version_name=active_ver.version_name if active_ver else None,
        active_version_number=active_ver.version_number if active_ver else None,
        data=current_module_data(db, module, active_ver) if active_ver else None,
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
        with project_first_lock(db, project.id):
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
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete {canonical_type.replace('_', ' ')} due to an unexpected internal error."
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
    planning_inputs: dict | None = None,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    if module_type not in DELETABLE_MODULE_TYPES:
        raise HTTPException(status_code=404, detail="Unknown generated module")
    # Unwrap embedded planning_inputs if client sent {"planning_inputs": {...}}
    effective_inputs = planning_inputs
    if isinstance(planning_inputs, dict) and "planning_inputs" in planning_inputs and len(planning_inputs) == 1:
        effective_inputs = planning_inputs["planning_inputs"]

    typed_inputs = None
    if module_type in ("execution_roadmap", "detailed_roadmap"):
        try:
            typed_inputs = RoadmapPlanningRequest.model_validate(effective_inputs or {})
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid roadmap planning inputs: {e}"
            )
    elif module_type == "tech_stack":
        try:
            typed_inputs = TechStackPlanningRequest.model_validate(effective_inputs or {})
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid tech stack planning inputs: {e}"
            )
    elif effective_inputs:
        raise HTTPException(status_code=400, detail="This module does not accept planning inputs")
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

    check_ai_rate_limit(project.user_id)

    new_ver, data_dict = ModuleOrchestrationService.execute_module_generation(
        db=db,
        project=project,
        module=module,
        module_type=module_type,
        planning_inputs=typed_inputs,
        project_dict=proj_info,
    )

    versions = getattr(new_ver, "_cached_versions", None)
    if versions is None:
        with SessionLocal() as q_db:
            versions = VersionService.get_versions(q_db, module.id)

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=new_ver.id,
        active_version_name=new_ver.version_name,
        active_version_number=new_ver.version_number,
        data=new_ver.data,
        versions=[VersionItemResponse.model_validate(v) for v in versions],
        is_stale=False,
        context_metadata=data_dict.get("context_metadata")
    )

@router.post("/{module_type}/accept-update", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def accept_module_update(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Explicitly refresh a stale module using latest cross-module context without mutating other modules."""
    canonical = normalize_module_type(module_type)
    planning = None
    if canonical == "execution_roadmap":
        version = active_version(db, find_module(db, project.id, canonical))
        saved = version.data.get("planning_inputs") if version and isinstance(version.data, dict) else None
        planning = RoadmapPlanningRequest.model_validate(saved) if saved else None
    return generate_module(module_type=canonical, planning_inputs=planning, project=project, db=db)

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

    active_ver = active_version(db, module)
    if not active_ver:
        raise HTTPException(status_code=404, detail="Active version data not found")

    VersionService.assert_version_capacity(db, module)

    t0 = time.time()
    project_id = project.id
    user_id = project.user_id
    module_id = module.id
    curr_data = current_module_data(db, module, active_ver)
    instruction = req.instruction
    proj_info = _get_project_dict(project)
    cross_ctx = read_project_context(db, project_id, exclude_module=module_type)[0]
    saved_inputs = (active_ver.data or {}).get("planning_inputs", {}) if isinstance(active_ver.data, dict) else {}

    check_ai_rate_limit(project.user_id)

    # Decouple: release database connection before calling the external provider
    db.close()

    try:
        new_data, change_summary = ai_service.modify_section(
            module_type=module_type,
            current_data=curr_data,
            instruction=instruction,
            project_info=proj_info,
            cross_module_context=cross_ctx,
        )
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        terminal_provider_error = ai_service._terminal_provider_error_message(e)
        raw_err = str(e)
        err_msg = terminal_provider_error or "An unexpected internal error occurred during module modification."
        err_cat = "provider_error" if terminal_provider_error else ("timeout" if "timeout" in raw_err.lower() else "api_error")
        try:
            with SessionLocal() as telemetry_db:
                record_ai_operation(
                    telemetry_db,
                    user_id=user_id,
                    project_id=project_id,
                    module_type=module_type,
                    operation_type="modify",
                    model_name=settings.GEMINI_MODEL,
                    duration_ms=dur_ms,
                    status="timeout" if "timeout" in raw_err.lower() else "failed",
                    error_category=err_cat,
                    error_message=err_msg,
                    structured_validation_passed=False,
                    persistence_status="failed",
                    is_retryable=terminal_provider_error is None,
                    retry_context={"module_type": module_type, "operation_type": "modify", "instruction": instruction, "planning_inputs": saved_inputs},
                )
                telemetry_db.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Module update failed: {err_msg}",
        ) from e

    if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
        planning = RoadmapPlanningRequest.model_validate(saved_inputs or {})
        new_data = _normalize_roadmap_schedule(new_data, planning)
        new_data["planning_inputs"] = planning.model_dump(mode="json")

    # Validate modified data against schema before persistence (F-09)
    _validate_module_data(module_type, new_data)

    # Save new version and reconcile roadmap tasks in short atomic transaction under project-first lock
    with SessionLocal(expire_on_commit=False) as persist_db:
        p_user = persist_db.query(User).filter(User.id == user_id).first()
        if not p_user or p_user.is_suspended:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is suspended or no longer active."
            )

        p_proj = persist_db.query(Project).filter(Project.id == project_id).first()
        if not p_proj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project was deleted while modification was in progress."
            )
        if p_proj.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project ownership changed or access revoked."
            )

        p_mod = persist_db.query(ModuleContent).filter(
            ModuleContent.id == module_id,
            ModuleContent.project_id == project_id,
        ).first()
        if not p_mod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module was deleted while modification was in progress."
            )

        with project_first_lock(persist_db, project_id, p_mod.id):
            VersionService.assert_version_capacity(persist_db, p_mod)

            if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
                if "tasks" not in new_data or not isinstance(new_data["tasks"], list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Roadmap data must contain an explicit 'tasks' list."
                    )
                canonical_tasks = RoadmapDomainService.canonicalize_incoming_tasks(persist_db, p_proj, new_data["tasks"])
                new_data = dict(new_data)
                new_data["tasks"] = canonical_tasks

            new_ver = VersionService.save_new_version(
                db=persist_db,
                module=p_mod,
                data=new_data,
                change_summary=change_summary,
                commit=False,
            )

            # Reconcile roadmap tasks if roadmap
            if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
                _reconcile_roadmap_tasks(persist_db, p_proj, new_data["tasks"])

            persist_db.commit()
            persist_db.refresh(new_ver)
            versions = VersionService.get_versions(persist_db, p_mod.id)

        dur_ms = int((time.time() - t0) * 1000)
        record_ai_operation(
            persist_db,
            user_id=user_id,
            project_id=project_id,
            module_type=module_type,
            operation_type="modify",
            model_name=settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="success",
            structured_validation_passed=True,
            persistence_status="persisted",
            retry_context={"module_type": module_type, "operation_type": "modify", "instruction": instruction, "planning_inputs": saved_inputs},
        )
        record_analytics_event(
            persist_db,
            user_id=user_id,
            project_id=project_id,
            event_name=f"{module_type}_modified",
        )
        persist_db.commit()

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=new_ver.id,
        active_version_name=new_ver.version_name,
        active_version_number=new_ver.version_number,
        data=new_ver.data,
        versions=[VersionItemResponse.model_validate(v) for v in versions],
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

    project_id = project.id
    user_id = project.user_id
    module_id = module.id
    target_ver_id = req.replace_version_id
    new_ver_name = req.new_version_name
    new_data = req.new_data
    change_summary = req.change_summary
    t0 = time.time()

    # If pending instruction provided, apply it via Gemini AI and validate
    if req.instruction:
        active_ver = active_version(db, module)
        if not active_ver:
            raise HTTPException(status_code=400, detail="No active version data found to apply modification")

        curr_data = current_module_data(db, module, active_ver)
        instruction = req.instruction
        proj_info = _get_project_dict(project)
        cross_ctx = read_project_context(db, project_id, exclude_module=module_type)[0]

        check_ai_rate_limit(project.user_id)

        # Decouple: release database connection before calling the external provider
        db.close()

        try:
            modified_data, summary = ai_service.modify_section(
                module_type=module_type,
                current_data=curr_data,
                instruction=instruction,
                project_info=proj_info,
                cross_module_context=cross_ctx,
            )
            _validate_module_data(module_type, modified_data)
            new_data = modified_data
            change_summary = summary or req.change_summary or f"Applied instruction: {req.instruction[:60]}"
        except Exception as e:
            dur_ms = int((time.time() - t0) * 1000)
            terminal_provider_error = ai_service._terminal_provider_error_message(e)
            err_msg = terminal_provider_error or "An unexpected internal error occurred during conflict resolution."
            try:
                with SessionLocal() as telemetry_db:
                    record_ai_operation(
                        telemetry_db,
                        user_id=user_id,
                        project_id=project_id,
                        module_type=module_type,
                        operation_type="modify",
                        model_name=settings.GEMINI_MODEL,
                        duration_ms=dur_ms,
                        status="failed",
                        error_category="provider_error" if terminal_provider_error else ("validation_error" if "validation" in err_msg.lower() else "api_error"),
                        error_message=err_msg,
                        structured_validation_passed=False,
                        persistence_status="failed",
                        is_retryable=terminal_provider_error is None,
                        retry_context={"module_type": module_type, "operation_type": "modify", "instruction": req.instruction, "replace_version_id": req.replace_version_id},
                    )
                    telemetry_db.commit()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Module update during conflict resolution failed: {err_msg}",
            ) from e
    else:
        db.close()

    if not new_data:
        raise HTTPException(status_code=400, detail="Missing new data or modification instruction for version replacement")

    # Validate replacement payload before persistence (F-09)
    try:
        _validate_module_data(module_type, new_data)
    except HTTPException:
        raise
    except Exception as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation failed for {module_type}: {str(ve)}",
        )

    with SessionLocal(expire_on_commit=False) as persist_db:
        p_user = persist_db.query(User).filter(User.id == user_id).first()
        if not p_user or p_user.is_suspended:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is suspended or no longer active.")
        p_proj = persist_db.query(Project).filter(Project.id == project_id).first()
        if not p_proj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project was deleted while conflict resolution was in progress.")
        if p_proj.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project ownership changed or access revoked.")
        p_mod = persist_db.query(ModuleContent).filter(
            ModuleContent.id == module_id,
            ModuleContent.project_id == project_id,
        ).first()
        if not p_mod:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module was deleted while conflict resolution was in progress.")

        p_target_ver = persist_db.query(ModuleVersion).filter(
            ModuleVersion.id == target_ver_id,
            ModuleVersion.module_content_id == p_mod.id,
        ).first()
        if not p_target_ver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version to replace not found in this module")

        with project_first_lock(persist_db, project_id, p_mod.id):
            if module_type in ("execution_roadmap", "detailed_roadmap"):
                if not isinstance(new_data, dict) or "tasks" not in new_data or not isinstance(new_data["tasks"], list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Roadmap data must contain an explicit 'tasks' list."
                    )
                canonical_tasks = RoadmapDomainService.canonicalize_incoming_tasks(persist_db, p_proj, new_data["tasks"])
                new_data = dict(new_data)
                new_data["tasks"] = canonical_tasks

            replaced_ver = VersionService.resolve_conflict_and_replace(
                db=persist_db,
                module=p_mod,
                replace_version_id=target_ver_id,
                new_data=new_data,
                new_name=new_ver_name,
                change_summary=change_summary,
                commit=False,
            )

            persist_db.commit()
            persist_db.refresh(replaced_ver)
            versions = VersionService.get_versions(persist_db, p_mod.id)

        if req.instruction:
            dur_ms = int((time.time() - t0) * 1000)
            record_ai_operation(
                persist_db,
                user_id=user_id,
                project_id=project_id,
                module_type=module_type,
                operation_type="modify",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="success",
                structured_validation_passed=True,
                persistence_status="persisted",
                retry_context={"module_type": module_type, "operation_type": "modify", "instruction": req.instruction, "replace_version_id": req.replace_version_id},
            )
            persist_db.commit()

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=replaced_ver.id,
        active_version_name=replaced_ver.version_name,
        active_version_number=replaced_ver.version_number,
        data=replaced_ver.data,
        versions=[VersionItemResponse.model_validate(v) for v in versions],
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
    with project_first_lock(db, project.id, module.id):
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
    try:
        with project_first_lock(db, project.id, module.id):
            VersionService.delete_version(db, module, version_id, commit=False)
            db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete version due to an unexpected internal error."
        )
    return {"message": "Version successfully deleted"}

@router.post("/{module_type}/versions/{version_id}/restore", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def restore_version(
    module_type: str,
    version_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module_type = normalize_module_type(module_type)
    module = find_module(db, project.id, module_type)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    try:
        with project_first_lock(db, project.id, module.id):
            new_ver = VersionService.restore_version(db, module, version_id, commit=False)
            db.commit()
            db.refresh(new_ver)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore version due to an unexpected internal error."
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

    if not PDFService.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export service is temporarily unavailable: missing export engine."
        )

    if not module or not module.active_version_id:
        # If overview or default, generate fallback data
        if module_type == "overview":
            mod_data = {"description": project.description, "goals": project.goals, "stage": normalize_business_stage(project.stage)}
        else:
            raise HTTPException(status_code=404, detail="No active version found for this module to export")
    else:
        ver = active_version(db, module)
        if not ver:
            raise HTTPException(status_code=404, detail="Active version content not found")
        mod_data = current_module_data(db, module, ver)

    try:
        pdf_bytes = PDFService.generate_single_module_pdf(proj_dict, module_type, mod_data)
        disposition = format_content_disposition(
            f"{project.name}_{module_type}",
            fallback=f"{module_type}_blueprint"
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": disposition}
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to export module PDF for %s: %s", module_type, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export {module_type} module PDF. Please retry shortly."
        )

