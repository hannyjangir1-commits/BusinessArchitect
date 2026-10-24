import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.all_models import (
    AIOperation, AnalyticsEvent, SecurityEvent, AuditLog, gen_id
)

logger = logging.getLogger("telemetry")

def record_ai_operation(
    db: Session,
    *,
    module_type: str,
    operation_type: str,
    model_name: str,
    duration_ms: int,
    status: str,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    retry_count: int = 0,
    error_category: Optional[str] = None,
    error_message: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    structured_validation_passed: bool = True,
    persistence_status: str = "persisted",
    is_retryable: bool = False,
    retry_of_id: Optional[str] = None
) -> Optional[AIOperation]:
    """Record an AI operation safely into the ai_operations audit table."""
    try:
        op = AIOperation(
            id=gen_id("aio_"),
            request_id=request_id,
            user_id=user_id,
            project_id=project_id,
            module_type=module_type,
            operation_type=operation_type,
            model_name=model_name,
            duration_ms=duration_ms,
            status=status,
            retry_count=retry_count,
            error_category=error_category,
            error_message=error_message[:1000] if error_message else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            structured_validation_passed=structured_validation_passed,
            persistence_status=persistence_status,
            is_retryable=is_retryable,
            retry_of_id=retry_of_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(op)
        db.commit()
        db.refresh(op)
        return op
    except Exception as e:
        db.rollback()
        logger.error("Failed to record AI operation telemetry: %s", str(e))
        return None

def record_analytics_event(
    db: Session,
    *,
    event_name: str,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    event_category: str = "application",
    metadata_json: Optional[Dict[str, Any]] = None
) -> Optional[AnalyticsEvent]:
    """Record a product analytics event."""
    try:
        evt = AnalyticsEvent(
            id=gen_id("evt_"),
            user_id=user_id,
            project_id=project_id,
            event_name=event_name,
            event_category=event_category,
            metadata_json=metadata_json or {},
            created_at=datetime.now(timezone.utc)
        )
        db.add(evt)
        db.commit()
        return evt
    except Exception as e:
        db.rollback()
        logger.error("Failed to record analytics event: %s", str(e))
        return None

def record_security_event(
    db: Optional[Session] = None,
    *,
    event_type: str,
    severity: str = "info",
    actor_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Optional[SecurityEvent]:
    """Record a security event safely in an isolated transaction to prevent committing caller state."""
    from app.db.session import SessionLocal
    with SessionLocal() as sec_db:
        try:
            sec = SecurityEvent(
                id=gen_id("sec_"),
                event_type=event_type,
                severity=severity,
                actor_id=actor_id,
                target_user_id=target_user_id,
                ip_address=ip_address,
                user_agent=user_agent[:255] if user_agent else None,
                request_path=request_path[:255] if request_path else None,
                details=details or {},
                created_at=datetime.now(timezone.utc)
            )
            sec_db.add(sec)
            sec_db.commit()
            return sec
        except Exception as e:
            sec_db.rollback()
            logger.error("Failed to record security event: %s", str(e))
            return None

def record_audit_log(
    db: Session,
    *,
    actor_id: Optional[str],
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    outcome: str = "success",
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Optional[AuditLog]:
    """Record an administrative audit log entry (immutable, server-side)."""
    try:
        log_entry = AuditLog(
            id=gen_id("aud_"),
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            reason=reason,
            details=details or {},
            created_at=datetime.now(timezone.utc)
        )
        db.add(log_entry)
        db.commit()
        return log_entry
    except Exception as e:
        db.rollback()
        logger.error("Failed to record administrative audit log: %s", str(e))
        return None
