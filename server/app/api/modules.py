import time
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask
from app.schemas.modules import (
    ModuleDetailResponse, VersionItemResponse, VersionRenameRequest,
    VersionConflictResolveRequest, SectionModifyRequest,
    BMCData, TechStackData, IdeaValidatorData, MarketResearchData
)
from app.services.version_service import VersionService
from app.services.pdf_service import PDFService
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.telemetry import record_ai_operation, record_analytics_event

router = APIRouter(prefix="/projects/{project_id}/modules", tags=["Modules & Version Control"])

ALLOWED_CHAT_MODULES = {"overview", "bmc", "tech_stack", "execution_roadmap", "detailed_roadmap"}
DISALLOWED_CHAT_MODULES = {"idea_validator", "market_research"}

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

def _reconcile_roadmap_tasks(db: Session, project: Project, tasks_data: List[Dict[str, Any]]):
    existing_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
    existing_by_code = {t.task_code: t for t in existing_tasks}

    base_date_str = project.created_at.strftime("%Y-%m-%d") if project.created_at else "2026-10-01"

    for idx, t in enumerate(tasks_data):
        code = t.get("task_code") or f"TSK-{str(idx+1).zfill(2)}"
        s_date = t.get("start_date") or base_date_str
        e_date = t.get("end_date") or s_date
        if e_date < s_date:
            e_date = s_date

        if code in existing_by_code:
            cur = existing_by_code[code]
            # Preserve user edits if ongoing or finished
            if cur.status not in ("Ongoing", "In Progress", "Finished"):
                raw_st = t.get("status", "Pending")
                cur.status = "Ongoing" if raw_st == "In Progress" else raw_st
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
            cur.order_index = idx
        else:
            raw_st = t.get("status", "Pending")
            st_val = "Ongoing" if raw_st == "In Progress" else raw_st
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
                order_index=idx
            )
            db.add(new_task)
    db.commit()

def _get_project_dict(project: Project) -> Dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "stage": project.stage,
        "description": project.description,
        "industry": project.industry,
        "target_customers": project.target_customers,
        "goals": project.goals,
        "business_context": project.business_context,
        "budget": project.budget,
        "existing_stack": project.existing_stack or {}
    }

@router.get("/{module_type}", response_model=ModuleDetailResponse)
def get_module(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module = VersionService.get_or_create_module(db, project.id, module_type)
    versions = VersionService.get_versions(db, module.id)

    active_ver = None
    if module.active_version_id:
        active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
    if not active_ver and versions:
        active_ver = versions[-1]
        module.active_version_id = active_ver.id
        db.commit()

    return ModuleDetailResponse(
        module_type=module_type,
        active_version_id=active_ver.id if active_ver else None,
        active_version_name=active_ver.version_name if active_ver else None,
        active_version_number=active_ver.version_number if active_ver else None,
        data=active_ver.data if active_ver else None,
        versions=[VersionItemResponse.model_validate(v) for v in versions]
    )

@router.post("/{module_type}/generate", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def generate_module(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Generates structured content for the specified module using Gemini AI and creates a version."""
    proj_info = _get_project_dict(project)
    module = VersionService.get_or_create_module(db, project.id, module_type)
    t0 = time.time()

    try:
        if module_type == "bmc":
            generated = ai_service.generate_bmc(proj_info)
            data_dict = generated.model_dump()
        elif module_type == "tech_stack":
            generated = ai_service.generate_tech_stack(proj_info)
            data_dict = generated.model_dump()
        elif module_type == "idea_validator":
            generated = ai_service.generate_idea_validator(proj_info)
            data_dict = generated.model_dump()
        elif module_type == "market_research":
            generated = ai_service.generate_market_research(proj_info)
            data_dict = generated.model_dump()
        elif module_type in ("execution_roadmap", "detailed_roadmap"):
            roadmap_raw = ai_service.generate_roadmap(proj_info)
            data_dict = roadmap_raw

            tasks_data = roadmap_raw.get("tasks", [])
            if tasks_data:
                _reconcile_roadmap_tasks(db, project, tasks_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported module type: {module_type}")

        # Save new version (enforcing 5-version maximum)
        new_ver = VersionService.save_new_version(
            db=db,
            module=module,
            data=data_dict,
            change_summary="Initial AI generation via Gemini"
        )

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
            versions=[VersionItemResponse.model_validate(v) for v in versions]
        )

    except HTTPException:
        raise
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        err_msg = str(e)
        err_cat = "timeout" if "timeout" in err_msg.lower() else ("parse_error" if "json" in err_msg.lower() or "validation" in err_msg.lower() else "api_error")
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
            is_retryable=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini generation failed: {str(e)}"
        )

@router.post("/{module_type}/modify", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def modify_module_with_ai(
    module_type: str,
    req: SectionModifyRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
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

    module = VersionService.get_or_create_module(db, project.id, module_type)
    if not module.active_version_id:
        raise HTTPException(
            status_code=400,
            detail="Module has no active version to modify. Please generate content first."
        )

    active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
    if not active_ver:
        raise HTTPException(status_code=404, detail="Active version data not found")

    t0 = time.time()
    try:
        new_data, change_summary = ai_service.modify_section(
            module_type=module_type,
            current_data=active_ver.data,
            instruction=req.instruction
        )

        new_ver = VersionService.save_new_version(
            db=db,
            module=module,
            data=new_data,
            change_summary=change_summary
        )

        # Reconcile roadmap tasks if roadmap
        if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
            tasks_data = new_data.get("tasks", [])
            if tasks_data:
                _reconcile_roadmap_tasks(db, project, tasks_data)

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
        err_msg = str(e)
        err_cat = "timeout" if "timeout" in err_msg.lower() else "api_error"
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
            is_retryable=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI modification failed: {str(e)}"
        )

@router.post("/{module_type}/resolve-conflict", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def resolve_version_conflict(
    module_type: str,
    req: VersionConflictResolveRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """User-confirmed replacement of an existing version when the 5-version limit is reached."""
    module = VersionService.get_or_create_module(db, project.id, module_type)

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
            record_ai_operation(
                db,
                user_id=project.user_id,
                project_id=project.id,
                module_type=module_type,
                operation_type="modify",
                model_name=settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="failed",
                error_category="validation_error" if "validation" in str(e).lower() else "api_error",
                error_message=str(e),
                structured_validation_passed=False,
                persistence_status="failed",
                is_retryable=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI modification during conflict resolution failed: {str(e)}"
            )

    if not new_data:
        raise HTTPException(status_code=400, detail="Missing new data or modification instruction for version replacement")

    replaced_ver = VersionService.resolve_conflict_and_replace(
        db=db,
        module=module,
        replace_version_id=req.replace_version_id,
        new_data=new_data,
        new_name=req.new_version_name,
        change_summary=change_summary
    )

    if module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(new_data, dict):
        tasks_data = new_data.get("tasks", [])
        if tasks_data:
            _reconcile_roadmap_tasks(db, project, tasks_data)

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
    module = VersionService.get_or_create_module(db, project.id, module_type)
    renamed = VersionService.rename_version(db, module, version_id, req.version_name)
    return {"message": "Version renamed successfully", "version_name": renamed.version_name}

@router.delete("/{module_type}/versions/{version_id}", dependencies=[Depends(verify_csrf)])
def delete_version(
    module_type: str,
    version_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module = VersionService.get_or_create_module(db, project.id, module_type)
    VersionService.delete_version(db, module, version_id)
    return {"message": "Version successfully deleted"}

@router.post("/{module_type}/versions/{version_id}/restore", response_model=ModuleDetailResponse, dependencies=[Depends(verify_csrf)])
def restore_version(
    module_type: str,
    version_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    module = VersionService.get_or_create_module(db, project.id, module_type)
    new_ver = VersionService.restore_version(db, module, version_id)
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
    proj_dict = _get_project_dict(project)
    module = VersionService.get_or_create_module(db, project.id, module_type)

    if not module or not module.active_version_id:
        # If overview or default, generate fallback data
        if module_type == "overview":
            mod_data = {"description": project.description, "goals": project.goals, "stage": project.stage}
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

