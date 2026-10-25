import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models.all_models import Project, CopilotMessage, User
from app.schemas.copilot import CopilotChatRequest, CopilotMessageResponse
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.business_stage import normalize_business_stage
from app.core.ai_limiter import check_ai_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/copilot", tags=["Blueprint Copilot"])

@router.get("", response_model=List[CopilotMessageResponse])
def get_chat_history(
    response: Response,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages to return (1-200)"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order by creation time ('asc' or 'desc')"),
    before_id: Optional[str] = Query(None, description="Cursor: return messages created before this message ID"),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    base_query = db.query(CopilotMessage).filter(CopilotMessage.project_id == project.id)
    total_count = base_query.count()

    query = base_query
    if before_id:
        target_msg = db.query(CopilotMessage).filter(
            CopilotMessage.id == before_id,
            CopilotMessage.project_id == project.id
        ).first()
        if target_msg:
            if order == "desc":
                query = query.filter(
                    (CopilotMessage.created_at < target_msg.created_at) |
                    ((CopilotMessage.created_at == target_msg.created_at) & (CopilotMessage.id < target_msg.id))
                )
            else:
                query = query.filter(
                    (CopilotMessage.created_at > target_msg.created_at) |
                    ((CopilotMessage.created_at == target_msg.created_at) & (CopilotMessage.id > target_msg.id))
                )

    if order == "desc":
        query = query.order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc())
    else:
        query = query.order_by(CopilotMessage.created_at.asc(), CopilotMessage.id.asc())

    messages = query.offset(offset).limit(limit).all()
    has_more = (offset + len(messages)) < total_count

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Has-More"] = "true" if has_more else "false"
    return messages

@router.post("", response_model=CopilotMessageResponse, dependencies=[Depends(verify_csrf)])
def send_chat_message(
    req: CopilotChatRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    check_ai_rate_limit(project.user_id)

    # Save user message
    user_msg = CopilotMessage(
        project_id=project.id,
        role="user",
        content=req.message
    )
    db.add(user_msg)
    db.commit()

    # Retrieve bounded recent history for provider context (independently of stored history)
    # Query up to 20 recent messages with stable tie-breaker
    raw_recent = (
        db.query(CopilotMessage)
        .filter(CopilotMessage.project_id == project.id, CopilotMessage.id != user_msg.id)
        .order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc())
        .limit(20)
        .all()
    )

    # Context character budget: max 16,000 characters of recent history
    # Drop oldest messages first when exceeding budget, keeping newest context intact
    MAX_HISTORY_CHARS = 16000
    budgeted_messages = []
    current_chars = 0
    for m in raw_recent:
        content_len = len(m.content or "")
        if current_chars + content_len > MAX_HISTORY_CHARS and budgeted_messages:
            break
        budgeted_messages.append(m)
        current_chars += content_len

    budgeted_messages.reverse()
    history_dicts = [{"role": m.role, "content": m.content} for m in budgeted_messages]

    # Read authorized snapshots without changing any source module.
    from app.services.project_context_service import read_project_context
    active_module_summaries, context_sources = read_project_context(db, project.id)

    project_id = project.id
    user_id = project.user_id
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

    # Decouple: release database connection before calling the external provider
    db.close()

    try:
        from app.core.diagnostics import record_stage
        with record_stage("provider_call"):
            reply_text = ai_service.chat_copilot(proj_info, history_dicts, req.message, cross_module_context=active_module_summaries)

        with SessionLocal(expire_on_commit=False) as persist_db:
            p_user = persist_db.query(User).filter(User.id == user_id).first()
            if not p_user or p_user.is_suspended:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is suspended or no longer active.")
            p_proj = persist_db.query(Project).filter(Project.id == project_id).first()
            if not p_proj:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project was deleted while copilot was responding.")
            if p_proj.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project ownership changed or access revoked.")

            assistant_msg = CopilotMessage(
                project_id=project_id,
                role="assistant",
                content=reply_text
            )
            persist_db.add(assistant_msg)
            persist_db.commit()
            persist_db.refresh(assistant_msg)
            return assistant_msg
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Planning Copilot error: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Planning Copilot failed to process the request. Please retry shortly."
        ) from e
