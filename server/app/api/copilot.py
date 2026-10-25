import base64
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models.all_models import Project, CopilotMessage, CopilotOperation, User
from app.schemas.copilot import (
    CopilotChatRequest,
    CopilotMessageResponse,
    CopilotHistoryPageResponse,
    CopilotSendResponse,
    CopilotOperationStatusResponse
)
from app.ai.gemini_service import ai_service
from app.api.deps import get_user_project, verify_csrf
from app.core.business_stage import normalize_business_stage
from app.core.ai_limiter import check_ai_rate_limit
from app.core.config import settings
from app.services.task_graph_validator import project_first_lock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/copilot", tags=["Blueprint Copilot"])


def encode_cursor(project_id: str, dt: datetime, msg_id: str) -> str:
    """Encode created_at timestamp and message ID into an authenticated URL-safe cursor using HMAC-SHA256."""
    payload = f"v1|{project_id}|{dt.isoformat()}|{msg_id}"
    sig = hmac.new(settings.SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    raw = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii")


def decode_cursor(project_id: str, cursor_str: str) -> Tuple[datetime, str]:
    """Decode, authenticate signature, and validate cursor strictly against authorized project_id."""
    if not cursor_str or not isinstance(cursor_str, str) or len(cursor_str) > 512:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor format or length."
        )
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode("ascii")).decode("utf-8")
        parts = raw.split("|")
        if len(parts) != 5 or parts[0] != "v1":
            raise ValueError("Malformed cursor structure.")
        _, c_proj_id, dt_str, msg_id, sig = parts
        if c_proj_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cursor does not belong to the authorized project."
            )
        expected_payload = f"v1|{project_id}|{dt_str}|{msg_id}"
        expected_sig = hmac.new(settings.SESSION_SECRET.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or tampered pagination cursor."
            )
        dt = datetime.fromisoformat(dt_str)
        return dt, msg_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor format."
        ) from e


@router.get("/page", response_model=CopilotHistoryPageResponse)
def get_chat_history_page(
    response: Response,
    before_cursor: Optional[str] = Query(None, description="Cursor: return messages created before this position"),
    limit: int = Query(50, ge=1, le=200, description="Page size (1-200)"),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """
    Retrieve a bounded page of chat history ordered chronologically ascending for display.
    When before_cursor is omitted, returns the latest messages.
    When before_cursor is supplied, returns older messages prior to the cursor.
    Validates cursor strictly against authorized project_id and cryptographic HMAC signature.
    """
    base_query = db.query(CopilotMessage).filter(CopilotMessage.project_id == project.id)
    total_count = base_query.count()

    query = base_query
    if before_cursor:
        _, cursor_id = decode_cursor(project.id, before_cursor)
        cursor_msg = db.query(CopilotMessage).filter(
            CopilotMessage.id == cursor_id,
            CopilotMessage.project_id == project.id
        ).first()
        if not cursor_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cursor message not found in the authorized project."
            )
        query = query.filter(
            (CopilotMessage.created_at < cursor_msg.created_at) |
            ((CopilotMessage.created_at == cursor_msg.created_at) & (CopilotMessage.id < cursor_msg.id))
        )

    # Order newest-first to slice the latest messages before cursor
    rows = query.order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    page_desc = rows[:limit]

    # Reverse into chronological order for display
    messages = list(reversed(page_desc))
    next_cursor = encode_cursor(project.id, page_desc[-1].created_at, page_desc[-1].id) if (page_desc and has_more) else None

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Has-More"] = "true" if has_more else "false"

    return {
        "messages": messages,
        "has_more": has_more,
        "before_cursor": next_cursor,
        "total_count": total_count
    }


@router.get("/operations/{client_msg_id}", response_model=CopilotOperationStatusResponse)
def get_operation_status(
    client_msg_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Check the status of an idempotent chat operation (e.g. after a client-side timeout)."""
    op = db.query(CopilotOperation).filter(
        CopilotOperation.project_id == project.id,
        CopilotOperation.client_msg_id == client_msg_id
    ).first()
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation '{client_msg_id}' not found for this project."
        )
    if op.user_id != project.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation belongs to a different user."
        )

    user_msg = db.get(CopilotMessage, op.user_message_id) if op.user_message_id else None
    assistant_msg = db.get(CopilotMessage, op.assistant_message_id) if op.assistant_message_id else None

    return CopilotOperationStatusResponse(
        client_msg_id=op.client_msg_id,
        status=op.status,
        user_message=CopilotMessageResponse.model_validate(user_msg) if user_msg else None,
        assistant_message=CopilotMessageResponse.model_validate(assistant_msg) if assistant_msg else None,
        error_detail=op.error_detail
    )


@router.get("", response_model=List[CopilotMessageResponse])
def get_chat_history(
    response: Response,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages to return (1-200)"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order by creation time ('asc' or 'desc')"),
    before_id: Optional[str] = Query(None, description="Cursor: return messages created before this message ID"),
    before_cursor: Optional[str] = Query(None, description="Encoded cursor for older messages"),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    base_query = db.query(CopilotMessage).filter(CopilotMessage.project_id == project.id)
    total_count = base_query.count()

    query = base_query
    if before_cursor:
        _, c_id = decode_cursor(project.id, before_cursor)
        before_id = c_id

    if before_id:
        target_msg = db.query(CopilotMessage).filter(
            CopilotMessage.id == before_id,
            CopilotMessage.project_id == project.id
        ).first()
        if not target_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cursor does not belong to the authorized project."
            )
        query = query.filter(
            (CopilotMessage.created_at < target_msg.created_at) |
            ((CopilotMessage.created_at == target_msg.created_at) & (CopilotMessage.id < target_msg.id))
        )

    if order == "desc":
        query = query.order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc())
    else:
        if before_id:
            query = query.order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc())
        else:
            query = query.order_by(CopilotMessage.created_at.asc(), CopilotMessage.id.asc())

    messages = query.offset(offset).limit(limit).all()
    if before_id and order == "asc":
        messages = list(reversed(messages))

    has_more = (offset + len(messages)) < total_count

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Has-More"] = "true" if has_more else "false"
    return messages


@router.post("", response_model=CopilotSendResponse, dependencies=[Depends(verify_csrf)])
def send_chat_message(
    req: CopilotChatRequest,
    response: Response,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    check_ai_rate_limit(project.user_id)

    msg_text = req.message.strip()
    if not msg_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")
    if len(msg_text) > 4000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message exceeds maximum allowed length of 4000 characters.")

    client_msg_id = (req.client_msg_id or "").strip() or None
    msg_hash = hashlib.sha256(msg_text.encode("utf-8")).hexdigest()

    user_msg: Optional[CopilotMessage] = None
    operation_to_update_id: Optional[str] = None

    if client_msg_id:
        with project_first_lock(db, project.id):
            existing_op = db.query(CopilotOperation).filter(
                CopilotOperation.project_id == project.id,
                CopilotOperation.client_msg_id == client_msg_id
            ).first()

            if existing_op:
                if existing_op.user_id != project.user_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this operation.")
                if existing_op.message_hash != msg_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Same client operation ID submitted with different message payload."
                    )
                if existing_op.status == "completed":
                    u_msg = db.get(CopilotMessage, existing_op.user_message_id) if existing_op.user_message_id else None
                    a_msg = db.get(CopilotMessage, existing_op.assistant_message_id) if existing_op.assistant_message_id else None
                    if u_msg and a_msg:
                        response.headers["X-User-Message-ID"] = str(u_msg.id)
                        response.headers["X-Assistant-Message-ID"] = str(a_msg.id)
                        return CopilotSendResponse(
                            id=a_msg.id,
                            role=a_msg.role,
                            content=a_msg.content,
                            created_at=a_msg.created_at,
                            user_message=CopilotMessageResponse.model_validate(u_msg),
                            assistant_message=CopilotMessageResponse.model_validate(a_msg),
                            operation_status="completed",
                            client_msg_id=client_msg_id
                        )

                if existing_op.status == "pending":
                    now = datetime.now(timezone.utc)
                    op_created = existing_op.created_at
                    if op_created.tzinfo is None:
                        op_created = op_created.replace(tzinfo=timezone.utc)
                    elapsed = (now - op_created).total_seconds()
                    if elapsed < 120.0:
                        u_msg = db.query(CopilotMessage).get(existing_op.user_message_id) if existing_op.user_message_id else None
                        if u_msg:
                            response.headers["X-User-Message-ID"] = str(u_msg.id)
                            return CopilotSendResponse(
                                id=u_msg.id,
                                role="user",
                                content=u_msg.content,
                                created_at=u_msg.created_at,
                                user_message=CopilotMessageResponse.model_validate(u_msg),
                                assistant_message=None,
                                operation_status="pending",
                                client_msg_id=client_msg_id
                            )

                # If failed or stale pending (> 120s), recover! Reuse existing saved user message
                if existing_op.user_message_id:
                    user_msg = db.query(CopilotMessage).get(existing_op.user_message_id)
                if not user_msg:
                    user_msg = CopilotMessage(
                        project_id=project.id,
                        role="user",
                        content=msg_text
                    )
                    db.add(user_msg)
                    db.flush()
                    existing_op.user_message_id = user_msg.id

                existing_op.status = "pending"
                existing_op.updated_at = datetime.now(timezone.utc)
                db.commit()
                operation_to_update_id = existing_op.id
            else:
                user_msg = CopilotMessage(
                    project_id=project.id,
                    role="user",
                    content=msg_text
                )
                db.add(user_msg)
                db.flush()
                new_op = CopilotOperation(
                    project_id=project.id,
                    user_id=project.user_id,
                    client_msg_id=client_msg_id,
                    message_hash=msg_hash,
                    status="pending",
                    user_message_id=user_msg.id
                )
                db.add(new_op)
                db.commit()
                operation_to_update_id = new_op.id
    else:
        user_msg = CopilotMessage(
            project_id=project.id,
            role="user",
            content=msg_text
        )
        db.add(user_msg)
        db.commit()

    response.headers["X-User-Message-ID"] = str(user_msg.id)

    # Context character budget: max 16,000 characters of recent history
    # Drop oldest messages first when exceeding budget; NEVER accept oversized first message
    MAX_HISTORY_CHARS = 16000
    raw_recent = (
        db.query(CopilotMessage)
        .filter(CopilotMessage.project_id == project.id, CopilotMessage.id != user_msg.id)
        .order_by(CopilotMessage.created_at.desc(), CopilotMessage.id.desc())
        .limit(20)
        .all()
    )

    budgeted_messages = []
    current_chars = 0
    for m in raw_recent:
        content_len = len(m.content or "")
        if current_chars + content_len > MAX_HISTORY_CHARS:
            break
        budgeted_messages.append(m)
        current_chars += content_len

    assert current_chars <= MAX_HISTORY_CHARS

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
            reply_text = ai_service.chat_copilot(
                proj_info, history_dicts, msg_text, cross_module_context=active_module_summaries
            )

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
            persist_db.flush()

            if operation_to_update_id:
                op_rec = persist_db.get(CopilotOperation, operation_to_update_id)
                if op_rec:
                    op_rec.status = "completed"
                    op_rec.assistant_message_id = assistant_msg.id
                    op_rec.updated_at = datetime.now(timezone.utc)

            persist_db.commit()
            persist_db.refresh(assistant_msg)

            p_user_msg = persist_db.get(CopilotMessage, user_msg.id)

            response.headers["X-Assistant-Message-ID"] = str(assistant_msg.id)
            return CopilotSendResponse(
                id=assistant_msg.id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                created_at=assistant_msg.created_at,
                user_message=CopilotMessageResponse.model_validate(p_user_msg or user_msg),
                assistant_message=CopilotMessageResponse.model_validate(assistant_msg),
                operation_status="completed",
                client_msg_id=client_msg_id
            )
    except HTTPException as http_exc:
        if operation_to_update_id:
            try:
                with SessionLocal() as fail_db:
                    op_rec = fail_db.query(CopilotOperation).get(operation_to_update_id)
                    if op_rec:
                        op_rec.status = "failed"
                        op_rec.error_detail = str(http_exc.detail)
                        fail_db.commit()
            except Exception:
                pass
        raise
    except Exception as e:
        logger.error("Planning Copilot error: %s", type(e).__name__)
        if operation_to_update_id:
            try:
                with SessionLocal() as fail_db:
                    op_rec = fail_db.query(CopilotOperation).get(operation_to_update_id)
                    if op_rec:
                        op_rec.status = "failed"
                        op_rec.error_detail = type(e).__name__
                        fail_db.commit()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Planning Copilot failed to process the request. Please retry shortly."
        ) from e
