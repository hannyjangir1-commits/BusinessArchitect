import re
from datetime import date
from typing import Any, Dict, List, Optional
from app.models.all_models import RoadmapTask

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_strict_date_only(d_str: Optional[str]) -> Optional[date]:
    """
    Parse a strict YYYY-MM-DD date string without timezone or DST drift.
    Enforces format YYYY-MM-DD, supported year boundary 1900-2100, and calendar validity.
    """
    if not d_str or not isinstance(d_str, str):
        return None
    trimmed = d_str.strip()
    if not DATE_REGEX.match(trimmed):
        return None
    parts = trimmed.split("-")
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if y < 1900 or y > 2100:
            return None
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def derive_anchor_date(tasks: List[RoadmapTask], saved_start_date: Optional[str] = None) -> Optional[date]:
    """
    Planning anchor date derivation contract:
    1. Saved active roadmap start date if valid.
    2. Fallback: earliest valid start_date across all tasks.
    3. If neither valid: returns None (no date-derived milestone membership).
    """
    if saved_start_date:
        parsed = parse_strict_date_only(saved_start_date)
        if parsed:
            return parsed

    earliest: Optional[date] = None
    for t in tasks:
        parsed = parse_strict_date_only(t.start_date)
        if parsed:
            if earliest is None or parsed < earliest:
                earliest = parsed
    return earliest


def is_task_completed(status: Optional[str]) -> bool:
    """Shared completion predicate for tasks."""
    if not status:
        return False
    norm = status.strip().lower()
    return norm in ("completed", "finished")


def due_by_day(task: RoadmapTask, anchor_date: Optional[date], day_limit: int) -> bool:
    """
    Check if a task is due by day_limit (cumulative calendar days from anchor).
    Planning anchor and valid task end_date are strictly required.
    - Inclusive calendar day: (task_end - anchor_date).days + 1.
    - Day 30 belongs to cumulative 30/60/90.
    - Day 31 belongs to cumulative 60/90, NOT 30.
    - Tasks due on or before day_limit (including overdue tasks before anchor, <= 0) belong to cumulative totals.
    - Undated or invalid end dates do not enter milestone totals (return False).
    - Zero timeline string fallbacks. Zero Day-31 exceptions.
    """
    if not anchor_date or not task.end_date:
        return False

    task_end = parse_strict_date_only(task.end_date)
    if not task_end:
        return False

    inclusive_day = (task_end - anchor_date).days + 1
    return inclusive_day <= day_limit


def calculate_roadmap_summary(tasks: List[RoadmapTask], saved_start_date: Optional[str] = None) -> Dict[str, Any]:
    """Calculate date-derived cumulative milestone progress and overall task completion."""
    anchor = derive_anchor_date(tasks, saved_start_date)

    total = len(tasks)
    completed = sum(1 for t in tasks if is_task_completed(t.status))
    overall_progress = int((completed / total) * 100) if total > 0 else 0

    # Cumulative milestones: day 30 tasks also belong to 60 and 90
    m30_tasks = [t for t in tasks if due_by_day(t, anchor, 30)]
    m30_total = len(m30_tasks)
    m30_comp = sum(1 for t in m30_tasks if is_task_completed(t.status))
    m30_prog = int((m30_comp / m30_total) * 100) if m30_total > 0 else 0

    m60_tasks = [t for t in tasks if due_by_day(t, anchor, 60)]
    m60_total = len(m60_tasks)
    m60_comp = sum(1 for t in m60_tasks if is_task_completed(t.status))
    m60_prog = int((m60_comp / m60_total) * 100) if m60_total > 0 else 0

    m90_tasks = [t for t in tasks if due_by_day(t, anchor, 90)]
    m90_total = len(m90_tasks)
    m90_comp = sum(1 for t in m90_tasks if is_task_completed(t.status))
    m90_prog = int((m90_comp / m90_total) * 100) if m90_total > 0 else 0

    return {
        "milestone_30_progress": m30_prog,
        "milestone_30_completed": m30_comp,
        "milestone_30_total": m30_total,
        "milestone_60_progress": m60_prog,
        "milestone_60_completed": m60_comp,
        "milestone_60_total": m60_total,
        "milestone_90_progress": m90_prog,
        "milestone_90_completed": m90_comp,
        "milestone_90_total": m90_total,
        "total_tasks": total,
        "completed_tasks": completed,
        "overall_progress": overall_progress
    }
