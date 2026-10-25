from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, case
from app.db.session import get_db, SessionLocal
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, AIOperation, AuditLog, gen_id
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.config import settings
from app.core.telemetry import record_ai_operation, record_audit_log
from app.core.business_stage import normalize_business_stage

router = APIRouter(prefix="/ai-operations", tags=["Admin AI Operations"])

@router.get("")
def list_ai_operations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    module: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(all|success|failed|timeout|retried)$"),
    error_category: Optional[str] = None,
    request_id: Optional[str] = None,
    project_id: Optional[str] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|duration_ms|module_type)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_admin: User = Depends(require_permission("view_ai_ops")),
    db: Session = Depends(get_db)
):
    query = db.query(AIOperation)

    if module and module != "all":
        query = query.filter(AIOperation.module_type == module)

    if status and status != "all":
        query = query.filter(AIOperation.status == status)

    if error_category and error_category != "all":
        query = query.filter(AIOperation.error_category == error_category)

    if request_id:
        query = query.filter(AIOperation.request_id.ilike(f"%{request_id.strip()}%"))

    if project_id:
        query = query.filter(AIOperation.project_id == project_id.strip())

    total = query.count()

    order_col = getattr(AIOperation, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(asc(order_col))

    offset = (page - 1) * limit
    ops = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "items": [
            {
                "id": op.id,
                "request_id": op.request_id,
                "user_id": op.user_id,
                "project_id": op.project_id,
                "module_type": op.module_type,
                "operation_type": op.operation_type,
                "model_name": op.model_name,
                "duration_ms": op.duration_ms,
                "status": op.status,
                "retry_count": op.retry_count,
                "error_category": op.error_category,
                "error_message": op.error_message,
                "structured_validation_passed": op.structured_validation_passed,
                "persistence_status": op.persistence_status,
                "is_retryable": op.is_retryable,
                "retry_of_id": op.retry_of_id,
                "created_at": op.created_at.isoformat()
            }
            for op in ops
        ]
    }

@router.get("/stats")
def get_ai_operations_stats(
    current_admin: User = Depends(require_permission("view_ai_ops")),
    db: Session = Depends(get_db)
):
    total = db.query(func.count(AIOperation.id)).scalar() or 0
    success_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status == "success").scalar() or 0
    failed_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status.in_(["failed", "timeout"])).scalar() or 0
    timeout_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status == "timeout").scalar() or 0
    retried_count = db.query(func.count(AIOperation.id)).filter(AIOperation.retry_count > 0).scalar() or 0

    success_rate = round((success_count / total * 100), 1) if total > 0 else 0.0
    failure_rate = round((failed_count / total * 100), 1) if total > 0 else 0.0

    durations = [op.duration_ms for op in db.query(AIOperation.duration_ms).filter(AIOperation.duration_ms != None).all()]
    if durations:
        durations.sort()
        n = len(durations)
        median_latency = durations[n // 2]
        p95_latency = durations[min(int(0.95 * n), n - 1)]
    else:
        median_latency = 0
        p95_latency = 0

    # Error categories breakdown
    err_rows = db.query(
        AIOperation.error_category, func.count(AIOperation.id)
    ).filter(AIOperation.error_category != None).group_by(AIOperation.error_category).all()
    error_categories = {cat: count for cat, count in err_rows}

    # Module breakdown
    mod_rows = db.query(
        AIOperation.module_type,
        func.count(AIOperation.id).label("total"),
        func.sum(case((AIOperation.status == "success", 1), else_=0)).label("success"),
        func.avg(AIOperation.duration_ms).label("avg_dur")
    ).group_by(AIOperation.module_type).all()

    module_performance = [
        {
            "module_type": r.module_type,
            "total": r.total,
            "success": int(r.success or 0),
            "success_rate": round(int(r.success or 0) / r.total * 100, 1) if r.total > 0 else None,
            "avg_duration_ms": round(float(r.avg_dur or 0), 0)
        }
        for r in mod_rows
    ]

    return {
        "total_operations": total,
        "successful_operations": success_count,
        "failed_operations": failed_count,
        "timeout_operations": timeout_count,
        "retried_operations": retried_count,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "median_latency_ms": median_latency,
        "p95_latency_ms": p95_latency,
        "configured_model": settings.GEMINI_MODEL,
        "error_categories": error_categories,
        "module_performance": module_performance
    }

@router.get("/quality")
def get_ai_quality_stats(
    current_admin: User = Depends(require_permission("view_ai_ops")),
    db: Session = Depends(get_db)
):
    total = db.query(func.count(AIOperation.id)).scalar() or 0
    passed_validation = db.query(func.count(AIOperation.id)).filter(
        AIOperation.structured_validation_passed == True
    ).scalar() or 0
    parse_errors = db.query(func.count(AIOperation.id)).filter(
        AIOperation.error_category == "parse_error"
    ).scalar() or 0
    persistence_failures = db.query(func.count(AIOperation.id)).filter(
        AIOperation.persistence_status == "failed"
    ).scalar() or 0

    validation_rate = round(passed_validation / total * 100, 1) if total > 0 else 100.0

    return {
        "total_evaluated_operations": total,
        "structured_validation_passed": passed_validation,
        "structured_validation_rate": validation_rate,
        "parse_failures": parse_errors,
        "persistence_failures": persistence_failures
    }

@router.post("/{operation_id}/retry")
def retry_failed_operation(
    operation_id: str,
    current_admin: User = Depends(require_permission("retry_ai_ops")),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """
    Genuine administrative retry of an eligible failed AI operation.
    Enforces least-privilege role boundary, project existence, real AI execution, and audit trail.
    """

    op = db.query(AIOperation).filter(AIOperation.id == operation_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operation record not found")

    if op.status == "success":
        raise HTTPException(status_code=400, detail="Cannot retry an already successful operation")

    # Verify genuine project context exists; never create a synthetic project
    if not op.project_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry operation: original operation has no associated project context."
        )

    proj = db.query(Project).filter(Project.id == op.project_id).first()
    if not proj:
        raise HTTPException(
            status_code=400,
            detail="Cannot retry operation: original project no longer exists."
        )

    if op.is_retryable is False:
        raise HTTPException(
            status_code=400,
            detail="Operation is marked as non-retryable."
        )

    if op.retry_count and op.retry_count >= 3:
        raise HTTPException(
            status_code=400,
            detail="Maximum retry threshold reached for this operation."
        )

    # Check for existing successful retry
    existing_retry = db.query(AIOperation).filter(
        AIOperation.retry_of_id == op.id,
        AIOperation.status == "success"
    ).first()
    if existing_retry:
        raise HTTPException(
            status_code=400,
            detail=f"This operation was already successfully recovered by retry ID: {existing_retry.id}"
        )

    from app.ai.gemini_service import ai_service
    from app.services.version_service import VersionService
    import time
    import copy

    admin_id = current_admin.id
    admin_username = current_admin.username
    op_id = op.id
    op_user_id = op.user_id
    op_project_id = op.project_id
    op_module_type = op.module_type
    op_operation_type = op.operation_type
    op_model_name = op.model_name
    op_retry_count = op.retry_count

    proj_info = {
        "id": proj.id,
        "name": proj.name,
        "stage": normalize_business_stage(proj.stage),
        "description": proj.description,
        "industry": proj.industry,
        "target_customers": proj.target_customers,
        "goals": proj.goals,
        "business_context": proj.business_context,
        "budget": proj.budget,
        "existing_stack": proj.existing_stack or {}
    }

    module = VersionService.get_or_create_module(db, proj.id, op_module_type)
    module_id = module.id
    VersionService.assert_version_capacity(db, module)

    active_ver_data = None
    if op_operation_type == "modify":
        active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
        if not active_ver or not active_ver.data:
            raise HTTPException(status_code=400, detail="Active version data not available to modify")
        active_ver_data = copy.deepcopy(active_ver.data)

    intent_log = db.query(AuditLog).filter(
        AuditLog.target_type == "ai_operation",
        AuditLog.target_id == op_id,
        AuditLog.action == "ai_operation_intent"
    ).order_by(desc(AuditLog.created_at)).first()

    intent_details = (intent_log.details or {}) if intent_log else {}

    planning_dict = None
    recovered_planning = None
    instruction = None

    if op_operation_type == "modify":
        instruction = intent_details.get("instruction")
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry operation: original modification instruction was not retained for this legacy operation and cannot be recovered."
            )
    else:
        if op_module_type in ("execution_roadmap", "detailed_roadmap"):
            raw_planning = intent_details.get("planning_inputs")
            if raw_planning is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot retry operation: original planning intent was not retained for this legacy operation and cannot be recovered."
                )
            try:
                from app.schemas.modules import RoadmapPlanningRequest
                recovered_planning = RoadmapPlanningRequest.model_validate(raw_planning)
                planning_dict = recovered_planning.model_dump(mode="json")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot retry operation: retained planning intent failed validation: {e}"
                )
        elif op_module_type == "tech_stack":
            raw_planning = intent_details.get("planning_inputs")
            if raw_planning:
                try:
                    from app.schemas.modules import TechStackPlanningRequest
                    recovered_planning = TechStackPlanningRequest.model_validate(raw_planning)
                    planning_dict = recovered_planning.model_dump(mode="json")
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot retry operation: retained tech stack planning intent failed validation: {e}"
                    )

    # Decouple: release database connection before calling the external provider
    db.close()

    new_op_id = gen_id("aio_")
    t0 = time.time()

    try:
        data_dict = None
        if op_operation_type == "modify":
            modified_data, _ = ai_service.modify_section(op_module_type, active_ver_data, instruction)
            data_dict = modified_data
        else:
            if op_module_type == "bmc":
                data_dict = ai_service.generate_bmc(proj_info).model_dump()
            elif op_module_type == "tech_stack":
                data_dict = ai_service.generate_tech_stack(proj_info, planning_inputs=planning_dict).model_dump()
                data_dict["planning_inputs"] = planning_dict or {}
            elif op_module_type == "idea_validator":
                data_dict = ai_service.generate_idea_validator(proj_info).model_dump()
            elif op_module_type == "market_research":
                data_dict = ai_service.generate_market_research(proj_info).model_dump()
            elif op_module_type in ("execution_roadmap", "detailed_roadmap"):
                from app.api.modules import _normalize_roadmap_schedule

                roadmap_raw = ai_service.generate_roadmap(proj_info, planning_dict)
                data_dict = _normalize_roadmap_schedule(roadmap_raw, recovered_planning)
                data_dict["planning_inputs"] = planning_dict
            else:
                raise ValueError(f"Unsupported module type for retry: {op_module_type}")

        # Structured output validation before saving
        from app.services.module_orchestration_service import ModuleOrchestrationService
        ModuleOrchestrationService.validate_module_payload(op_module_type, data_dict)
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        terminal_provider_error = ai_service._terminal_provider_error_message(e)
        err_msg = terminal_provider_error or "An internal error occurred during admin retry execution."
        try:
            with SessionLocal() as fail_db:
                failed_retry_record = AIOperation(
                    id=new_op_id,
                    request_id=f"retry_{op_id[:8]}",
                    user_id=op_user_id,
                    project_id=op_project_id,
                    module_type=op_module_type,
                    operation_type=op_operation_type,
                    model_name=op_model_name or settings.GEMINI_MODEL,
                    duration_ms=dur_ms,
                    status="failed",
                    error_category="provider_error" if terminal_provider_error else "api_error",
                    error_message=err_msg,
                    retry_count=op_retry_count,
                    structured_validation_passed=False,
                    persistence_status="failed",
                    is_retryable=terminal_provider_error is None,
                    retry_of_id=op_id,
                    created_at=datetime.now(timezone.utc)
                )
                fail_db.add(failed_retry_record)
                record_audit_log(
                    fail_db,
                    actor_id=admin_id,
                    action="ai_operation_retry",
                    target_type="ai_operation",
                    target_id=op_id,
                    outcome="failed",
                    reason=f"Admin {admin_username} retry attempt failed due to provider error: {err_msg}",
                    details={"original_op_id": op_id, "new_op_id": new_op_id}
                )
                fail_db.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Retry generation failed: {err_msg}"
        ) from e

    with SessionLocal(expire_on_commit=False) as persist_db:
        p_admin = persist_db.query(User).filter(User.id == admin_id).first()
        from app.api.deps import _get_permissions_for_role
        if not p_admin or p_admin.is_suspended or "retry_ai_ops" not in _get_permissions_for_role(p_admin.role):
            raise HTTPException(status_code=403, detail="Admin authorization revoked.")

        p_proj = persist_db.query(Project).filter(Project.id == op_project_id).first()
        if not p_proj:
            raise HTTPException(status_code=404, detail="Project was deleted while retry was in progress.")

        p_op = persist_db.query(AIOperation).filter(AIOperation.id == op_id).first()
        if not p_op:
            raise HTTPException(status_code=404, detail="Original AI operation was deleted.")

        # Re-check for concurrent successful retry
        existing_retry = persist_db.query(AIOperation).filter(
            AIOperation.retry_of_id == op_id,
            AIOperation.status == "success"
        ).first()
        if existing_retry:
            raise HTTPException(
                status_code=400,
                detail=f"This operation was already successfully recovered by retry ID: {existing_retry.id}"
            )

        from app.services.task_graph_validator import project_first_lock
        p_mod = VersionService.get_or_create_module(persist_db, op_project_id, op_module_type)
        with project_first_lock(persist_db, op_project_id, p_mod.id):
            VersionService.assert_version_capacity(persist_db, p_mod)

            if op_module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(data_dict, dict):
                from app.services.roadmap_service import RoadmapDomainService
                if "tasks" not in data_dict or not isinstance(data_dict["tasks"], list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Roadmap data must contain an explicit 'tasks' list."
                    )
                canonical_tasks = RoadmapDomainService.canonicalize_incoming_tasks(persist_db, p_proj, data_dict["tasks"])
                data_dict = dict(data_dict)
                data_dict["tasks"] = canonical_tasks

            VersionService.save_new_version(
                db=persist_db,
                module=p_mod,
                data=data_dict,
                change_summary=f"Recovered via admin retry ({admin_username})",
                commit=False
            )

            if op_module_type in ("execution_roadmap", "detailed_roadmap") and isinstance(data_dict, dict):
                from app.api.modules import _reconcile_roadmap_tasks
                _reconcile_roadmap_tasks(persist_db, p_proj, data_dict["tasks"])

            p_op.status = "retried"
            p_op.retry_count += 1

            dur_ms = int((time.time() - t0) * 1000)
            retry_record = AIOperation(
                id=new_op_id,
                request_id=f"retry_{op_id[:8]}",
                user_id=op_user_id,
                project_id=op_project_id,
                module_type=op_module_type,
                operation_type=op_operation_type,
                model_name=op_model_name or settings.GEMINI_MODEL,
                duration_ms=dur_ms,
                status="success",
                retry_count=p_op.retry_count,
                structured_validation_passed=True,
                persistence_status="persisted",
                is_retryable=False,
                retry_of_id=op_id,
                created_at=datetime.now(timezone.utc)
            )
            persist_db.add(retry_record)

            record_audit_log(
                persist_db,
                actor_id=admin_id,
                action="ai_operation_retry",
                target_type="ai_operation",
                target_id=op_id,
                outcome="success",
                reason=f"Admin {admin_username} successfully recovered failed operation {op_id} ({op_module_type})",
                details={"original_op_id": op_id, "new_op_id": new_op_id, "duration_ms": dur_ms}
            )

            if intent_details:
                record_audit_log(
                    persist_db,
                    actor_id=admin_id,
                    action="ai_operation_intent",
                    target_type="ai_operation",
                    target_id=new_op_id,
                    outcome="recorded",
                    reason=f"Retried operation intent metadata for {op_operation_type}:{op_module_type}",
                    details=intent_details,
                )

            persist_db.commit()

    return {
        "message": "Operation retry executed and persisted successfully via Gemini.",
        "original_operation_id": op_id,
        "retry_operation_id": new_op_id,
        "duration_ms": dur_ms,
        "status": "success"
    }
