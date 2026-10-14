import re
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask
from app.services.pdf_service import PDFService
from app.api.deps import get_user_project

router = APIRouter(prefix="/projects/{project_id}/export", tags=["Exports"])

def _slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)

@router.get("/pdf")
def export_full_project_pdf(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """
    Exports a consolidated multi-page PDF covering all active modules.
    Explicitly excludes Copilot messages, version history, and audit records.
    """
    proj_dict = {
        "name": project.name,
        "stage": project.stage,
        "industry": project.industry,
        "description": project.description,
        "target_customers": project.target_customers,
        "goals": project.goals,
        "budget": project.budget,
        "existing_stack": project.existing_stack
    }

    # Fetch active versions of all generated modules
    modules = db.query(ModuleContent).filter(ModuleContent.project_id == project.id).all()
    modules_data = {}
    for m in modules:
        if m.active_version_id:
            ver = db.query(ModuleVersion).filter(ModuleVersion.id == m.active_version_id).first()
            if ver:
                modules_data[m.module_type] = ver.data

    # Fetch tasks
    tasks = db.query(RoadmapTask).filter(
        RoadmapTask.project_id == project.id
    ).order_by(RoadmapTask.order_index.asc()).all()

    tasks_list = [
        {
            "task_code": t.task_code,
            "phase": t.phase,
            "title": t.title,
            "timeline": t.timeline,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "priority": t.priority,
            "status": t.status,
            "deliverables": t.deliverables
        }
        for t in tasks
    ]

    try:
        pdf_bytes = PDFService.generate_full_project_pdf(proj_dict, modules_data, tasks_list)
        filename = f"{_slugify(project.name)}_enterprise_blueprint.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate project PDF: {str(e)}")

@router.get("/modules/{module_type}/pdf")
def export_module_pdf(
    module_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Exports a dedicated PDF for a single specified module."""
    proj_dict = {
        "name": project.name,
        "stage": project.stage,
        "industry": project.industry
    }

    module = db.query(ModuleContent).filter(
        ModuleContent.project_id == project.id,
        ModuleContent.module_type == module_type
    ).first()

    if not module or not module.active_version_id:
        raise HTTPException(status_code=404, detail="No active version found for this module to export")

    ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
    if not ver:
        raise HTTPException(status_code=404, detail="Active version content not found")

    try:
        pdf_bytes = PDFService.generate_single_module_pdf(proj_dict, module_type, ver.data)
        filename = f"{_slugify(project.name)}_{module_type}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export module PDF: {str(e)}")
