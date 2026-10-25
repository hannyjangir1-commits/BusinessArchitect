import { RoadmapTask, RoadmapSummary } from '../types';

export interface DateOnly {
  year: number;
  month: number;
  day: number;
}

/**
 * Parse strict YYYY-MM-DD date string without timezone or DST drift.
 */
export function parseStrictDateOnly(dStr?: string | null): DateOnly | null {
  if (!dStr || typeof dStr !== 'string') return null;
  const parts = dStr.trim().split('-');
  if (parts.length !== 3) return null;
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

/**
 * Difference in calendar days between two strict date-only values (d1 - d2).
 * Pure UTC day math immune to local timezone or daylight savings changes.
 */
export function differenceInCalendarDays(d1: DateOnly, d2: DateOnly): number {
  const utc1 = Date.UTC(d1.year, d1.month - 1, d1.day);
  const utc2 = Date.UTC(d2.year, d2.month - 1, d2.day);
  return Math.round((utc1 - utc2) / (1000 * 60 * 60 * 24));
}

/**
 * Derive planning anchor date:
 * 1. Saved active roadmap planning start date if valid.
 * 2. Legacy fallback: earliest valid task start_date.
 */
export function deriveAnchorDate(tasks: RoadmapTask[], savedStartDate?: string | null): string | null {
  if (savedStartDate && parseStrictDateOnly(savedStartDate)) {
    return savedStartDate.trim();
  }

  let earliestDate: DateOnly | null = null;
  let earliestStr: string | null = null;

  for (const t of tasks) {
    const parsed = parseStrictDateOnly(t.start_date);
    if (parsed) {
      if (!earliestDate || differenceInCalendarDays(parsed, earliestDate) < 0) {
        earliestDate = parsed;
        earliestStr = t.start_date.trim();
      }
    }
  }

  return earliestStr;
}

/**
 * Shared completion predicate for tasks.
 */
export function isTaskCompleted(status?: string | null): boolean {
  if (!status) return false;
  const s = status.trim().toLowerCase();
  return s === 'completed' || s === 'finished';
}

/**
 * Contract for cumulative milestone membership:
 * A task is due by dayCount if its inclusive calendar day from anchor is <= dayCount.
 * Tasks due on or before day 30 also belong to day 60 and 90 cumulative totals.
 */
export function dueByDay(task: RoadmapTask, anchor: string | null | undefined, dayLimit: number): boolean {
  if (!anchor) {
    if (task.timeline) return task.timeline.includes(String(dayLimit));
    return false;
  }

  const due = parseStrictDateOnly(task.end_date);
  const base = parseStrictDateOnly(anchor);

  if (!due || !base) {
    if (!task.end_date && task.timeline && task.timeline.includes(String(dayLimit))) {
      return true;
    }
    return false;
  }

  const inclusiveDay = differenceInCalendarDays(due, base) + 1;

  if (inclusiveDay <= dayLimit) {
    return true;
  }

  // Month 1 boundary tolerance (e.g. October 1 to October 31 is 31 days) for legacy tasks marked 30-day
  if (dayLimit === 30 && inclusiveDay === 31 && (task.timeline || '').includes('30')) {
    return true;
  }

  return false;
}

/**
 * Classify a task for UI filters:
 * '30-day': due by day 30
 * '60-day': due between day 31 and 60
 * '90-day': due between day 61 and 90
 * 'later': due past day 90
 * 'undated': no valid end date
 */
export function classifyTaskMilestone(
  task: RoadmapTask,
  anchor: string | null | undefined
): '30-day' | '60-day' | '90-day' | 'later' | 'undated' {
  if (!anchor) {
    if (task.timeline?.includes('30')) return '30-day';
    if (task.timeline?.includes('60')) return '60-day';
    if (task.timeline?.includes('90')) return '90-day';
    return task.end_date ? 'later' : 'undated';
  }

  const due = parseStrictDateOnly(task.end_date);
  const base = parseStrictDateOnly(anchor);

  if (!due || !base) {
    if (task.timeline?.includes('30')) return '30-day';
    if (task.timeline?.includes('60')) return '60-day';
    if (task.timeline?.includes('90')) return '90-day';
    return 'undated';
  }

  const inclusiveDay = differenceInCalendarDays(due, base) + 1;

  if (inclusiveDay <= 30 || (inclusiveDay === 31 && (task.timeline || '').includes('30'))) {
    return '30-day';
  }
  if (inclusiveDay <= 60) {
    return '60-day';
  }
  if (inclusiveDay <= 90) {
    return '90-day';
  }
  return 'later';
}

/**
 * Derive full summary matching the backend calculate_roadmap_summary contract
 */
export function calculateLocalRoadmapSummary(
  tasks: RoadmapTask[],
  savedStartDate?: string | null
): RoadmapSummary {
  const anchor = deriveAnchorDate(tasks, savedStartDate);

  const total = tasks.length;
  const completed = tasks.filter(t => isTaskCompleted(t.status)).length;
  const overall_progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  const m30 = tasks.filter(t => dueByDay(t, anchor, 30));
  const m30_total = m30.length;
  const m30_completed = m30.filter(t => isTaskCompleted(t.status)).length;
  const m30_progress = m30_total > 0 ? Math.round((m30_completed / m30_total) * 100) : 0;

  const m60 = tasks.filter(t => dueByDay(t, anchor, 60));
  const m60_total = m60.length;
  const m60_completed = m60.filter(t => isTaskCompleted(t.status)).length;
  const m60_progress = m60_total > 0 ? Math.round((m60_completed / m60_total) * 100) : 0;

  const m90 = tasks.filter(t => dueByDay(t, anchor, 90));
  const m90_total = m90.length;
  const m90_completed = m90.filter(t => isTaskCompleted(t.status)).length;
  const m90_progress = m90_total > 0 ? Math.round((m90_completed / m90_total) * 100) : 0;

  return {
    milestone_30_progress: m30_progress,
    milestone_30_completed: m30_completed,
    milestone_30_total: m30_total,
    milestone_60_progress: m60_progress,
    milestone_60_completed: m60_completed,
    milestone_60_total: m60_total,
    milestone_90_progress: m90_progress,
    milestone_90_completed: m90_completed,
    milestone_90_total: m90_total,
    total_tasks: total,
    completed_tasks: completed,
    overall_progress
  };
}
