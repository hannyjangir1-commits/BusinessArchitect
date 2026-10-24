"""Task identity, dependency graph, and schedule integrity validation service."""

from datetime import datetime, date
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from app.models.all_models import RoadmapTask, Project

# Fixed striped locks for in-process per-project synchronization.
# Strictly bounded constant memory: 256 locks allocated once.
_PROJECT_TASK_LOCK_STRIPES = 256
_STRIPED_PROJECT_LOCKS = [threading.Lock() for _ in range(_PROJECT_TASK_LOCK_STRIPES)]


def get_project_task_lock(project_id: str) -> threading.Lock:
    """Return a deterministic striped lock for the given project ID."""
    clean_id = project_id.strip() if project_id else "default"
    import hashlib
    idx = int(hashlib.md5(clean_id.encode("utf-8")).hexdigest()[:8], 16) % _PROJECT_TASK_LOCK_STRIPES
    return _STRIPED_PROJECT_LOCKS[idx]


def lock_project_for_task_mutation(db: Session, project_id: str) -> None:
    """
    Acquire database-level project lock on PostgreSQL to safely serialize
    concurrent task creations and graph renames per project.
    """
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        # Row-level lock on the parent project row
        db.execute(
            text("SELECT id FROM projects WHERE id = :pid FOR UPDATE"),
            {"pid": project_id}
        )


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
        self.task_code = str(task_code).strip()
        self.task_id = task_id
        self.start_date_obj = parse_iso_date(start_date)
        self.end_date_obj = parse_iso_date(end_date)
        self.dependencies = [str(d).strip() for d in (dependencies or []) if str(d).strip()]

        if self.end_date_obj < self.start_date_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"End date ({self.end_date_obj.isoformat()}) cannot be earlier than start date ({self.start_date_obj.isoformat()}) for task '{self.task_code}'."
            )


def validate_candidate_task_graph(
    candidate_tasks: List[TaskGraphNode],
    project_id: Optional[str] = None
) -> None:
    """
    Comprehensive graph and schedule validator.

    Enforces:
    1. Unique task codes (no duplicates within project graph).
    2. Missing reference rejection (all dependencies must resolve within the project).
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate task code '{sorted_dups[0]}' detected in project graph."
        )

    # 1. Self-dependency and missing reference checks
    for node in candidate_tasks:
        for dep in node.dependencies:
            if dep == node.task_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Self-dependency error: task '{node.task_code}' cannot depend on itself."
                )
            if dep not in code_to_node:
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
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Circular dependency detected: {' -> '.join(cycle_chain)}"
                )

    # 3. Prerequisite date ordering enforcement
    for node in candidate_tasks:
        for dep_code in node.dependencies:
            prereq_node = code_to_node[dep_code]
            if node.start_date_obj < prereq_node.end_date_obj:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Schedule conflict: Task '{node.task_code}' starts on "
                        f"{node.start_date_obj.isoformat()}, which is earlier than "
                        f"prerequisite '{prereq_node.task_code}' end date "
                        f"({prereq_node.end_date_obj.isoformat()})."
                    )
                )


def allocate_next_task_code(db: Session, project_id: str) -> str:
    """
    Monotonically allocate the next unique automatic task code for a project.

    Policy (B01 fix):
    - Inspects all existing task codes in the project.
    - Extracts numeric indices from codes matching 'TSK-<number>'.
    - Determines the highest index N across all existing tasks.
    - Next candidate code is TSK-(N + 1).
    - If a gap was created by deleting an earlier task (e.g. TSK-01 deleted while TSK-02 exists),
      allocation does NOT reuse TSK-02; it continues forward to TSK-03.
    - If any collision exists with a custom-named task, increments forward until an available
      code is guaranteed unique.
    """
    existing_codes = {
        row[0] for row in db.query(RoadmapTask.task_code)
        .filter(RoadmapTask.project_id == project_id)
        .all()
    }

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
