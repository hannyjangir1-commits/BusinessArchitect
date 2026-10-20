import React, { useMemo, useRef, useState } from 'react';
import { RoadmapTask } from '../types';
import { Calendar } from 'lucide-react';

interface Props {
  tasks: RoadmapTask[];
}

interface DatedTask {
  task: RoadmapTask;
  start: Date;
  end: Date;
}

interface TaskGroup {
  name: string;
  color: string;
  tasks: DatedTask[];
  start: Date;
  end: Date;
}

const LEFT_COLUMN_WIDTH = 365;
const PIXELS_PER_DAY = 4.5;
const ROW_PHASE = 42;
const ROW_TASK = 38;
const COLORS = ['var(--primary-text)', 'var(--text-muted)', 'var(--primary-text)', 'var(--primary-text)', 'var(--primary-text)', 'var(--text-muted)', 'var(--danger-text)'];

const utcDate = (year: number, month: number, day: number) => new Date(Date.UTC(year, month, day));
const parseDate = (value: string | undefined): Date => {
  if (!value) return utcDate(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
  const parts = value.slice(0, 10).split('-').map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? utcDate(parts[0], parts[1] - 1, parts[2]) : utcDate(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
};
const daysBetween = (start: Date, end: Date) => Math.round((end.getTime() - start.getTime()) / 86400000);
const isoDate = (date: Date) => date.toISOString().slice(0, 10);
const monthName = (date: Date) => new Intl.DateTimeFormat(undefined, { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
const isFinished = (status: string) => ['finished', 'completed'].includes(status.toLowerCase());
const getLocalToday = () => {
  const now = new Date();
  return utcDate(now.getFullYear(), now.getMonth(), now.getDate());
};

export const GanttChart: React.FC<Props> = ({ tasks }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({});
  const today = getLocalToday();

  const datedTasks = useMemo<DatedTask[]>(() => tasks.map((task) => {
    const start = parseDate(task.start_date);
    const parsedEnd = parseDate(task.end_date);
    const end = parsedEnd < start ? start : parsedEnd;
    return { task, start, end };
  }).sort((a, b) => a.start.getTime() - b.start.getTime()), [tasks]);

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
    const start = utcDate(first.getUTCFullYear(), first.getUTCMonth(), 1);
    const end = utcDate(last.getUTCFullYear(), last.getUTCMonth() + 1, 1);
    const totalDays = Math.max(1, daysBetween(start, end));
    const months: { date: Date; width: number }[] = [];
    for (let month = new Date(start); month < end; month = utcDate(month.getUTCFullYear(), month.getUTCMonth() + 1, 1)) {
      const next = utcDate(month.getUTCFullYear(), month.getUTCMonth() + 1, 1);
      months.push({ date: month, width: daysBetween(month, next) * PIXELS_PER_DAY });
    }
    return {
      start,
      end,
      totalDays,
      width: Math.max(900, totalDays * PIXELS_PER_DAY),
      months,
      label: `${monthName(start)} – ${monthName(utcDate(end.getUTCFullYear(), end.getUTCMonth() - 1, 1))}`
    };
  }, [datedTasks, today]);

  const goToToday = () => {
    if (!scrollRef.current) return;
    const todayOffset = daysBetween(timeline.start, today) * PIXELS_PER_DAY;
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

  const todayX = daysBetween(timeline.start, today) * PIXELS_PER_DAY + PIXELS_PER_DAY / 2;
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-card)', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={18} color="var(--primary-text)" />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>Project Execution Timeline</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <Calendar size={13} /> {timeline.label}
          </div>
          <button type="button" onClick={goToToday} style={{ padding: '5px 12px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 12, fontWeight: 600, color: 'var(--text-main)', cursor: 'pointer' }}>
            Today
          </button>
        </div>
      </div>

      <div ref={scrollRef} style={{ display: 'flex', width: '100%', overflow: 'auto', maxHeight: 620 }}>
        <div style={{ width: LEFT_COLUMN_WIDTH, minWidth: LEFT_COLUMN_WIDTH, borderRight: '1px solid var(--border-color)', background: 'var(--bg-card)', zIndex: 2 }}>
          <div style={{ display: 'flex', height: 50, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-subtle)', fontWeight: 600, fontSize: 11, color: 'var(--text-muted)', alignItems: 'center' }}>
            <div style={{ flex: 1, paddingLeft: 14 }}>Task / Phase</div>
            <div style={{ width: 82, textAlign: 'center' }}>Start</div>
            <div style={{ width: 82, textAlign: 'center' }}>End</div>
          </div>
          {groups.map((group) => {
            const expanded = expandedPhases[group.name] ?? true;
            return (
              <React.Fragment key={group.name}>
                <div onClick={() => setExpandedPhases((current) => ({ ...current, [group.name]: !expanded }))} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setExpandedPhases((current) => ({ ...current, [group.name]: !expanded })); }} style={{ display: 'flex', alignItems: 'center', height: ROW_PHASE, borderBottom: '1px solid var(--border-color)', fontSize: 12.5, fontWeight: 700, color: 'var(--text-main)', cursor: 'pointer', background: 'var(--bg-card)' }}>
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 7, paddingLeft: 12, minWidth: 0 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</span>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: group.color, flex: '0 0 auto' }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{group.name}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 500 }}>({group.tasks.length})</span>
                  </div>
                  <div style={{ width: 82, textAlign: 'center', fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 500 }}>{isoDate(group.start)}</div>
                  <div style={{ width: 82, textAlign: 'center', fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 500 }}>{isoDate(group.end)}</div>
                </div>
                {expanded && group.tasks.map(({ task, start, end }) => (
                  <div key={task.id} title={task.title} style={{ display: 'flex', alignItems: 'center', height: ROW_TASK, borderBottom: '1px solid var(--border-color)', fontSize: 11.5, color: 'var(--text-main)', paddingLeft: 32, background: 'var(--bg-subtle)' }}>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: group.color, flex: '0 0 auto' }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{task.title}</span>
                    </div>
                    <div style={{ width: 82, textAlign: 'center', fontSize: 10, color: 'var(--text-muted)' }}>{isoDate(start)}</div>
                    <div style={{ width: 82, textAlign: 'center', fontSize: 10, color: 'var(--text-muted)' }}>{isoDate(end)}</div>
                  </div>
                ))}
              </React.Fragment>
            );
          })}
        </div>

        <div style={{ flex: '0 0 auto', width: timeline.width, position: 'relative', background: 'var(--bg-card)' }}>
          <div style={{ display: 'flex', height: 50, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-subtle)', position: 'relative', zIndex: 1 }}>
            {timeline.months.map(({ date, width }) => (
              <div key={isoDate(date)} style={{ flex: `0 0 ${width}px`, width, fontSize: 11, fontWeight: 700, color: 'var(--text-main)', textAlign: 'center', borderRight: '1px solid var(--border-color)', lineHeight: '50px' }}>
                {monthName(date)}
              </div>
            ))}
          </div>

          {(() => {
            return groups.map((group) => {
              const expanded = expandedPhases[group.name] ?? true;
              const phaseLeft = daysBetween(timeline.start, group.start) * PIXELS_PER_DAY;
              const phaseWidth = Math.max(8, (daysBetween(group.start, group.end) + 1) * PIXELS_PER_DAY);
              return (
                <React.Fragment key={`timeline-${group.name}`}>
                  <div style={{ height: ROW_PHASE, borderBottom: '1px solid var(--border-color)', position: 'relative' }}>
                    <div title={`${isoDate(group.start)} – ${isoDate(group.end)}`} style={{ position: 'absolute', top: 10, left: phaseLeft + 2, width: Math.max(6, phaseWidth - 4), height: 22, background: group.color, opacity: 0.45, borderRadius: 5 }} />
                  </div>
                  {expanded && group.tasks.map(({ task, start, end }) => {
                    const taskLeft = daysBetween(timeline.start, start) * PIXELS_PER_DAY;
                    const taskWidth = Math.max(8, (daysBetween(start, end) + 1) * PIXELS_PER_DAY);
                    const overdue = !isFinished(task.status) && end < today;
                    const color = isFinished(task.status) ? 'var(--primary-text)' : overdue ? 'var(--danger-text)' : group.color;
                    return (
                      <div key={`bar-row-${task.id}`} style={{ height: ROW_TASK, borderBottom: '1px solid var(--border-color)', position: 'relative', background: 'var(--bg-subtle)' }}>
                        <div title={`${task.title}: ${isoDate(start)} – ${isoDate(end)}${overdue ? ' (overdue)' : ''}`} style={{ position: 'absolute', top: 10, left: taskLeft + 2, width: Math.max(5, taskWidth - 4), height: 18, background: color, borderRadius: 5, boxShadow: '0 1px 3px rgb(69 60 55 / 0.12)' }} />
                      </div>
                    );
                  })}
                </React.Fragment>
              );
            });
          })()}

          {todayX >= 0 && todayX <= timeline.width && (
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: todayX, width: 2, background: 'var(--bg-subtle)', zIndex: 3, pointerEvents: 'none' }}>
              <div style={{ position: 'absolute', top: 3, left: -18, background: 'var(--bg-subtle)', color: 'var(--text-main)', fontSize: 9, fontWeight: 700, padding: '2px 5px', borderRadius: 4 }}>Today</div>
            </div>
          )}
        </div>
      </div>
      <div style={{ padding: '9px 14px', borderTop: '1px solid var(--border-color)', display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 10.5, color: 'var(--text-muted)' }}>
        <span><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--bg-subtle)', marginRight: 5 }} />Completed</span>
        <span><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--danger-text)', marginRight: 5 }} />Overdue unfinished task</span>
        <span><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: 'var(--bg-subtle)', marginRight: 5 }} />Today</span>
      </div>
    </div>
  );
};
