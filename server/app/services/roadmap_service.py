"""Domain service for Roadmap scheduling, cycle detection, and task reconciliation."""
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.all_models import Project, RoadmapTask
from app.schemas.modules import RoadmapPlanningRequest


class RoadmapDomainService:
    @staticmethod
    def parse_roadmap_date(value: Any) -> Optional[date]:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                clean_val = value.strip()
                return date.fromisoformat(clean_val[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def matches_planning_items(task: Dict[str, Any], items: List[str]) -> bool:
        ignored = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
            "have", "has", "been", "already", "complete", "completed", "defined", "work", "task",
        }
        task_text = f"{task.get('title', '')} {task.get('description', '')}".lower()
        task_terms = set(re.findall(r"[a-z0-9]+", task_text)) - ignored
        if not task_terms:
            return False
        for item in items:
            item_text = str(item).strip().lower()
            item_terms = set(re.findall(r"[a-z0-9]+", item_text)) - ignored
            if item_text and (item_text in task_text or task_text.strip() in item_text):
                return True
            overlap = len(task_terms & item_terms)
            if len(item_terms) >= 2 and overlap >= 2 and overlap / len(item_terms) >= 0.65:
                return True
        return False

    @staticmethod
    def detect_and_break_dependency_cycles(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect circular dependencies (e.g. A -> B and B -> A) and remove offending back-edges."""
        adj: Dict[str, List[str]] = {}
        for t in tasks:
            code = t.get("task_code")
            if code:
                deps = t.get("dependencies") or []
                adj[code] = [d for d in deps if isinstance(d, str)]

        visited: Dict[str, int] = {}

        def dfs(node: str, path: List[str]):
            visited[node] = 1
            path.append(node)
            for neighbor in list(adj.get(node, [])):
                if visited.get(neighbor) == 1:
                    # Cycle detected: remove back-edge
                    if neighbor in adj[node]:
                        adj[node].remove(neighbor)
                    for t in tasks:
                        if t.get("task_code") == node:
                            t_deps = t.get("dependencies", [])
                            if neighbor in t_deps:
                                t_deps.remove(neighbor)
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor, path)
            path.pop()
            visited[node] = 2

        for code in list(adj.keys()):
            if visited.get(code, 0) == 0:
                dfs(code, [])
        return tasks

    @classmethod
    def normalize_roadmap_schedule(
        cls, data: Dict[str, Any], planning: RoadmapPlanningRequest
    ) -> Dict[str, Any]:
        """Repair malformed dates and shift unfinished work to the requested/current date."""
        result = dict(data)
        today = date.today()
        baseline = max(planning.start_date, today)
        tasks = [dict(task) for task in result.get("tasks", []) if isinstance(task, dict)]
        completed_items = [item.item for item in planning.checklist if item.status == "Completed"]
        completed_items.extend(part.strip() for part in re.split(r"[\n;]+", planning.completed_work) if part.strip())
        in_progress_items = [item.item for item in planning.checklist if item.status == "In progress"]
        in_progress_items.extend(part.strip() for part in re.split(r"[\n;]+", planning.in_progress_work) if part.strip())
        cursor = baseline

        for index, task in enumerate(tasks):
            task["task_code"] = task.get("task_code") or f"TSK-{index + 1:02d}"
            task["phase"] = str(task.get("phase") or "Execution").strip() or "Execution"
            raw_status = str(task.get("status") or "Pending").strip().lower()
            if raw_status in {"in progress", "ongoing", "underway"} and cls.matches_planning_items(task, in_progress_items):
                task["status"] = "In Progress"
            elif raw_status in {"finished", "completed", "done"} and cls.matches_planning_items(task, completed_items):
                task["status"] = "Finished"
            else:
                task["status"] = "Pending"
            start = cls.parse_roadmap_date(task.get("start_date")) or cursor
            end = cls.parse_roadmap_date(task.get("end_date")) or (start + timedelta(days=6))
            task["start_date"] = start.isoformat()
            task["end_date"] = end.isoformat()
            cursor = max(cursor, max(start, end) + timedelta(days=1))

        unfinished_starts = [
            cls.parse_roadmap_date(task["start_date"])
            for task in tasks
            if str(task.get("status", "Pending")).strip().lower() not in {"finished", "completed"}
        ]
        valid_starts = [value for value in unfinished_starts if value]
        shift_days = max(0, (baseline - min(valid_starts)).days) if valid_starts else 0

        for task in tasks:
            is_finished = str(task.get("status", "Pending")).strip().lower() in {"finished", "completed"}
            if not is_finished and shift_days:
                start = cls.parse_roadmap_date(task["start_date"]) + timedelta(days=shift_days)
                end = cls.parse_roadmap_date(task["end_date"]) + timedelta(days=shift_days)
                task["start_date"] = start.isoformat()
                task["end_date"] = end.isoformat()

        # Consistent 4-color palette accents for phase differentiation
        phase_colors = ["#2563eb", "#0f172a", "#475569", "#64748b"]
        raw_phases = {phase.get("name"): phase for phase in (result.get("phases") or []) if isinstance(phase, dict)}
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for task in tasks:
            grouped.setdefault(task["phase"], []).append(task)

        phases = []
        for index, (name, phase_tasks) in enumerate(grouped.items()):
            first = raw_phases.get(name, {})
            phases.append({
                "name": name,
                "color": first.get("color") or phase_colors[index % len(phase_colors)],
                "start_date": min(task["start_date"] for task in phase_tasks),
                "end_date": max(task["end_date"] for task in phase_tasks),
                "description": first.get("description") or f"Work grouped under {name}.",
            })

        # Do not silently delete dependency edges; candidate graph validation will detect and report cycles cleanly
        result["tasks"] = tasks
        result["phases"] = phases
        return result

    @staticmethod
    def canonicalize_incoming_tasks(
        db: Session,
        project: Project,
        tasks_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate and canonicalize incoming roadmap tasks into a pure canonical dictionary list.
        Does NOT mutate caller-owned dictionaries.

        Guarantees:
        - Acquires project transaction lock to read authoritative existing codes.
        - Refreshes identity map via populate_existing=True.
        - Two-pass code reservation: collects all valid explicit incoming codes before
          allocating missing codes, preventing collisions with explicit subsequent tasks.
        - Deterministically allocates missing codes against reserved existing and incoming codes.
        - Normalizes whitespace on task codes and dependencies identically.
        - Rejects non-string codes/deps and invalid date ranges (end < start).
        """
        from fastapi import HTTPException, status
        from app.services.task_graph_validator import (
            project_first_lock,
            allocate_next_task_code_from_reserved,
            get_authoritative_project_tasks,
            IncompatibleTaskGraphError,
            parse_iso_date,
        )

        with project_first_lock(db, project.id):
            existing_tasks = get_authoritative_project_tasks(db, project.id)
            existing_by_code = {t.task_code: t for t in existing_tasks if t.task_code}
            base_date_str = project.created_at.strftime("%Y-%m-%d") if project.created_at else "2026-10-01"

            # Pass 1: Validate input types and collect all explicit incoming codes
            explicit_incoming_codes: set = set()
            for idx, t in enumerate(tasks_data):
                if not isinstance(t, dict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid task entry at index {idx}. Task items must be JSON objects."
                    )
                raw_code = t.get("task_code")
                if raw_code is not None:
                    if not isinstance(raw_code, str):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Non-string task code '{raw_code}' received. Task codes must be strings."
                        )
                    code = raw_code.strip()
                    if code:
                        # Reject duplicate incoming explicit codes
                        if code in explicit_incoming_codes:
                            raise IncompatibleTaskGraphError(
                                error_code="DUPLICATE_TASK_CODE",
                                message=f"Duplicate task code '{code}' detected in incoming roadmap plan.",
                                affected_task_codes=[code]
                            )
                        explicit_incoming_codes.add(code)

                        # Reject collision with existing manual tasks
                        if code in existing_by_code and not existing_by_code[code].is_ai_generated:
                            raise IncompatibleTaskGraphError(
                                error_code="MANUAL_TASK_COLLISION",
                                message=f"Incoming task code '{code}' conflicts with an existing manual task.",
                                affected_task_codes=[code]
                            )

            # Reservation set = all existing project codes + all explicit incoming codes
            reserved_codes = set(existing_by_code.keys()) | explicit_incoming_codes

            # Pass 2: Allocate missing codes in input order and canonicalize fields
            canonical_tasks: List[Dict[str, Any]] = []
            for idx, t in enumerate(tasks_data):
                raw_code = t.get("task_code")
                code = raw_code.strip() if (raw_code is not None and isinstance(raw_code, str)) else None
                if not code:
                    code = allocate_next_task_code_from_reserved(reserved_codes)
                    reserved_codes.add(code)

                # Validate dependencies
                raw_deps = t.get("dependencies") or []
                if not isinstance(raw_deps, list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Dependencies for task '{code}' must be a list of task codes."
                    )
                clean_deps: List[str] = []
                for d in raw_deps:
                    if not isinstance(d, str):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Non-string dependency reference '{d}' in task '{code}'. Dependencies must be strings."
                        )
                    trimmed_d = d.strip()
                    if trimmed_d:
                        clean_deps.append(trimmed_d)

                # Validate dates
                raw_s_date = t.get("start_date") or base_date_str
                raw_e_date = t.get("end_date") or raw_s_date
                s_date_obj = parse_iso_date(raw_s_date)
                e_date_obj = parse_iso_date(raw_e_date)
                if e_date_obj < s_date_obj:
                    raise IncompatibleTaskGraphError(
                        error_code="INVALID_DATE_RANGE",
                        message=f"End date ({e_date_obj.isoformat()}) cannot be earlier than start date ({s_date_obj.isoformat()}) for task '{code}'.",
                        affected_task_codes=[code]
                    )

                # Build pure copy with canonicalized attributes
                canonical_t = dict(t)
                canonical_t["task_code"] = code
                canonical_t["start_date"] = s_date_obj.isoformat()
                canonical_t["end_date"] = e_date_obj.isoformat()
                canonical_t["dependencies"] = clean_deps
                canonical_t["branch_type"] = t.get("branch_type", "core")
                canonical_t["parent_outcome"] = t.get("parent_outcome")
                canonical_t["definition_of_done"] = t.get("definition_of_done")
                canonical_t["acceptance_criteria"] = list(t.get("acceptance_criteria") or [])
                canonical_t["edge_type"] = t.get("edge_type", "prerequisite")
                canonical_t["roadmap_mode"] = t.get("roadmap_mode", "execution")
                canonical_tasks.append(canonical_t)

            return canonical_tasks

    @classmethod
    def reconcile_roadmap_tasks(
        cls,
        db: Session,
        project: Project,
        tasks_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Synchronize the relational RoadmapTask table with the roadmap JSON tasks.

        Multi-stage pipeline:
        Stage 1: Acquire the required project transaction lock (Project-first protocol).
        Stage 2: Read authoritative current task state with identity-map freshness.
        Stage 3: Validate incoming structure and canonical identifiers via canonicalize_incoming_tasks.
        Stage 4: Construct the complete proposed final task set in memory.
        Stage 5: Validate candidate merged graph (no cycles, no missing refs, correct schedule order).
        Stage 6: Apply inserts, updates, and deletions in relational table.
        Stage 7: Flush without committing (caller transaction retains commit ownership).
        """
        from sqlalchemy.orm.attributes import flag_modified
        from app.services.task_graph_validator import (
            project_first_lock,
            validate_candidate_task_graph,
            TaskGraphNode,
            IncompatibleTaskGraphError,
            get_authoritative_project_tasks,
        )

        with project_first_lock(db, project.id):
            # Stage 2 & 3: Authoritative canonicalization under project lock
            normalized_incoming = cls.canonicalize_incoming_tasks(db, project, tasks_data)

            # Authoritative read of current tasks
            existing_tasks = get_authoritative_project_tasks(db, project.id)
            existing_by_code = {t.task_code: t for t in existing_tasks if t.task_code}
            existing_manual_tasks = [t for t in existing_tasks if not t.is_ai_generated]
            existing_completed_ai_tasks = [
                t for t in existing_tasks
                if t.is_ai_generated and t.status in ("Finished", "Completed")
            ]

            # Stage 4: Construct proposed complete final task set in memory
            active_incoming_codes = {t["task_code"] for t in normalized_incoming}

            # Candidate deletion set: Unfinished AI tasks omitted from incoming plan
            candidate_deletions = [
                cur for cur in existing_tasks
                if cur.task_code not in active_incoming_codes
                and cur.is_ai_generated
                and cur.status not in ("Finished", "Completed")
            ]
            deleted_codes = {cur.task_code for cur in candidate_deletions}

            # Retained tasks: all manual tasks + completed AI tasks not in incoming plan
            retained_manual_tasks = existing_manual_tasks
            retained_completed_tasks = [
                cur for cur in existing_completed_ai_tasks
                if cur.task_code not in active_incoming_codes
            ]
            all_retained_existing = retained_manual_tasks + retained_completed_tasks
            retained_task_codes = {t.task_code for t in all_retained_existing}

            # Pre-check: Ensure retained tasks do not lose prerequisites to candidate deletions (Reproduction B)
            blocking_retained: List[str] = []
            missing_prereqs: set = set()
            for ret in all_retained_existing:
                deps = ret.dependencies or []
                for d in deps:
                    if d in deleted_codes:
                        blocking_retained.append(ret.task_code)
                        missing_prereqs.add(d)

            if blocking_retained:
                sorted_missing = sorted(list(missing_prereqs))
                raise IncompatibleTaskGraphError(
                    error_code="RETAINED_TASK_PREREQUISITE_MISSING",
                    message=(
                        f"Cannot reconcile roadmap: retained task(s) {blocking_retained} depend on "
                        f"prerequisite(s) {sorted_missing} omitted from the new plan."
                    ),
                    affected_task_codes=blocking_retained,
                    missing_prerequisite_codes=sorted_missing,
                    blocking_retained_task_codes=blocking_retained
                )

            # Build candidate graph nodes representing the proposed post-reconciliation state
            candidate_nodes: List[TaskGraphNode] = []
            for t in normalized_incoming:
                existing_row = existing_by_code.get(t["task_code"])
                candidate_nodes.append(TaskGraphNode(
                    task_code=t["task_code"],
                    start_date=t["start_date"],
                    end_date=t["end_date"],
                    dependencies=t["dependencies"],
                    task_id=existing_row.id if existing_row else None
                ))

            for ret in all_retained_existing:
                candidate_nodes.append(TaskGraphNode(
                    task_code=ret.task_code,
                    start_date=ret.start_date,
                    end_date=ret.end_date,
                    dependencies=ret.dependencies or [],
                    task_id=ret.id
                ))

            # Stage 5: Validate the merged candidate graph atomically
            validate_candidate_task_graph(
                candidate_nodes,
                project_id=project.id,
                structured_error=True,
                retained_task_codes=retained_task_codes
            )

            # Stage 6: Apply inserts, updates, and deletions
            for idx, t in enumerate(normalized_incoming):
                code = t["task_code"]
                s_date = t["start_date"]
                e_date = t["end_date"]
                deps = t["dependencies"]

                if code in existing_by_code:
                    cur = existing_by_code[code]
                    # Preserve user-maintained execution status
                    if cur.status not in ("In Progress", "Ongoing", "Finished", "Completed"):
                        raw_st = t.get("status", "Pending")
                        cur.status = "In Progress" if raw_st in ("In Progress", "Ongoing") else raw_st
                    cur.phase = t.get("phase", cur.phase)
                    cur.title = t.get("title", cur.title)
                    cur.description = t.get("description", cur.description)
                    cur.timeline = t.get("timeline", cur.timeline)
                    cur.start_date = s_date
                    cur.end_date = e_date
                    cur.priority = t.get("priority", cur.priority)
                    cur.dependencies = deps
                    cur.deliverables = t.get("deliverables", cur.deliverables)
                    cur.effort = t.get("effort", cur.effort)
                    # Preserve user assignments if already set
                    if not cur.assigned_to or cur.assigned_to == "Unassigned":
                        cur.assigned_to = t.get("assigned_to", "Unassigned")
                    if not cur.assigned_role:
                        cur.assigned_role = t.get("assigned_role")
                    if not cur.department:
                        cur.department = t.get("department")
                    cur.steps = t.get("steps", cur.steps or [])
                    cur.is_overloaded = t.get("is_overloaded", cur.is_overloaded or False)
                    cur.branch_type = t.get("branch_type", cur.branch_type or "core")
                    cur.parent_outcome = t.get("parent_outcome", cur.parent_outcome)
                    cur.definition_of_done = t.get("definition_of_done", cur.definition_of_done)
                    cur.acceptance_criteria = t.get("acceptance_criteria", cur.acceptance_criteria or [])
                    cur.edge_type = t.get("edge_type", cur.edge_type or "prerequisite")
                    cur.roadmap_mode = t.get("roadmap_mode", cur.roadmap_mode or "execution")
                    cur.order_index = idx
                    flag_modified(cur, "dependencies")
                    flag_modified(cur, "steps")
                    flag_modified(cur, "acceptance_criteria")
                else:
                    raw_st = t.get("status", "Pending")
                    st_val = "In Progress" if raw_st in ("In Progress", "Ongoing") else raw_st
                    new_task = RoadmapTask(
                        project_id=project.id,
                        task_code=code,
                        phase=t.get("phase", "Planning & Research"),
                        title=t.get("title", f"Task {idx + 1}"),
                        description=t.get("description", ""),
                        timeline=t.get("timeline", "30-day"),
                        start_date=s_date,
                        end_date=e_date,
                        priority=t.get("priority", "Medium"),
                        status=st_val,
                        dependencies=deps,
                        deliverables=t.get("deliverables", ""),
                        effort=t.get("effort", "1 week"),
                        assigned_to=t.get("assigned_to", "Unassigned"),
                        assigned_role=t.get("assigned_role"),
                        department=t.get("department"),
                        steps=t.get("steps", []),
                        is_overloaded=t.get("is_overloaded", False),
                        order_index=idx,
                        is_ai_generated=True,
                        branch_type=t.get("branch_type", "core"),
                        parent_outcome=t.get("parent_outcome"),
                        definition_of_done=t.get("definition_of_done"),
                        acceptance_criteria=t.get("acceptance_criteria", []),
                        edge_type=t.get("edge_type", "prerequisite"),
                        roadmap_mode=t.get("roadmap_mode", "execution"),
                    )
                    db.add(new_task)

            # Safely delete candidate deletions (verified to have no dependents)
            for cur in candidate_deletions:
                db.delete(cur)

            # Stage 7: Flush without committing (owning transaction commits)
            db.flush()
            return normalized_incoming
