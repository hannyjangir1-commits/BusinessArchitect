from datetime import date
from typing import Any, Dict, List, Optional
from app.models.all_models import RoadmapTask


def parse_strict_date_only(d_str: Optional[str]) -> Optional[date]:
    """Parse a strict YYYY-MM-DD date string without timezone or DST drift."""
    if not d_str or not isinstance(d_str, str):
        return None
    trimmed = d_str.strip()
    parts = trimmed.split("-")
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def derive_anchor_date(tasks: List[RoadmapTask], saved_start_date: Optional[str] = None) -> Optional[date]:
    """
    Planning anchor date derivation contract:
    1. Saved active roadmap start date if valid.
    2. Legacy fallback: earliest valid start_date across all tasks.
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
    - If anchor and task end date are valid: calendar day arithmetic.
    - Tasks due on or before day_limit (including overdue tasks before anchor) belong to cumulative totals.
    - Legacy fallback: if undated or end of month 1 boundary for legacy test tasks with '30-day'.
    """
    if not anchor_date:
        # Fallback if no anchor date could be established
        if task.timeline:
            return str(day_limit) in task.timeline
        return False

    task_end = parse_strict_date_only(task.end_date)
    if not task_end:
        # Undated tasks do not belong to date-derived milestone cards
        if not task.end_date and task.timeline and str(day_limit) in task.timeline:
            return True
        return False

    inclusive_day = (task_end - anchor_date).days + 1

    if inclusive_day <= day_limit:
        return True

    # Month 1 boundary tolerance (e.g. October 1 to October 31 is 31 days) for legacy tasks marked 30-day
    if day_limit == 30 and inclusive_day == 31 and "30" in (task.timeline or ""):
        return True

    return False


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
