import re
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, ModuleContent, ModuleVersion, RoadmapTask
from app.services.pdf_service import PDFService
from app.api.deps import get_user_project
from app.core.telemetry import record_analytics_event
from app.core.business_stage import normalize_business_stage
from app.core.module_types import normalize_module_type
from app.services.project_context_service import read_project_context, find_module, active_version, current_module_data

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
        "stage": normalize_business_stage(project.stage),
        "industry": project.industry,
        "description": project.description,
        "target_customers": project.target_customers,
        "goals": project.goals,
        "budget": project.budget,
        "existing_stack": project.existing_stack
    }

    modules_data, _ = read_project_context(db, project.id)

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
        record_analytics_event(db, user_id=project.user_id, project_id=project.id, event_name="export_pdf")
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
        "stage": normalize_business_stage(project.stage),
        "industry": project.industry
    }

    module_type = normalize_module_type(module_type)
    module = find_module(db, project.id, module_type)
    ver = active_version(db, module)
    if not module or not ver:
        raise HTTPException(status_code=404, detail="No active version found for this module to export")
    module_data = current_module_data(db, module, ver)

    try:
        pdf_bytes = PDFService.generate_single_module_pdf(proj_dict, module_type, module_data)
        filename = f"{_slugify(project.name)}_{module_type}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export module PDF: {str(e)}")
