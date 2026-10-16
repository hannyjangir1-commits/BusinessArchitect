from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, case
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, AIOperation, AuditLog, gen_id
)
from app.api.deps import require_admin, require_permission, verify_csrf
from app.core.config import settings
from app.core.telemetry import record_ai_operation, record_audit_log

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

    proj_info = {
        "id": proj.id,
        "name": proj.name,
        "stage": proj.stage,
        "description": proj.description,
        "industry": proj.industry,
        "target_customers": proj.target_customers,
        "goals": proj.goals,
        "business_context": proj.business_context,
        "budget": proj.budget,
        "existing_stack": proj.existing_stack or {}
    }

    new_op_id = gen_id("aio_")
    t0 = time.time()

    try:
        data_dict = None
        module_type = op.module_type

        if op.operation_type == "modify":
            # For modification retries, attempt section modify with previous prompt or error note
            module = VersionService.get_or_create_module(db, proj.id, module_type)
            active_ver = db.query(ModuleVersion).filter(ModuleVersion.id == module.active_version_id).first()
            if not active_ver or not active_ver.data:
                raise ValueError("Active version data not available to modify")
            instruction = f"Administrative recovery retry for failed operation {op.id}"
            modified_data, _ = ai_service.modify_section(module_type, active_ver.data, instruction)
            data_dict = modified_data
        else:
            # Generation retry
            if module_type == "bmc":
                data_dict = ai_service.generate_bmc(proj_info).model_dump()
            elif module_type == "tech_stack":
                data_dict = ai_service.generate_tech_stack(proj_info).model_dump()
            elif module_type == "idea_validator":
                data_dict = ai_service.generate_idea_validator(proj_info).model_dump()
            elif module_type == "market_research":
                data_dict = ai_service.generate_market_research(proj_info).model_dump()
            elif module_type in ("execution_roadmap", "detailed_roadmap"):
                roadmap_raw = ai_service.generate_roadmap(proj_info)
                data_dict = roadmap_raw
                tasks_data = roadmap_raw.get("tasks", [])
                if tasks_data:
                    from app.api.modules import _reconcile_roadmap_tasks
                    _reconcile_roadmap_tasks(db, proj, tasks_data)
            else:
                raise ValueError(f"Unsupported module type for retry: {module_type}")

        dur_ms = int((time.time() - t0) * 1000)

        # Persist new version
        module = VersionService.get_or_create_module(db, proj.id, module_type)
        VersionService.save_new_version(
            db=db,
            module=module,
            data=data_dict,
            change_summary=f"Recovered via admin retry ({current_admin.username})"
        )

        op.status = "retried"
        op.retry_count += 1

        retry_record = AIOperation(
            id=new_op_id,
            request_id=f"retry_{op.id[:8]}",
            user_id=op.user_id,
            project_id=op.project_id,
            module_type=op.module_type,
            operation_type=op.operation_type,
            model_name=op.model_name or settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="success",
            retry_count=op.retry_count,
            structured_validation_passed=True,
            persistence_status="persisted",
            is_retryable=False,
            retry_of_id=op.id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(retry_record)
        db.commit()

        record_audit_log(
            db,
            actor_id=current_admin.id,
            action="ai_operation_retry",
            target_type="ai_operation",
            target_id=op.id,
            outcome="success",
            reason=f"Admin {current_admin.username} successfully recovered failed operation {op.id} ({op.module_type})",
            details={"original_op_id": op.id, "new_op_id": new_op_id, "duration_ms": dur_ms}
        )

        return {
            "message": "Operation retry executed and persisted successfully via Gemini.",
            "original_operation_id": op.id,
            "retry_operation_id": new_op_id,
            "duration_ms": dur_ms,
            "status": "success"
        }
    except Exception as e:
        dur_ms = int((time.time() - t0) * 1000)
        db.rollback()

        failed_retry_record = AIOperation(
            id=new_op_id,
            request_id=f"retry_{op.id[:8]}",
            user_id=op.user_id,
            project_id=op.project_id,
            module_type=op.module_type,
            operation_type=op.operation_type,
            model_name=op.model_name or settings.GEMINI_MODEL,
            duration_ms=dur_ms,
            status="failed",
            error_category="api_error",
            error_message=str(e),
            retry_count=op.retry_count,
            structured_validation_passed=False,
            persistence_status="failed",
            is_retryable=True,
            retry_of_id=op.id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(failed_retry_record)
        db.commit()

        record_audit_log(
            db,
            actor_id=current_admin.id,
            action="ai_operation_retry",
            target_type="ai_operation",
            target_id=op.id,
            outcome="failed",
            reason=f"Admin {current_admin.username} retry attempt failed: {str(e)}",
            details={"original_op_id": op.id, "new_op_id": new_op_id, "error": str(e)}
        )

        raise HTTPException(status_code=500, detail=f"Retry execution failed: {str(e)}")
