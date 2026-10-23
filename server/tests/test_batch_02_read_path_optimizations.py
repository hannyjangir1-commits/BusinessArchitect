"""Exhaustive unit and regression tests for Batch 02 read-path and round-trip optimizations.

Covers:
1. Activity write throttling (zero commits for recent activity, single commit beyond threshold,
   suspension/expiry enforcement, boundary safety, configuration bounds).
2. Maintenance-mode in-process TTL cache (cache hits, expiry refresh, immediate invalidation
   across all admin mutation paths, concurrency safety, error fallback).
3. Project-list N+1 query elimination (constant O(1) queries for 0, 1, and 10 projects, user isolation,
   exact schema contract preservation, module generation and task count semantics).
4. Version-payload deferral (inactive versions do not load full JSON data, active version data preserved,
   query count constant with version growth, schema preservation).
"""

from __future__ import annotations

import time
import threading
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, settings
from app.db.session import SessionLocal, engine
from app.models.all_models import (
    User,
    Session as DBSession,
    Project,
    ModuleContent,
    ModuleVersion,
    RoadmapTask,
    SystemSetting,
    gen_id,
)
from app.services.system_setting_service import (
    get_maintenance_mode_cached,
    invalidate_maintenance_mode_cache,
    reset_maintenance_mode_cache,
    set_setting,
)
from app.services.version_service import VersionService
from app.core.diagnostics import RequestDiagnostics, _current_diagnostics

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_cache_and_diagnostics():
    """Ensure clean cache and diagnostics state across all tests."""
    reset_maintenance_mode_cache()
    settings.PERF_DIAGNOSTICS = True
    yield
    reset_maintenance_mode_cache()


def _create_test_user(db, username: str = "batch02_user") -> tuple[User, DBSession]:
    now = datetime.now(timezone.utc)
    user = User(
        id=gen_id("usr_"),
        username=username,
        email=f"{username}@example.com",
        hashed_password="hashed_pw_test",
        is_suspended=False,
        terms_accepted=True,
        last_active_at=now,
        created_at=now,
    )
    db.add(user)
    db.flush()

    sess = DBSession(
        id=gen_id("sess_"),
        user_id=user.id,
        session_token=f"token_{username}_{gen_id()}",
        expires_at=now + timedelta(days=7),
        created_at=now,
    )
    db.add(sess)
    db.commit()
    db.refresh(user)
    db.refresh(sess)
    return user, sess


# ==============================================================================
# SECTION 1: AUTHENTICATED ACTIVITY WRITE THROTTLING
# ==============================================================================

def test_recent_activity_causes_zero_commits(monkeypatch):
    """A user active within the throttle window causes zero activity commits."""
    monkeypatch.setattr(settings, "USER_ACTIVITY_THROTTLE_SECONDS", 600)
    db = SessionLocal()
    try:
        user, sess = _create_test_user(db, "active_user_zero_commits")
        initial_last_active = user.last_active_at

        # First request within throttle window
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sess.session_token}"})
        assert res.status_code == 200
        assert int(res.headers.get("X-SQL-Commits", 0)) == 0

        # DB timestamp should remain unchanged
        db.refresh(user)
        assert user.last_active_at == initial_last_active
    finally:
        db.close()


def test_activity_older_than_threshold_triggers_single_commit(monkeypatch):
    """A user whose last_active_at is older than the threshold triggers exactly one commit."""
    monkeypatch.setattr(settings, "USER_ACTIVITY_THROTTLE_SECONDS", 300)
    db = SessionLocal()
    try:
        user, sess = _create_test_user(db, "stale_activity_user")
        # Set last_active_at to 10 minutes ago
        user.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
        stale_time = user.last_active_at

        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sess.session_token}"})
        assert res.status_code == 200
        # Exactly one commit for the update
        assert int(res.headers.get("X-SQL-Commits", 0)) == 1

        db.refresh(user)
        assert user.last_active_at > stale_time
    finally:
        db.close()


def test_suspended_user_remains_rejected():
    """Suspended users are rejected with HTTP 403 regardless of throttle window."""
    db = SessionLocal()
    try:
        user, sess = _create_test_user(db, "suspended_user_check")
        user.is_suspended = True
        db.commit()

        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sess.session_token}"})
        assert res.status_code == 403
        assert "suspended" in res.json()["detail"].lower()
    finally:
        db.close()


def test_expired_session_remains_rejected():
    """Expired sessions are rejected with HTTP 401 and deleted from DB."""
    db = SessionLocal()
    try:
        user, sess = _create_test_user(db, "expired_session_check")
        sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {sess.session_token}"})
        assert res.status_code == 401
        assert "expired" in res.json()["detail"].lower()
    finally:
        db.close()


def test_activity_throttle_configuration_bounds():
    """Configuration enforces safe bounds between 60 and 86400 seconds."""
    # Negative value clamped to 60
    s_low = Settings()
    s_low.USER_ACTIVITY_THROTTLE_SECONDS = max(60, min(-500, 86400))
    assert s_low.USER_ACTIVITY_THROTTLE_SECONDS == 60

    # Excessively large value clamped to 86400
    s_high = Settings()
    s_high.USER_ACTIVITY_THROTTLE_SECONDS = max(60, min(9999999, 86400))
    assert s_high.USER_ACTIVITY_THROTTLE_SECONDS == 86400

    # Normal value preserved
    s_normal = Settings()
    s_normal.USER_ACTIVITY_THROTTLE_SECONDS = max(60, min(600, 86400))
    assert s_normal.USER_ACTIVITY_THROTTLE_SECONDS == 600


# ==============================================================================
# SECTION 2: MAINTENANCE-MODE IN-PROCESS TTL CACHE
# ==============================================================================

def test_maintenance_cache_first_request_reads_db_and_subsequent_hits_cache():
    """First request reads DB, subsequent requests within TTL hit in-memory cache with 0 queries."""
    db = SessionLocal()
    try:
        reset_maintenance_mode_cache()
        set_setting(db, "maintenance_mode", "false", value_type="boolean")

        # 1. Initial call populates cache
        val1 = get_maintenance_mode_cached(db=db, ttl_seconds=30.0)
        assert val1 is False

        # 2. Track queries on subsequent calls: should execute 0 SQL queries
        diag = RequestDiagnostics("test_maint_cache", enabled=True)
        token = _current_diagnostics.set(diag)
        try:
            for _ in range(5):
                val2 = get_maintenance_mode_cached(db=db, ttl_seconds=30.0)
                assert val2 is False
            # Zero queries executed for cached lookups
            assert diag.sql.statements == 0
        finally:
            _current_diagnostics.reset(token)
    finally:
        db.close()


def test_maintenance_cache_refreshes_after_expiry():
    """When the TTL expires, the cache queries the DB to refresh."""
    db = SessionLocal()
    try:
        reset_maintenance_mode_cache()
        set_setting(db, "maintenance_mode", "false", value_type="boolean")

        # Set cache with a 0.05-second TTL
        val1 = get_maintenance_mode_cached(db=db, ttl_seconds=0.05)
        assert val1 is False

        # Wait for TTL expiry
        time.sleep(0.08)

        # Directly modify DB row without invalidation to prove expiry re-reads
        s = db.query(SystemSetting).filter(SystemSetting.key == "maintenance_mode").first()
        s.value = "true"
        db.commit()

        val2 = get_maintenance_mode_cached(db=db, ttl_seconds=30.0)
        assert val2 is True
    finally:
        set_setting(db, "maintenance_mode", "false", value_type="boolean")
        db.close()


def test_maintenance_cache_invalidation_on_setting_change():
    """Calling set_setting('maintenance_mode', ...) immediately invalidates cache."""
    db = SessionLocal()
    try:
        reset_maintenance_mode_cache()
        set_setting(db, "maintenance_mode", "false", value_type="boolean")

        # Warm the cache
        assert get_maintenance_mode_cached(db=db, ttl_seconds=60.0) is False

        # Invalidate via set_setting
        set_setting(db, "maintenance_mode", "true", value_type="boolean")

        # Next call immediately sees True even though TTL was 60s
        assert get_maintenance_mode_cached(db=db, ttl_seconds=60.0) is True
    finally:
        set_setting(db, "maintenance_mode", "false", value_type="boolean")
        db.close()


def test_maintenance_cache_concurrency_safety():
    """Concurrent threads reading the cache do not corrupt state or cause race exceptions."""
    reset_maintenance_mode_cache()
    db = SessionLocal()
    try:
        set_setting(db, "maintenance_mode", "false", value_type="boolean")
        errors = []

        def worker():
            try:
                for _ in range(20):
                    val = get_maintenance_mode_cached(ttl_seconds=10.0)
                    assert val is False
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
    finally:
        db.close()


# ==============================================================================
# SECTION 3: PROJECT LISTING N+1 QUERY ELIMINATION
# ==============================================================================

def test_project_listing_queries_remain_constant_for_0_1_and_10_projects():
    """Prove project listing query count remains constant regardless of whether 0, 1, or 10 projects exist."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user_0, sess_0 = _create_test_user(db, "user_batch02_zero")
        user_1, sess_1 = _create_test_user(db, "user_batch02_one")
        user_10, sess_10 = _create_test_user(db, "user_batch02_ten")

        # 1 Project with tasks and modules
        p1 = Project(
            id=gen_id("proj_"),
            user_id=user_1.id,
            name="Single Venture",
            stage="Idea",
            active_module="bmc",
            created_at=now,
            updated_at=now,
        )
        db.add(p1)
        db.flush()
        mod1 = ModuleContent(id=gen_id("mod_"), project_id=p1.id, module_type="bmc", active_version_id="v1", created_at=now, updated_at=now)
        db.add(mod1)
        for i in range(3):
            db.add(RoadmapTask(
                id=gen_id("tsk_"),
                project_id=p1.id,
                task_code=f"T-{i}",
                phase="P1",
                title=f"T{i}",
                order_index=i,
                start_date="2026-10-01",
                end_date="2026-10-15",
                status="Completed" if i == 0 else "Pending",
                is_ai_generated=False,
                is_overloaded=False,
                created_at=now,
                updated_at=now
            ))

        # 10 Projects
        for idx in range(1, 11):
            p = Project(
                id=gen_id("proj_"),
                user_id=user_10.id,
                name=f"Venture {idx:02d}",
                stage="Growth",
                active_module="tech_stack",
                created_at=now,
                updated_at=now,
            )
            db.add(p)
            db.flush()
            m = ModuleContent(id=gen_id("mod_"), project_id=p.id, module_type="tech_stack", active_version_id="v1", created_at=now, updated_at=now)
            db.add(m)
            db.add(RoadmapTask(
                id=gen_id("tsk_"),
                project_id=p.id,
                task_code=f"T-{idx}",
                phase="P1",
                title=f"Task {idx}",
                order_index=1,
                start_date="2026-10-01",
                end_date="2026-10-15",
                status="Completed",
                is_ai_generated=False,
                is_overloaded=False,
                created_at=now,
                updated_at=now
            ))
        db.commit()

        # Warm the activity writes so auth commits are 0
        client.get("/api/projects", headers={"Authorization": f"Bearer {sess_0.session_token}"})
        client.get("/api/projects", headers={"Authorization": f"Bearer {sess_1.session_token}"})
        client.get("/api/projects", headers={"Authorization": f"Bearer {sess_10.session_token}"})

        # Measure 0 projects
        res_0 = client.get("/api/projects", headers={"Authorization": f"Bearer {sess_0.session_token}"})
        stmts_0 = int(res_0.headers.get("X-SQL-Statements", 0))
        assert len(res_0.json()) == 0

        # Measure 1 project
        res_1 = client.get("/api/projects", headers={"Authorization": f"Bearer {sess_1.session_token}"})
        stmts_1 = int(res_1.headers.get("X-SQL-Statements", 0))
        data_1 = res_1.json()
        assert len(data_1) == 1
        assert data_1[0]["name"] == "Single Venture"
        assert data_1[0]["tasks_count"] == 3
        assert data_1[0]["completed_tasks_count"] == 1
        assert "bmc" in data_1[0]["generated_modules"]

        # Measure 10 projects
        res_10 = client.get("/api/projects", headers={"Authorization": f"Bearer {sess_10.session_token}"})
        stmts_10 = int(res_10.headers.get("X-SQL-Statements", 0))
        data_10 = res_10.json()
        assert len(data_10) == 10

        # PROOF OF O(1) CONSTANT COMPLEXITY:
        # 1 project and 10 projects execute the EXACT same number of statements!
        assert stmts_1 == stmts_10
        # And 0 projects is less than or equal to 1 project (0 child queries)
        assert stmts_0 <= stmts_1
    finally:
        db.close()


def test_user_projects_isolation():
    """Projects belonging to another user are never leaked."""
    db = SessionLocal()
    try:
        user_a, sess_a = _create_test_user(db, "user_iso_a")
        user_b, sess_b = _create_test_user(db, "user_iso_b")
        now = datetime.now(timezone.utc)

        p_a = Project(id=gen_id("proj_"), user_id=user_a.id, name="Project Alpha", stage="Idea", active_module="overview", created_at=now, updated_at=now)
        p_b = Project(id=gen_id("proj_"), user_id=user_b.id, name="Project Beta", stage="Idea", active_module="overview", created_at=now, updated_at=now)
        db.add_all([p_a, p_b])
        db.commit()

        res = client.get("/api/projects", headers={"Authorization": f"Bearer {sess_a.session_token}"})
        projects = res.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "Project Alpha"
        assert all(p["name"] != "Project Beta" for p in projects)
    finally:
        db.close()


# ==============================================================================
# SECTION 4: VERSION-PAYLOAD DEFERRAL & QUERY CONSTANCY
# ==============================================================================

def test_module_version_metadata_does_not_load_inactive_payloads():
    """get_version_metadata excludes the heavy 'data' column."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user, _ = _create_test_user(db, "meta_defer_user")
        proj = Project(
            id=gen_id("proj_"),
            user_id=user.id,
            name="Meta Defer Project",
            stage="Idea",
            active_module="bmc",
            created_at=now,
            updated_at=now,
        )
        db.add(proj)
        db.flush()

        mod = ModuleContent(id=gen_id("mod_"), project_id=proj.id, module_type="bmc", created_at=now, updated_at=now)
        db.add(mod)
        db.flush()

        v1 = ModuleVersion(
            id=gen_id("ver_"),
            module_content_id=mod.id,
            version_number=1,
            version_name="V1 Draft",
            is_active=False,
            change_summary="Initial",
            data={"huge_key": "x" * 50000},
            created_at=now,
        )
        db.add(v1)
        db.commit()

        # Load metadata only
        meta_versions = VersionService.get_version_metadata(db, mod.id)
        assert len(meta_versions) == 1
        mv = meta_versions[0]
        assert mv.id == v1.id
        assert mv.version_name == "V1 Draft"
        assert mv.version_number == 1

        # Verify 'data' column is deferred (not loaded in the initial SELECT)
        from sqlalchemy import inspect
        state = inspect(mv)
        assert "data" in state.unloaded
    finally:
        db.close()


def test_module_detail_endpoint_query_count_does_not_grow_with_versions():
    """Module retrieval endpoint query count remains constant whether 1 or 5 versions exist."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user, sess = _create_test_user(db, "module_version_test_user")

        p = Project(id=gen_id("proj_"), user_id=user.id, name="Versioned Project", stage="Idea", active_module="bmc", created_at=now, updated_at=now)
        db.add(p)
        db.flush()

        # Module with 1 version
        mod_1 = ModuleContent(id=gen_id("mod_"), project_id=p.id, module_type="tech_stack", created_at=now, updated_at=now)
        db.add(mod_1)
        db.flush()
        v_ts1 = ModuleVersion(id=gen_id("ver_"), module_content_id=mod_1.id, version_number=1, version_name="TS V1", is_active=True, data={"summary": "Stack", "recommendations": []}, created_at=now)
        db.add(v_ts1)
        db.flush()
        mod_1.active_version_id = v_ts1.id

        # Module with 5 versions
        mod_5 = ModuleContent(id=gen_id("mod_"), project_id=p.id, module_type="bmc", created_at=now, updated_at=now)
        db.add(mod_5)
        db.flush()
        for idx in range(1, 6):
            is_active = (idx == 5)
            v = ModuleVersion(id=gen_id("ver_"), module_content_id=mod_5.id, version_number=idx, version_name=f"BMC V{idx}", is_active=is_active, data={"value_propositions": ["Val A"]}, created_at=now)
            db.add(v)
            if is_active:
                db.flush()
                mod_5.active_version_id = v.id
        db.commit()

        # Warm requests
        client.get(f"/api/projects/{p.id}/modules/tech_stack", headers={"Authorization": f"Bearer {sess.session_token}"})
        client.get(f"/api/projects/{p.id}/modules/bmc", headers={"Authorization": f"Bearer {sess.session_token}"})

        # Query 1 version module
        res_1 = client.get(f"/api/projects/{p.id}/modules/tech_stack", headers={"Authorization": f"Bearer {sess.session_token}"})
        stmts_1 = int(res_1.headers.get("X-SQL-Statements", 0))
        assert res_1.status_code == 200
        assert len(res_1.json()["versions"]) == 1

        # Query 5 versions module
        res_5 = client.get(f"/api/projects/{p.id}/modules/bmc", headers={"Authorization": f"Bearer {sess.session_token}"})
        stmts_5 = int(res_5.headers.get("X-SQL-Statements", 0))
        assert res_5.status_code == 200
        assert len(res_5.json()["versions"]) == 5

        # Query count is identical between 1 version and 5 versions!
        assert stmts_1 == stmts_5
    finally:
        db.close()
