"""
Multiprocessing workers for PostgreSQL concurrency testing.
Each worker runs in an independent operating system process with its own engine
and connection pool, ensuring that lock contention tests database-level row locks
(SELECT FOR UPDATE) rather than process-local in-memory mutexes.
"""

from typing import Any, Dict, List, Optional
import os


def sanitize_worker_error(worker_name: str, stage: str, exc: Exception) -> Dict[str, Any]:
    """
    Sanitize worker error reports to allowlisted category and stage information.
    Guarantees no raw SQL, database URLs, or credentials can be exposed.
    """
    category = type(exc).__name__
    if "Timeout" in category:
        cat_type = "TIMEOUT"
    elif "Deadlock" in category or "deadlock" in str(exc).lower():
        cat_type = "DEADLOCK"
    elif "Lock" in category or "lock" in str(exc).lower():
        cat_type = "LOCK_FAILURE"
    elif "Integrity" in category:
        cat_type = "INTEGRITY_ERROR"
    else:
        cat_type = "OPERATIONAL_FAILURE"

    return {
        "worker": worker_name,
        "stage": stage,
        "category": cat_type,
        "exception_type": category
    }


def get_worker_engine_and_session(db_url_str: str, schema_name: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        db_url_str,
        connect_args={
            "connect_timeout": 3,
            "options": f"-c search_path={schema_name} -c statement_timeout=5000 -c lock_timeout=5000"
        },
        pool_pre_ping=True
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, Session


def worker_manual_mutation_hold(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    a_holding: Any,
    a_release: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import RoadmapTask
        from app.services.task_graph_validator import project_first_lock

        with Session() as s:
            with project_first_lock(s, proj_id, mod_id):
                task = RoadmapTask(
                    project_id=proj_id,
                    task_code="MAN-LOCK",
                    phase="P1",
                    title="Manual While Locked",
                    start_date="2026-11-01",
                    end_date="2026-11-05",
                    status="Pending",
                    dependencies=[],
                    is_ai_generated=False
                )
                s.add(task)
                s.flush()
                a_holding.set()
                if not a_release.wait(timeout=5):
                    raise TimeoutError("Worker A timed out waiting for release signal.")
                s.commit()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Manual Hold", "hold_mutation", e))
    finally:
        engine.dispose()


def worker_roadmap_restore_compete(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    v1_id: str,
    a_holding: Any,
    b_started: Any,
    b_finished: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import ModuleContent
        from app.services.version_service import VersionService
        from app.services.roadmap_service import RoadmapDomainService
        from app.services.task_graph_validator import project_first_lock

        if not a_holding.wait(timeout=5):
            raise TimeoutError("Worker B timed out waiting for Worker A to acquire lock.")

        with Session() as s:
            mod = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            # Signal immediately before attempting the contested lock
            b_started.set()
            with project_first_lock(s, proj_id, mod_id):
                VersionService.restore_version(s, mod, v1_id, commit=False)
                tasks_data = [{"task_code": "V1-01", "phase": "P1", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
                RoadmapDomainService.reconcile_roadmap_tasks(s, mod.project, tasks_data)
                s.commit()
                b_finished.set()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Restore Compete", "compete_restore", e))
    finally:
        engine.dispose()


def worker_gen_hold_mutation(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    a_holding: Any,
    a_release: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import RoadmapTask
        from app.services.task_graph_validator import project_first_lock

        with Session() as s:
            with project_first_lock(s, proj_id, mod_id):
                t = RoadmapTask(
                    project_id=proj_id,
                    task_code="TSK-01",
                    phase="P1",
                    title="Manual 1",
                    start_date="2026-11-01",
                    end_date="2026-11-05",
                    status="Pending",
                    dependencies=[],
                    is_ai_generated=False
                )
                s.add(t)
                s.flush()
                a_holding.set()
                if not a_release.wait(timeout=5):
                    raise TimeoutError("Worker A timed out waiting for release signal.")
                s.commit()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Gen Hold", "hold_mutation", e))
    finally:
        engine.dispose()


def worker_gen_compete_persistence(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    raw_tasks: List[Dict[str, Any]],
    a_holding: Any,
    b_started: Any,
    b_finished: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import ModuleContent
        from app.services.version_service import VersionService
        from app.services.roadmap_service import RoadmapDomainService
        from app.services.task_graph_validator import project_first_lock

        if not a_holding.wait(timeout=5):
            raise TimeoutError("Worker B timed out waiting for Worker A to acquire lock.")

        with Session() as s:
            mod = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            # Signal immediately before attempting the contested lock
            b_started.set()
            with project_first_lock(s, proj_id, mod_id):
                canonical = RoadmapDomainService.canonicalize_incoming_tasks(s, mod.project, raw_tasks)
                VersionService.save_new_version(
                    db=s,
                    module=mod,
                    data={"phases": [{"name": "P1"}], "tasks": canonical},
                    change_summary="Gen B",
                    commit=False
                )
                RoadmapDomainService.reconcile_roadmap_tasks(s, mod.project, canonical)
                s.commit()
                b_finished.set()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Gen Compete", "compete_persistence", e))
    finally:
        engine.dispose()


def worker_restore_hold(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    v1_id: str,
    a_holding: Any,
    a_release: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import ModuleContent
        from app.services.version_service import VersionService
        from app.services.roadmap_service import RoadmapDomainService
        from app.services.task_graph_validator import project_first_lock

        with Session() as s:
            mod = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            with project_first_lock(s, proj_id, mod_id):
                VersionService.restore_version(s, mod, v1_id, commit=False)
                tasks_data = [{"task_code": "V1-01", "phase": "P1", "title": "V1", "start_date": "2026-11-01", "end_date": "2026-11-05", "dependencies": []}]
                RoadmapDomainService.reconcile_roadmap_tasks(s, mod.project, tasks_data)
                s.flush()
                a_holding.set()
                if not a_release.wait(timeout=5):
                    raise TimeoutError("Worker Restore timed out waiting for release.")
                s.commit()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Restore Hold", "hold_restore", e))
    finally:
        engine.dispose()


def worker_repair_compete(
    db_url_str: str,
    schema_name: str,
    proj_id: str,
    mod_id: str,
    a_holding: Any,
    b_started: Any,
    b_finished: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import ModuleContent, ModuleVersion
        from app.services.version_service import VersionService
        from app.services.roadmap_service import RoadmapDomainService
        from app.services.task_graph_validator import project_first_lock

        if not a_holding.wait(timeout=5):
            raise TimeoutError("Worker Repair timed out waiting for Worker Restore to acquire lock.")

        with Session() as s:
            mod = s.query(ModuleContent).filter(ModuleContent.id == mod_id).first()
            # Signal immediately before attempting the contested lock
            b_started.set()
            with project_first_lock(s, proj_id, mod_id):
                # Execute actual production VersionService repair operation
                VersionService.repair_active_version_for_module(s, mod)
                active_v = s.query(ModuleVersion).filter(ModuleVersion.id == mod.active_version_id).first()
                if active_v and active_v.data and "tasks" in active_v.data:
                    RoadmapDomainService.reconcile_roadmap_tasks(s, mod.project, active_v.data["tasks"])
                s.commit()
                b_finished.set()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker Repair Compete", "repair_execution", e))
    finally:
        engine.dispose()


def worker_p1_hold(
    db_url_str: str,
    schema_name: str,
    p1_id: str,
    p1_holding: Any,
    p1_release: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.services.task_graph_validator import project_first_lock

        with Session() as s:
            with project_first_lock(s, p1_id):
                p1_holding.set()
                if not p1_release.wait(timeout=5):
                    raise TimeoutError("P1 timed out waiting for release.")
                s.commit()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker P1 Hold", "hold_p1", e))
    finally:
        engine.dispose()


def worker_p2_compete(
    db_url_str: str,
    schema_name: str,
    p2_id: str,
    p1_holding: Any,
    p2_finished: Any,
    error_queue: Any
) -> None:
    engine, Session = get_worker_engine_and_session(db_url_str, schema_name)
    try:
        from app.models.all_models import RoadmapTask
        from app.services.task_graph_validator import project_first_lock

        if not p1_holding.wait(timeout=5):
            raise TimeoutError("P2 timed out waiting for P1 holding.")

        with Session() as s:
            with project_first_lock(s, p2_id):
                t = RoadmapTask(
                    project_id=p2_id,
                    task_code="P2-TASK",
                    phase="P1",
                    title="P2 Task",
                    start_date="2026-11-01",
                    end_date="2026-11-05",
                    status="Pending",
                    dependencies=[],
                    is_ai_generated=False
                )
                s.add(t)
                s.commit()
                p2_finished.set()
    except Exception as e:
        error_queue.put(sanitize_worker_error("Worker P2 Compete", "compete_p2", e))
    finally:
        engine.dispose()
