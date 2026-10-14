from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask
from app.schemas.modules import (
    ModuleDetailResponse, VersionItemResponse, VersionRenameRequest,
    VersionConflictResolveRequest, SectionModifyRequest
)
from app.services.version_service import VersionService
from app.services.pdf_service import PDFService
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf

router = APIRouter(prefix="/projects/{project_id}/modules", tags=["Modules & Version Control"])

ALLOWED_CHAT_MODULES = {"overview", "bmc", "tech_stack", "execution_roadmap", "detailed_roadmap"}
DISALLOWED_CHAT_MODULES = {"idea_validator", "market_research"}

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

            # Also populate or sync the RoadmapTask records in the database
            tasks_data = roadmap_raw.get("tasks", [])
            # If no tasks exist yet, insert them
            existing_count = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).count()
            if existing_count == 0:
                for idx, t in enumerate(tasks_data):
                    task = RoadmapTask(
                        project_id=project.id,
                        task_code=t.get("task_code", f"TSK-0{idx+1}"),
                        phase=t.get("phase", "Planning & Research"),
                        title=t.get("title", f"Task {idx+1}"),
                        description=t.get("description", ""),
                        timeline=t.get("timeline", "30-day"),
                        start_date=t.get("start_date", "2026-10-01"),
                        end_date=t.get("end_date", "2026-10-15"),
                        priority=t.get("priority", "Medium"),
                        status=t.get("status", "Pending"),
                        dependencies=t.get("dependencies", []),
                        deliverables=t.get("deliverables", ""),
                        effort=t.get("effort", "1 week"),
                        order_index=idx
                    )
                    db.add(task)
                db.commit()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported module type: {module_type}")

        # Save new version (enforcing 5-version maximum)
        new_ver = VersionService.save_new_version(
            db=db,
            module=module,
            data=data_dict,
            change_summary="Initial AI generation via Gemini"
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
    replaced_ver = VersionService.resolve_conflict_and_replace(
        db=db,
        module=module,
        replace_version_id=req.replace_version_id,
        new_data=req.new_data,
        new_name=req.new_version_name,
        change_summary=req.change_summary
    )

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
    renamed = VersionService.rename_version(db, version_id, req.version_name)
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

