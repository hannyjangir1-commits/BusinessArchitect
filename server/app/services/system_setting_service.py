import json
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.all_models import SystemSetting

logger = logging.getLogger("system.settings")

# Documented default settings
DEFAULT_SETTINGS = {
    "ai_timeout_seconds": 60,
    "ai_max_retries": 3,
    "session_expiry_days": 7,
    "alert_ai_failure_pct": 20.0,
    "alert_db_latency_ms": 200.0,
    "maintenance_mode": False,
    "public_registration_enabled": True,
}

def get_setting_raw(db: Session, key: str) -> Optional[SystemSetting]:
    """Retrieve raw SystemSetting row safely."""
    try:
        return db.query(SystemSetting).filter(SystemSetting.key == key).first()
    except Exception as e:
        logger.warning("Failed to query system setting '%s': %s", key, str(e))
        return None

def get_setting_int(db: Session, key: str, default: Optional[int] = None) -> int:
    """Retrieve an integer setting with fallback to documented defaults."""
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, 0)
    row = get_setting_raw(db, key)
    if not row or row.value is None:
        return fallback
    try:
        return int(row.value)
    except (ValueError, TypeError):
        logger.warning("Malformed int value '%s' for setting '%s', using default %s", row.value, key, fallback)
        return fallback

def get_setting_float(db: Session, key: str, default: Optional[float] = None) -> float:
    """Retrieve a float setting with fallback to documented defaults."""
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, 0.0)
    row = get_setting_raw(db, key)
    if not row or row.value is None:
        return fallback
    try:
        return float(row.value)
    except (ValueError, TypeError):
        logger.warning("Malformed float value '%s' for setting '%s', using default %s", row.value, key, fallback)
        return fallback

def get_setting_bool(db: Session, key: str, default: Optional[bool] = None) -> bool:
    """Retrieve a boolean setting with fallback to documented defaults."""
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, False)
    row = get_setting_raw(db, key)
    if not row or row.value is None:
        return fallback
    val_str = str(row.value).strip().lower()
    if val_str in ("true", "1", "yes", "t"):
        return True
    elif val_str in ("false", "0", "no", "f"):
        return False
    logger.warning("Malformed boolean value '%s' for setting '%s', using default %s", row.value, key, fallback)
    return fallback

def get_setting_str(db: Session, key: str, default: Optional[str] = None) -> str:
    """Retrieve a string setting with fallback to documented defaults."""
    fallback = default if default is not None else DEFAULT_SETTINGS.get(key, "")
    row = get_setting_raw(db, key)
    if not row or row.value is None:
        return fallback
    return str(row.value)

def set_setting(db: Session, key: str, value: Any, value_type: str = "string", updated_by: Optional[str] = None) -> SystemSetting:
    """Helper to set or update a system setting."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=str(value), value_type=value_type)
        db.add(setting)
    else:
        setting.value = str(value)
        setting.value_type = value_type
    if updated_by:
        setting.updated_by = updated_by
    db.commit()
    db.refresh(setting)

    if key == "maintenance_mode":
        invalidate_maintenance_mode_cache()

    return setting

# --- In-Process Thread-Safe Maintenance Mode TTL Cache (Batch 02) ---
import time
import threading

MAINTENANCE_CACHE_TTL_SECONDS: float = 30.0
_maintenance_cache_lock = threading.Lock()
_cached_maintenance_value: Optional[bool] = None
_cached_maintenance_expiry: float = 0.0

def get_maintenance_mode_cached(
    db: Optional[Session] = None,
    ttl_seconds: float = MAINTENANCE_CACHE_TTL_SECONDS
) -> bool:
    """
    Thread-safe, bounded in-process TTL cache for the global maintenance_mode setting.
    Eliminates redundant database round-trips on high-frequency request paths.

    Note: In multi-worker deployments, this is a per-process cache with a maximum
    consistency delay equal to ttl_seconds.
    """
    global _cached_maintenance_value, _cached_maintenance_expiry

    now_mono = time.monotonic()
    if _cached_maintenance_value is not None and now_mono < _cached_maintenance_expiry:
        return _cached_maintenance_value

    with _maintenance_cache_lock:
        now_mono = time.monotonic()
        if _cached_maintenance_value is not None and now_mono < _cached_maintenance_expiry:
            return _cached_maintenance_value

        val = False
        try:
            from app.core.diagnostics import record_stage
            with record_stage("maintenance_lookup"):
                if db is not None:
                    val = get_setting_bool(db, "maintenance_mode", False)
                else:
                    from app.db.session import SessionLocal
                    with SessionLocal() as local_db:
                        val = get_setting_bool(local_db, "maintenance_mode", False)
            _cached_maintenance_value = val
            _cached_maintenance_expiry = time.monotonic() + max(0.01, float(ttl_seconds))
            return val
        except Exception as e:
            logger.warning("Failed to refresh cached maintenance mode from database: %s", str(e))
            if _cached_maintenance_value is not None:
                return _cached_maintenance_value
            return False

def invalidate_maintenance_mode_cache() -> None:
    """Immediately invalidate the local in-process maintenance-mode cache."""
    global _cached_maintenance_value, _cached_maintenance_expiry
    with _maintenance_cache_lock:
        _cached_maintenance_value = None
        _cached_maintenance_expiry = 0.0

def reset_maintenance_mode_cache() -> None:
    """Reset the maintenance-mode cache state (for test isolation)."""
    invalidate_maintenance_mode_cache()
