"""Task identity, dependency graph, and schedule integrity validation service."""

from contextlib import contextmanager
from datetime import datetime, date
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.all_models import RoadmapTask, Project

# Fixed striped locks for in-process per-project synchronization.
# Strictly bounded constant memory: 256 RLock instances allocated once.
# Using RLock ensures safe re-entrancy for nested service calls in the same thread.
_PROJECT_TASK_LOCK_STRIPES = 256
_STRIPED_PROJECT_LOCKS = [threading.RLock() for _ in range(_PROJECT_TASK_LOCK_STRIPES)]


def get_project_task_lock(project_id: str) -> threading.RLock:
    """Return a deterministic striped lock for the given project ID."""
    clean_id = project_id.strip() if project_id else "default"
    import hashlib
    idx = int(hashlib.md5(clean_id.encode("utf-8")).hexdigest()[:8], 16) % _PROJECT_TASK_LOCK_STRIPES
    return _STRIPED_PROJECT_LOCKS[idx]


def lock_project_for_task_mutation(db: Session, project_id: str) -> None:
    """
    Acquire database-level project lock to safely serialize concurrent task
    creations and graph renames per project on PostgreSQL and SQLite.
    """
    from app.services.transaction_service import lock_record
    lock_record(db, Project, project_id)


@contextmanager
def project_first_lock(
    db: Session,
    project_id: str,
    module_id: Optional[str] = None
):
    """
    Hierarchical lock protocol: Project -> ModuleContent -> task/version reads & writes.

    Acquires locks in strict hierarchical order:
    1. In-process striped Project lock (RLock)
    2. In-process striped Module lock (RLock, if module_id specified)
    3. Database-level Project row lock (SELECT FOR UPDATE on Postgres / write reservation on SQLite)
    4. Database-level ModuleContent row lock (if module_id specified)

    Refreshes stale ORM state via populate_existing() on row locks to guarantee authoritative reads.
    Prevents AB-BA deadlocks by ensuring Project is always locked before ModuleContent.
    """
    from app.services.transaction_service import lock_record
    from app.models.all_models import ModuleContent
    from app.services.version_service import get_module_lock

    proj_lock = get_project_task_lock(project_id)
    mod_lock = get_module_lock(module_id) if module_id else None

    with proj_lock:
        if mod_lock:
            with mod_lock:
                lock_record(db, Project, project_id)
                lock_record(db, ModuleContent, module_id)
                yield
        else:
            lock_record(db, Project, project_id)
            yield


class IncompatibleTaskGraphError(HTTPException):
    """Structured validation exception for incompatible candidate task graphs."""

    def __init__(
        self,
        error_code: str,
        message: str,
        affected_task_codes: Optional[List[str]] = None,
        missing_prerequisite_codes: Optional[List[str]] = None,
        blocking_retained_task_codes: Optional[List[str]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        detail = {
            "error_code": error_code,
            "message": message,
            "affected_task_codes": affected_task_codes or [],
            "missing_prerequisite_codes": missing_prerequisite_codes or [],
            "blocking_retained_task_codes": blocking_retained_task_codes or [],
        }
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.message = message
        self.affected_task_codes = affected_task_codes or []
        self.missing_prerequisite_codes = missing_prerequisite_codes or []
        self.blocking_retained_task_codes = blocking_retained_task_codes or []


def parse_iso_date(date_val: Union[str, date, datetime]) -> date:
    """Parse YYYY-MM-DD date string or date object into a date instance."""
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if not isinstance(date_val, str) or not date_val.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or empty date value. Expected YYYY-MM-DD."
        )
    try:
        return datetime.strptime(date_val.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format '{date_val}'. Expected YYYY-MM-DD."
        )


class TaskGraphNode:
    """Lightweight representation of a candidate task for graph validation."""

    def __init__(
        self,
        task_code: str,
        start_date: Union[str, date],
        end_date: Union[str, date],
        dependencies: Optional[List[str]] = None,
        task_id: Optional[str] = None
    ):
        if not isinstance(task_code, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Non-string task code '{task_code}' received. Task codes must be strings."
            )
        self.task_code = task_code.strip()
        if not self.task_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty task code received in graph node."
            )
        self.task_id = task_id
        self.start_date_obj = parse_iso_date(start_date)
        self.end_date_obj = parse_iso_date(end_date)

        clean_deps: List[str] = []
        for d in (dependencies or []):
            if not isinstance(d, str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Non-string dependency reference '{d}' received in task '{self.task_code}'."
                )
            clean_d = d.strip()
            if clean_d:
                clean_deps.append(clean_d)
        self.dependencies = clean_deps

        if self.end_date_obj < self.start_date_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"End date ({self.end_date_obj.isoformat()}) cannot be earlier than start date ({self.start_date_obj.isoformat()}) for task '{self.task_code}'."
            )


def validate_candidate_task_graph(
    candidate_tasks: List[TaskGraphNode],
    project_id: Optional[str] = None,
    structured_error: bool = False,
    retained_task_codes: Optional[Set[str]] = None
) -> None:
    """
    Comprehensive graph and schedule validator.

    Enforces:
    1. Unique, non-empty task codes (no duplicates within project graph).
    2. Missing reference rejection (all dependencies must resolve within the candidate graph).
    3. Self-dependency rejection (task cannot depend on itself).
    4. Circular dependency cycle detection (graph must be a Directed Acyclic Graph).
    5. Prerequisite date ordering rule:
       For every task T and prerequisite P in T.dependencies:
       T.start_date >= P.end_date.
       Boundary-date equality rule:
       A dependent task MAY commence on the same calendar date that its prerequisite
       finishes (T.start_date == P.end_date), but MUST NOT commence strictly prior to
       the prerequisite's end date (T.start_date < P.end_date is rejected).
    """
    if not candidate_tasks:
        return

    code_to_node: Dict[str, TaskGraphNode] = {}
    duplicate_codes: Set[str] = set()

    for node in candidate_tasks:
        if node.task_code in code_to_node:
            duplicate_codes.add(node.task_code)
        code_to_node[node.task_code] = node

    if duplicate_codes:
        sorted_dups = sorted(duplicate_codes)
        first_dup = sorted_dups[0]
        if structured_error:
            raise IncompatibleTaskGraphError(
                error_code="DUPLICATE_TASK_CODE",
                message=f"Duplicate task code '{first_dup}' detected in project graph.",
                affected_task_codes=sorted_dups
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate task code '{first_dup}' detected in project graph."
        )

    # 1. Self-dependency and missing reference checks
    for node in candidate_tasks:
        for dep in node.dependencies:
            if dep == node.task_code:
                if structured_error:
                    raise IncompatibleTaskGraphError(
                        error_code="SELF_DEPENDENCY",
                        message=f"Self-dependency error: task '{node.task_code}' cannot depend on itself.",
                        affected_task_codes=[node.task_code]
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Self-dependency error: task '{node.task_code}' cannot depend on itself."
                )
            if dep not in code_to_node:
                is_retained = bool(retained_task_codes and (node.task_code in retained_task_codes))
                if structured_error:
                    err_code = "RETAINED_TASK_PREREQUISITE_MISSING" if is_retained else "MISSING_PREREQUISITE"
                    blocking = [node.task_code] if is_retained else []
                    msg = (
                        f"Retained task '{node.task_code}' depends on missing prerequisite '{dep}'."
                        if is_retained
                        else f"Dependency reference '{dep}' does not exist in this project."
                    )
                    raise IncompatibleTaskGraphError(
                        error_code=err_code,
                        message=msg,
                        affected_task_codes=[node.task_code],
                        missing_prerequisite_codes=[dep],
                        blocking_retained_task_codes=blocking
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dependency reference '{dep}' does not exist in this project."
                )

    # 2. Cycle detection via DFS
    visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
    cycle_chain: List[str] = []

    def dfs(node_code: str, path: List[str]) -> bool:
        visited[node_code] = 1
        curr_node = code_to_node.get(node_code)
        if curr_node:
            for neighbor in curr_node.dependencies:
                if visited.get(neighbor) == 1:
                    cycle_chain.extend(path + [node_code, neighbor])
                    return True
                if visited.get(neighbor, 0) == 0:
                    if dfs(neighbor, path + [node_code]):
                        return True
        visited[node_code] = 2
        return False

    for code in code_to_node:
        if visited.get(code, 0) == 0:
            if dfs(code, []):
                cycle_str = " -> ".join(cycle_chain)
                if structured_error:
                    raise IncompatibleTaskGraphError(
                        error_code="CIRCULAR_DEPENDENCY",
                        message=f"Circular dependency detected: {cycle_str}",
                        affected_task_codes=cycle_chain
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Circular dependency detected: {cycle_str}"
                )

    # 3. Prerequisite date ordering enforcement
    for node in candidate_tasks:
        for dep_code in node.dependencies:
            prereq_node = code_to_node[dep_code]
            if node.start_date_obj < prereq_node.end_date_obj:
                msg = (
                    f"Schedule conflict: Task '{node.task_code}' starts on "
                    f"{node.start_date_obj.isoformat()}, which is earlier than "
                    f"prerequisite '{prereq_node.task_code}' end date "
                    f"({prereq_node.end_date_obj.isoformat()})."
                )
                if structured_error:
                    raise IncompatibleTaskGraphError(
                        error_code="SCHEDULE_CONFLICT",
                        message=msg,
                        affected_task_codes=[node.task_code, prereq_node.task_code]
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=msg
                )


def allocate_next_task_code(
    db: Session,
    project_id: str,
    reserved_codes: Optional[Set[str]] = None
) -> str:
    """
    Allocate the next unique automatic task code for a project.

    Allocation policy (Batch 06.1):
    - Inspects all existing task codes in the project plus any explicitly reserved codes.
    - Extracts numeric indices from codes matching 'TSK-<number>'.
    - Determines the highest index N across existing and reserved tasks.
    - Next candidate code is TSK-(N + 1).
    - Prevents count-based delete/create collisions by taking the max index rather than total row count.
    - Monotonicity scope: Derives from max(existing/reserved) rather than a permanently monotonic sequence.
      If the highest-numbered task in the project is deleted, its code index may be reused on subsequent allocations.
      Stable, immutable task identity is guaranteed by the database primary key (RoadmapTask.id).
    - If any collision exists with a custom-named task or reserved code, increments forward until an available
      code is guaranteed unique within the project.
    """
    existing_codes = {
        row[0] for row in db.query(RoadmapTask.task_code)
        .filter(RoadmapTask.project_id == project_id)
        .all()
    }
    if reserved_codes:
        existing_codes.update(reserved_codes)

    max_num = 0
    for code in existing_codes:
        m = re.match(r"^TSK-(\d+)$", code, re.IGNORECASE)
        if m:
            try:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass

    candidate_num = max_num + 1
    candidate_code = f"TSK-{str(candidate_num).zfill(2)}"
    while candidate_code in existing_codes:
        candidate_num += 1
        candidate_code = f"TSK-{str(candidate_num).zfill(2)}"

    return candidate_code
