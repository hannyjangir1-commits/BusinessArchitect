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
                return date.fromisoformat(value[:10])
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
            if end < start:
                end = start + timedelta(days=6)
            task["start_date"] = start.isoformat()
            task["end_date"] = end.isoformat()
            cursor = max(cursor, end + timedelta(days=1))

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

        cls.detect_and_break_dependency_cycles(tasks)
        result["tasks"] = tasks
        result["phases"] = phases
        return result

    @staticmethod
    def reconcile_roadmap_tasks(db: Session, project: Project, tasks_data: List[Dict[str, Any]]) -> None:
        """Synchronize the relational RoadmapTask table with the roadmap JSON tasks."""
        existing_tasks = db.query(RoadmapTask).filter(RoadmapTask.project_id == project.id).all()
        existing_by_code = {t.task_code: t for t in existing_tasks}

        base_date_str = project.created_at.strftime("%Y-%m-%d") if project.created_at else "2026-10-01"
        active_codes = set()
        seen_incoming_codes = set()

        for idx, t in enumerate(tasks_data):
            raw_code = t.get("task_code")
            code = raw_code.strip() if raw_code and str(raw_code).strip() else f"TSK-{str(idx + 1).zfill(2)}"
            if code in seen_incoming_codes:
                suffix = 2
                while f"{code}_{suffix}" in seen_incoming_codes or f"{code}_{suffix}" in existing_by_code:
                    suffix += 1
                code = f"{code}_{suffix}"
            seen_incoming_codes.add(code)
            active_codes.add(code)
            s_date = t.get("start_date") or base_date_str
            e_date = t.get("end_date") or s_date
            if e_date < s_date:
                e_date = s_date

            if code in existing_by_code:
                cur = existing_by_code[code]
                if cur.status not in ("In Progress", "Ongoing", "Finished"):
                    raw_st = t.get("status", "Pending")
                    cur.status = "In Progress" if raw_st in ("In Progress", "Ongoing") else raw_st
                cur.phase = t.get("phase", cur.phase)
                cur.title = t.get("title", cur.title)
                cur.description = t.get("description", cur.description)
                cur.timeline = t.get("timeline", cur.timeline)
                cur.start_date = s_date
                cur.end_date = e_date
                cur.priority = t.get("priority", cur.priority)
                cur.dependencies = t.get("dependencies", cur.dependencies)
                cur.deliverables = t.get("deliverables", cur.deliverables)
                cur.effort = t.get("effort", cur.effort)
                cur.assigned_to = t.get("assigned_to", cur.assigned_to or "Unassigned")
                cur.assigned_role = t.get("assigned_role", cur.assigned_role)
                cur.department = t.get("department", cur.department)
                cur.steps = t.get("steps", cur.steps or [])
                cur.is_overloaded = t.get("is_overloaded", cur.is_overloaded or False)
                cur.order_index = idx
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
                    dependencies=t.get("dependencies", []),
                    deliverables=t.get("deliverables", ""),
                    effort=t.get("effort", "1 week"),
                    assigned_to=t.get("assigned_to", "Unassigned"),
                    assigned_role=t.get("assigned_role"),
                    department=t.get("department"),
                    steps=t.get("steps", []),
                    is_overloaded=t.get("is_overloaded", False),
                    order_index=idx,
                    is_ai_generated=True,
                )
                db.add(new_task)

        # Delete AI-generated tasks that are no longer part of active plan
        for cur in existing_tasks:
            if cur.task_code not in active_codes and cur.is_ai_generated and cur.status not in ("Finished", "Completed"):
                db.delete(cur)

        db.flush()
