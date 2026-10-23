from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, CopilotMessage, ModuleContent, ModuleVersion
from app.schemas.copilot import CopilotChatRequest, CopilotMessageResponse
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.business_stage import normalize_business_stage

router = APIRouter(prefix="/projects/{project_id}/copilot", tags=["Blueprint Copilot"])

@router.get("", response_model=List[CopilotMessageResponse])
def get_chat_history(
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    messages = db.query(CopilotMessage).filter(
        CopilotMessage.project_id == project.id
    ).order_by(CopilotMessage.created_at.asc()).all()
    return messages

@router.post("", response_model=CopilotMessageResponse, dependencies=[Depends(verify_csrf)])
def send_chat_message(
    req: CopilotChatRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    # Save user message
    user_msg = CopilotMessage(
        project_id=project.id,
        role="user",
        content=req.message
    )
    db.add(user_msg)
    db.commit()

    # Retrieve history for context
    past_messages = db.query(CopilotMessage).filter(
        CopilotMessage.project_id == project.id
    ).order_by(CopilotMessage.created_at.asc()).all()

    history_dicts = [{"role": m.role, "content": m.content} for m in past_messages]

    # Read authorized snapshots without changing any source module.
    from app.services.project_context_service import read_project_context
    active_module_summaries, context_sources = read_project_context(db, project.id)

    proj_info = {
        "name": project.name,
        "stage": normalize_business_stage(project.stage),
        "industry": project.industry,
        "description": project.description,
        "goals": project.goals,
        "budget": project.budget,
        "business_context": project.business_context,
        "existing_stack": project.existing_stack,
        "target_customers": project.target_customers,
        "generated_modules": list(active_module_summaries.keys()),
        "context_sources": context_sources
    }

    try:
        from app.core.diagnostics import record_stage
        with record_stage("provider_call"):
            reply_text = ai_service.chat_copilot(proj_info, history_dicts, req.message, cross_module_context=active_module_summaries)
        assistant_msg = CopilotMessage(
            project_id=project.id,
            role="assistant",
            content=reply_text
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)
        return assistant_msg
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Planning Copilot error: {str(e)}"
        )
