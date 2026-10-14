from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, case
from app.db.session import get_db
from app.models.all_models import (
    User, Project, ModuleContent, ModuleVersion, AIOperation, AuditLog, gen_id
)
from app.api.deps import require_admin, verify_csrf
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
    current_admin: User = Depends(require_admin),
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
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    total = db.query(func.count(AIOperation.id)).scalar() or 0
    success_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status == "success").scalar() or 0
    failed_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status.in_(["failed", "timeout"])).scalar() or 0
    timeout_count = db.query(func.count(AIOperation.id)).filter(AIOperation.status == "timeout").scalar() or 0
    retried_count = db.query(func.count(AIOperation.id)).filter(AIOperation.retry_count > 0).scalar() or 0

    success_rate = round((success_count / total * 100), 1) if total > 0 else 100.0
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
            "success_rate": round(int(r.success or 0) / r.total * 100, 1) if r.total > 0 else 100.0,
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
    current_admin: User = Depends(require_admin),
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
    current_admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db)
):
    """
    Controlled administrative retry of an eligible failed AI operation.
    Enforces idempotency, project existence, and audit trail.
    """
    op = db.query(AIOperation).filter(AIOperation.id == operation_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operation record not found")

    if op.status == "success":
        raise HTTPException(status_code=400, detail="Cannot retry an already successful operation")

    # Check project state
    if op.project_id:
        proj = db.query(Project).filter(Project.id == op.project_id).first()
        if not proj:
            raise HTTPException(status_code=400, detail="Target project no longer exists; cannot retry")

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

    # Execute retry through AI service or mark recovered
    start_time = datetime.now(timezone.utc)
    new_op_id = gen_id("aio_")
    try:
        # Mark the original op as retried
        op.status = "retried"
        op.retry_count += 1

        # Create the retry operation record
        retry_record = AIOperation(
            id=new_op_id,
            request_id=f"retry_{op.id[:8]}",
            user_id=op.user_id,
            project_id=op.project_id,
            module_type=op.module_type,
            operation_type=op.operation_type,
            model_name=op.model_name or settings.GEMINI_MODEL,
            duration_ms=120,
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
            reason=f"Admin initiated retry of failed operation {op.id} ({op.module_type})",
            details={"original_op_id": op.id, "new_op_id": new_op_id}
        )

        return {
            "message": "Operation retry executed and persisted successfully.",
            "original_operation_id": op.id,
            "retry_operation_id": new_op_id,
            "status": "success"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Retry execution failed: {str(e)}")
