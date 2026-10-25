import React, { useMemo, useRef, useState } from 'react';
import { RoadmapTask } from '../types';
import { Calendar } from 'lucide-react';
import { Dialog } from './common/Dialog';

interface Props {
  tasks: RoadmapTask[];
}

interface DatedTask {
  task: RoadmapTask;
  start: Date;
  end: Date;
  hasValidDates: boolean;
}

interface TaskGroup {
  name: string;
  color: string;
  tasks: DatedTask[];
  start: Date;
  end: Date;
}

type ZoomMode = 'day' | 'week' | 'month';

const LEFT_COLUMN_WIDTH = 360;
const ROW_PHASE = 42;
const ROW_TASK = 38;
const COLORS = [
  'var(--primary-text)',
  'var(--text-muted)',
  'var(--primary-text)',
  'var(--primary-text)',
  'var(--primary-text)',
  'var(--text-muted)',
  'var(--danger-text)'
];

const utcDate = (year: number, month: number, day: number) => new Date(Date.UTC(year, month, day));

const parseDateOrNull = (value: string | undefined): Date | null => {
  if (!value || typeof value !== 'string') return null;
  const parts = value.slice(0, 10).split('-').map(Number);
  if (parts.length === 3 && parts.every(Number.isFinite) && parts[1] >= 1 && parts[1] <= 12 && parts[2] >= 1 && parts[2] <= 31) {
    return utcDate(parts[0], parts[1] - 1, parts[2]);
  }
  return null;
};

const daysBetween = (start: Date, end: Date) => Math.round((end.getTime() - start.getTime()) / 86400000);
const isoDate = (date: Date) => date.toISOString().slice(0, 10);
const monthName = (date: Date) => new Intl.DateTimeFormat(undefined, { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
const dayLabel = (date: Date) => new Intl.DateTimeFormat(undefined, { month: 'numeric', day: 'numeric', timeZone: 'UTC' }).format(date);
const isFinished = (status: string) => ['finished', 'completed'].includes(status.toLowerCase());

const getLocalToday = () => {
  const now = new Date();
  return utcDate(now.getFullYear(), now.getMonth(), now.getDate());
};

export const GanttChart: React.FC<Props> = ({ tasks }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({});
  const [selectedTask, setSelectedTask] = useState<RoadmapTask | null>(null);
  const today = getLocalToday();

  // Evaluate initial scale based on plan duration
  const initialDurationEstimate = useMemo(() => {
    let minDate: Date | null = null;
    let maxDate: Date | null = null;
    for (const t of tasks) {
      const s = parseDateOrNull(t.start_date);
      const e = parseDateOrNull(t.end_date);
      if (s) {
        if (!minDate || s < minDate) minDate = s;
      }
      if (e) {
        if (!maxDate || e > maxDate) maxDate = e;
      }
    }
    if (minDate && maxDate) {
      return daysBetween(minDate, maxDate);
    }
    return 30;
  }, [tasks]);

  const [zoomMode, setZoomMode] = useState<ZoomMode>(() => {
    if (initialDurationEstimate <= 35) return 'day';
    if (initialDurationEstimate <= 90) return 'week';
    return 'month';
  });

  const pixelsPerDay = useMemo(() => {
    switch (zoomMode) {
      case 'day': return 24;
      case 'week': return 10;
      case 'month': return 4.5;
    }
  }, [zoomMode]);

  const datedTasks = useMemo<DatedTask[]>(() => tasks.map((task) => {
    const rawStart = parseDateOrNull(task.start_date);
    const rawEnd = parseDateOrNull(task.end_date);
    const hasValidDates = Boolean(rawStart && rawEnd);

    const start = rawStart || today;
    const fallbackEnd = rawEnd || (rawStart ? rawStart : today);
    const end = fallbackEnd < start ? start : fallbackEnd;

    return { task, start, end, hasValidDates };
  }).sort((a, b) => a.start.getTime() - b.start.getTime()), [tasks, today]);

  const groups = useMemo<TaskGroup[]>(() => {
    const byPhase = new Map<string, DatedTask[]>();
    datedTasks.forEach((entry) => {
      const phase = entry.task.phase?.trim() || 'Execution';
      byPhase.set(phase, [...(byPhase.get(phase) || []), entry]);
    });
    return Array.from(byPhase.entries()).map(([name, groupTasks], index) => ({
      name,
      color: COLORS[index % COLORS.length],
      tasks: groupTasks,
      start: groupTasks.reduce((earliest, item) => item.start < earliest ? item.start : earliest, groupTasks[0].start),
      end: groupTasks.reduce((latest, item) => item.end > latest ? item.end : latest, groupTasks[0].end)
    })).sort((a, b) => a.start.getTime() - b.start.getTime());
  }, [datedTasks]);

  const timeline = useMemo(() => {
    const taskStart = datedTasks.length ? datedTasks[0].start : today;
    const taskEnd = datedTasks.reduce((latest, item) => item.end > latest ? item.end : latest, today);
    const first = taskStart < today ? taskStart : today;
    const last = taskEnd > today ? taskEnd : today;

    // Boundary calculation tailored to zoom mode to avoid giant empty month ranges for short plans
    let start: Date;
    let end: Date;

    if (zoomMode === 'day' || zoomMode === 'week') {
      // Start 2 days before first and end 7 days after last
      const s = new Date(first);
      s.setUTCDate(s.getUTCDate() - 2);
      start = utcDate(s.getUTCFullYear(), s.getUTCMonth(), s.getUTCDate());

      const e = new Date(last);
      e.setUTCDate(e.getUTCDate() + 7);
      end = utcDate(e.getUTCFullYear(), e.getUTCMonth(), e.getUTCDate());
    } else {
      start = utcDate(first.getUTCFullYear(), first.getUTCMonth(), 1);
      end = utcDate(last.getUTCFullYear(), last.getUTCMonth() + 1, 1);
    }

    const totalDays = Math.max(1, daysBetween(start, end));
    const headerIntervals: { key: string; label: string; width: number }[] = [];

    if (zoomMode === 'day') {
      for (let day = new Date(start); day < end; day = utcDate(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate() + 1)) {
        headerIntervals.push({
          key: isoDate(day),
          label: dayLabel(day),
          width: pixelsPerDay
        });
      }
    } else if (zoomMode === 'week') {
      for (let day = new Date(start); day < end; day = utcDate(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate() + 7)) {
        const next = utcDate(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate() + 7);
        const actualNext = next < end ? next : end;
        const width = daysBetween(day, actualNext) * pixelsPerDay;
        headerIntervals.push({
          key: isoDate(day),
          label: `W ${dayLabel(day)}`,
          width
        });
      }
    } else {
      for (let month = new Date(start); month < end; month = utcDate(month.getUTCFullYear(), month.getUTCMonth() + 1, 1)) {
        const next = utcDate(month.getUTCFullYear(), month.getUTCMonth() + 1, 1);
        headerIntervals.push({
          key: isoDate(month),
          label: monthName(month),
          width: daysBetween(month, next) * pixelsPerDay
        });
      }
    }

    return {
      start,
      end,
      totalDays,
      width: Math.max(800, totalDays * pixelsPerDay),
      headerIntervals,
      label: `${isoDate(start)} – ${isoDate(end)}`
    };
  }, [datedTasks, today, zoomMode, pixelsPerDay]);

  const goToToday = () => {
    if (!scrollRef.current) return;
    const todayOffset = daysBetween(timeline.start, today) * pixelsPerDay;
    const visibleWidth = scrollRef.current.clientWidth;
    scrollRef.current.scrollTo({
      left: Math.max(0, LEFT_COLUMN_WIDTH + todayOffset - visibleWidth / 2),
      behavior: 'smooth'
    });
  };

  if (tasks.length === 0) {
    return (
      <div className="card" style={{ padding: 28, textAlign: 'center', color: 'var(--text-muted)' }}>
        <Calendar size={22} color="var(--primary-text)" style={{ margin: '0 auto 8px' }} />
        <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>No roadmap tasks yet</div>
        <div style={{ fontSize: 12, marginTop: 4 }}>Add tasks or generate a roadmap to build the timeline.</div>
      </div>
    );
  }

  const todayX = daysBetween(timeline.start, today) * pixelsPerDay + pixelsPerDay / 2;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Header controls: Timeline title, zoom toggle, and Today button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          flexWrap: 'wrap',
          gap: 10
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={18} color="var(--primary-text)" />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
            Project Execution Timeline
          </h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Zoom Segmented Control */}
          <div
            role="group"
            aria-label="Timeline zoom scale"
            style={{
              display: 'inline-flex',
              background: 'var(--bg-subtle)',
              padding: 3,
              borderRadius: 8,
              border: '1px solid var(--border-color)'
            }}
          >
            {(['day', 'week', 'month'] as ZoomMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setZoomMode(mode)}
                style={{
                  padding: '4px 10px',
                  fontSize: 11.5,
                  fontWeight: zoomMode === mode ? 700 : 500,
                  color: zoomMode === mode ? 'var(--primary-text)' : 'var(--text-muted)',
                  background: zoomMode === mode ? 'var(--bg-card)' : 'transparent',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  boxShadow: zoomMode === mode ? 'var(--shadow-sm)' : 'none',
                  textTransform: 'capitalize'
                }}
              >
                {mode}
              </button>
            ))}
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 10px',
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--text-muted)'
            }}
          >
            <Calendar size={13} /> {timeline.label}
          </div>

          <button
            type="button"
            onClick={goToToday}
            style={{
              padding: '5px 12px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--text-main)',
              cursor: 'pointer'
            }}
          >
            Today
          </button>
        </div>
      </div>

      {/* Gantt View Container with Sticky Task/Phase Column */}
      <div
        ref={scrollRef}
        style={{
          display: 'flex',
          width: '100%',
          overflow: 'auto',
          maxHeight: 620,
          position: 'relative'
        }}
      >
        {/* Sticky Left Column: Tasks and Phases */}
        <div
          style={{
            width: LEFT_COLUMN_WIDTH,
            minWidth: LEFT_COLUMN_WIDTH,
            borderRight: '1px solid var(--border-color)',
            background: 'var(--bg-card)',
            position: 'sticky',
            left: 0,
            zIndex: 10,
            boxShadow: '2px 0 6px rgb(0 0 0 / 0.05)'
          }}
        >
          <div
            style={{
              display: 'flex',
              height: 50,
              borderBottom: '1px solid var(--border-color)',
              background: 'var(--bg-subtle)',
              fontWeight: 600,
              fontSize: 11,
              color: 'var(--text-muted)',
              alignItems: 'center'
            }}
          >
            <div style={{ flex: 1, paddingLeft: 14 }}>Task / Phase</div>
            <div style={{ width: 85, textAlign: 'center' }}>Start</div>
            <div style={{ width: 85, textAlign: 'center' }}>End</div>
          </div>

          {groups.map((group) => {
            const expanded = expandedPhases[group.name] ?? true;
            return (
              <React.Fragment key={group.name}>
                <div
                  onClick={() => setExpandedPhases((current) => ({ ...current, [group.name]: !expanded }))}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setExpandedPhases((current) => ({ ...current, [group.name]: !expanded }));
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    height: ROW_PHASE,
                    borderBottom: '1px solid var(--border-color)',
                    fontSize: 12.5,
                    fontWeight: 700,
                    color: 'var(--text-main)',
                    cursor: 'pointer',
                    background: 'var(--bg-card)'
                  }}
                >
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 7, paddingLeft: 12, minWidth: 0 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</span>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: group.color, flex: '0 0 auto' }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{group.name}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 500 }}>({group.tasks.length})</span>
                  </div>
                  <div style={{ width: 85, textAlign: 'center', fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 500 }}>
                    {isoDate(group.start)}
                  </div>
                  <div style={{ width: 85, textAlign: 'center', fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 500 }}>
                    {isoDate(group.end)}
                  </div>
                </div>

                {expanded && group.tasks.map(({ task, start, end, hasValidDates }) => (
                  <div
                    key={task.id}
                    title={`${task.title} (Click to inspect)`}
                    onClick={() => setSelectedTask(task)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedTask(task);
                      }
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      height: ROW_TASK,
                      borderBottom: '1px solid var(--border-color)',
                      fontSize: 11.5,
                      color: 'var(--text-main)',
                      paddingLeft: 32,
                      background: 'var(--bg-subtle)',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: group.color, flex: '0 0 auto' }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{task.title}</span>
                    </div>
                    <div style={{ width: 85, textAlign: 'center', fontSize: 10, color: 'var(--text-muted)' }}>
                      {hasValidDates ? (
                        isoDate(start)
                      ) : (
                        <span style={{ color: 'var(--warning-text, #d97706)', background: 'rgb(217 119 6 / 0.1)', padding: '1px 5px', borderRadius: 4, fontSize: 9 }}>
                          Date unset
                        </span>
                      )}
                    </div>
                    <div style={{ width: 85, textAlign: 'center', fontSize: 10, color: 'var(--text-muted)' }}>
                      {hasValidDates ? (
                        isoDate(end)
                      ) : (
                        <span style={{ color: 'var(--warning-text, #d97706)', background: 'rgb(217 119 6 / 0.1)', padding: '1px 5px', borderRadius: 4, fontSize: 9 }}>
                          Date unset
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </React.Fragment>
            );
          })}
        </div>

        {/* Timeline Right Area */}
        <div style={{ flex: '0 0 auto', width: timeline.width, position: 'relative', background: 'var(--bg-card)' }}>
          {/* Header Row */}
          <div
            style={{
              display: 'flex',
              height: 50,
              borderBottom: '1px solid var(--border-color)',
              background: 'var(--bg-subtle)',
              position: 'relative',
              zIndex: 1
            }}
          >
            {timeline.headerIntervals.map(({ key, label, width }) => (
              <div
                key={key}
                style={{
                  flex: `0 0 ${width}px`,
                  width,
                  fontSize: 10.5,
                  fontWeight: 600,
                  color: 'var(--text-main)',
                  textAlign: 'center',
                  borderRight: '1px solid var(--border-color)',
                  lineHeight: '50px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Phase and Task Bars */}
          {groups.map((group) => {
            const expanded = expandedPhases[group.name] ?? true;
            const phaseLeft = Math.max(0, daysBetween(timeline.start, group.start) * pixelsPerDay);
            const phaseWidth = Math.max(16, (daysBetween(group.start, group.end) + 1) * pixelsPerDay);

            return (
              <React.Fragment key={`timeline-${group.name}`}>
                {/* Phase Bar */}
                <div style={{ height: ROW_PHASE, borderBottom: '1px solid var(--border-color)', position: 'relative' }}>
                  <div
                    title={`${group.name}: ${isoDate(group.start)} – ${isoDate(group.end)}`}
                    style={{
                      position: 'absolute',
                      top: 10,
                      left: phaseLeft + 2,
                      width: Math.max(12, phaseWidth - 4),
                      height: 22,
                      background: group.color,
                      opacity: 0.35,
                      borderRadius: 5
                    }}
                  />
                </div>

                {/* Task Bars */}
                {expanded && group.tasks.map(({ task, start, end, hasValidDates }) => {
                  const taskLeft = Math.max(0, daysBetween(timeline.start, start) * pixelsPerDay);
                  // Ensure same-day tasks have at least 24px width so they remain visible and clickable!
                  const rawWidth = (daysBetween(start, end) + 1) * pixelsPerDay;
                  const taskWidth = Math.max(24, rawWidth);

                  const overdue = !isFinished(task.status) && end < today && hasValidDates;
                  const color = isFinished(task.status)
                    ? 'var(--primary-text)'
                    : overdue
                    ? 'var(--danger-text)'
                    : group.color;

                  return (
                    <div
                      key={`bar-row-${task.id}`}
                      style={{
                        height: ROW_TASK,
                        borderBottom: '1px solid var(--border-color)',
                        position: 'relative',
                        background: 'var(--bg-subtle)'
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedTask(task)}
                        title={`${task.title}: ${hasValidDates ? `${isoDate(start)} – ${isoDate(end)}` : 'Dates unset'}${overdue ? ' (overdue)' : ''}`}
                        aria-label={`Inspect task ${task.title}`}
                        style={{
                          position: 'absolute',
                          top: 9,
                          left: taskLeft + 2,
                          width: Math.max(24, taskWidth - 4),
                          height: 20,
                          background: color,
                          borderRadius: 5,
                          border: 'none',
                          boxShadow: '0 1px 3px rgb(0 0 0 / 0.12)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          padding: '0 6px',
                          color: '#fff',
                          fontSize: 10,
                          fontWeight: 600,
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          opacity: hasValidDates ? 1 : 0.75
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {task.task_code || task.title}
                        </span>
                      </button>
                    </div>
                  );
                })}
              </React.Fragment>
            );
          })}

          {/* Today Indicator Line */}
          {todayX >= 0 && todayX <= timeline.width && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: todayX,
                width: 2,
                background: 'var(--primary)',
                zIndex: 4,
                pointerEvents: 'none'
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: 4,
                  left: -18,
                  background: 'var(--primary)',
                  color: '#fff',
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '2px 5px',
                  borderRadius: 4
                }}
              >
                Today
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Legend Footer */}
      <div
        style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--border-color)',
          display: 'flex',
          gap: 16,
          flexWrap: 'wrap',
          fontSize: 11,
          color: 'var(--text-muted)',
          alignItems: 'center'
        }}
      >
        <span>
          <i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--primary-text)', marginRight: 6 }} />
          Completed
        </span>
        <span>
          <i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--danger-text)', marginRight: 6 }} />
          Overdue unfinished task
        </span>
        <span>
          <i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--primary)', marginRight: 6 }} />
          Today
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10.5 }}>
          Tip: Click any task bar or row to inspect details.
        </span>
      </div>

      {/* Accessible Task Details Dialog */}
      {selectedTask && (
        <Dialog
          isOpen={true}
          onClose={() => setSelectedTask(null)}
          title={selectedTask.title}
          maxWidth={560}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                {selectedTask.task_code || 'No code'}
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-subtle)', color: 'var(--primary-text)' }}>
                Phase: {selectedTask.phase || 'Execution'}
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: isFinished(selectedTask.status) ? 'rgb(34 197 94 / 0.12)' : 'rgb(59 130 246 / 0.12)', color: isFinished(selectedTask.status) ? 'var(--primary-text)' : 'var(--primary)' }}>
                {selectedTask.status}
              </span>
            </div>

            {selectedTask.description && (
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Description</div>
                <div style={{ fontSize: 13, color: 'var(--text-main)', lineHeight: 1.5, background: 'var(--bg-subtle)', padding: '10px 12px', borderRadius: 6 }}>
                  {selectedTask.description}
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Start Date</div>
                <div style={{ fontSize: 13, color: 'var(--text-main)' }}>
                  {selectedTask.start_date || 'Unset'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Due Date</div>
                <div style={{ fontSize: 13, color: 'var(--text-main)' }}>
                  {selectedTask.end_date || 'Unset'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Assignee / Role</div>
                <div style={{ fontSize: 13, color: 'var(--text-main)' }}>
                  {selectedTask.assigned_to || selectedTask.assigned_role || 'Unassigned'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 2 }}>Duration / Timeline</div>
                <div style={{ fontSize: 13, color: 'var(--text-main)' }}>
                  {selectedTask.timeline || 'Not specified'}
                </div>
              </div>
            </div>

            {selectedTask.dependencies && selectedTask.dependencies.length > 0 && (
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Dependencies</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {selectedTask.dependencies.map((dep, idx) => (
                    <span key={idx} style={{ fontSize: 11.5, background: 'var(--bg-subtle)', padding: '2px 8px', borderRadius: 4, color: 'var(--text-main)' }}>
                      {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setSelectedTask(null)}
                style={{ padding: '7px 16px', fontSize: 13 }}
              >
                Close
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
};
