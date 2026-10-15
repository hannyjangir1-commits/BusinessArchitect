import React, { useState } from 'react';
import { RoadmapTask } from '../types';
import { Calendar, ChevronDown } from 'lucide-react';

interface Props {
  tasks: RoadmapTask[];
}

export const GanttChart: React.FC<Props> = ({ tasks }) => {
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({
    'Planning & Research': true,
    'System Design': true,
    'Development': true,
    'Testing & Deployment': true,
    'Launch & Monitor': true
  });

  const togglePhase = (phaseName: string) => {
    setExpandedPhases(prev => ({ ...prev, [phaseName]: !prev[phaseName] }));
  };

  const months = ['Oct 2026', 'Nov 2026', 'Dec 2026', 'Jan 2027', 'Feb 2027', 'Mar 2027'];
  const totalWeeks = months.length * 4; // 24 weeks total

  const phases = [
    { name: '1. Planning & Research', color: '#10b981', startWeek: 0, endWeek: 4, startStr: 'Oct 01', endStr: 'Oct 31' },
    { name: '2. System Design', color: '#3b82f6', startWeek: 4, endWeek: 8, startStr: 'Nov 01', endStr: 'Nov 30' },
    { name: '3. Development', color: '#8b5cf6', startWeek: 8, endWeek: 16, startStr: 'Dec 01', endStr: 'Jan 31' },
    { name: '4. Testing & Deployment', color: '#f97316', startWeek: 16, endWeek: 20, startStr: 'Feb 01', endStr: 'Feb 28' },
    { name: '5. Launch & Monitor', color: '#eab308', startWeek: 20, endWeek: 24, startStr: 'Mar 01', endStr: 'Mar 31' }
  ];

  const colWidth = 28; // width per week in px
  const chartWidth = totalWeeks * colWidth;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-card)', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={18} color="#6366f1" />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>Project Execution Timeline</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '5px 10px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>
            Month View <ChevronDown size={14} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <Calendar size={14} /> Oct 2026 - Mar 2027
          </div>
          <button style={{ padding: '5px 12px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 12, fontWeight: 600, color: 'var(--text-main)', cursor: 'pointer' }}>
            Today
          </button>
        </div>
      </div>

      {/* Gantt Interactive Area */}
      <div style={{ display: 'flex', width: '100%', overflowX: 'auto' }}>
        {/* Left Column: Tasks / Phases */}
        <div style={{ width: 340, minWidth: 340, borderRight: '1px solid var(--border-color)', background: 'var(--bg-card)', zIndex: 2 }}>
          {/* Header row */}
          <div style={{ display: 'flex', height: 50, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-subtle)', fontWeight: 600, fontSize: 12, color: 'var(--text-muted)', alignItems: 'center' }}>
            <div style={{ flex: 1, paddingLeft: 16 }}>Task / Phase</div>
            <div style={{ width: 65, textAlign: 'center' }}>Start</div>
            <div style={{ width: 65, textAlign: 'center' }}>End</div>
          </div>

          {/* Rows */}
          {phases.map((p) => {
            const phaseTasks = tasks.filter(t => t.phase.toLowerCase().includes(p.name.slice(3).toLowerCase()));
            const isExpanded = expandedPhases[p.name.slice(3).trim()] ?? true;

            return (
              <React.Fragment key={p.name}>
                {/* Phase Row */}
                <div
                  onClick={() => togglePhase(p.name.slice(3).trim())}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    height: 42,
                    borderBottom: '1px solid var(--border-color)',
                    fontSize: 13,
                    fontWeight: 700,
                    color: 'var(--text-main)',
                    cursor: 'pointer',
                    background: 'var(--bg-card)',
                    transition: 'background 0.15s ease'
                  }}
                >
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 12 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{isExpanded ? '▼' : '▶'}</span>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: p.color }} />
                    {p.name}
                  </div>
                  <div style={{ width: 65, textAlign: 'center', fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 500 }}>{p.startStr}</div>
                  <div style={{ width: 65, textAlign: 'center', fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 500 }}>{p.endStr}</div>
                </div>

                {/* Child Task Rows */}
                {isExpanded && phaseTasks.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      height: 38,
                      borderBottom: '1px solid var(--border-color)',
                      fontSize: 12.5,
                      color: 'var(--text-main)',
                      paddingLeft: 38,
                      background: 'var(--bg-subtle)'
                    }}
                  >
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: p.color }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.title}</span>
                    </div>
                    <div style={{ width: 65, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                      {t.start_date.slice(5)}
                    </div>
                    <div style={{ width: 65, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                      {t.end_date.slice(5)}
                    </div>
                  </div>
                ))}
              </React.Fragment>
            );
          })}
        </div>

        {/* Right Gantt Canvas */}
        <div style={{ flex: 1, minWidth: chartWidth, position: 'relative', background: 'var(--bg-card)' }}>
          {/* Header Row Months & Weeks */}
          <div style={{ height: 50, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-subtle)', display: 'flex', flexDirection: 'column' }}>
            {/* Months row */}
            <div style={{ display: 'flex', height: 26, borderBottom: '1px solid var(--border-color)' }}>
              {months.map((m) => (
                <div
                  key={m}
                  style={{
                    width: colWidth * 4,
                    fontSize: 11.5,
                    fontWeight: 700,
                    color: 'var(--text-main)',
                    textAlign: 'center',
                    borderRight: '1px solid var(--border-color)',
                    lineHeight: '26px'
                  }}
                >
                  {m}
                </div>
              ))}
            </div>
            {/* Weeks row */}
            <div style={{ display: 'flex', height: 24 }}>
              {Array.from({ length: totalWeeks }).map((_, w) => (
                <div
                  key={w}
                  style={{
                    width: colWidth,
                    fontSize: 9.5,
                    color: 'var(--text-muted)',
                    textAlign: 'center',
                    borderRight: '1px solid var(--border-color)',
                    lineHeight: '24px'
                  }}
                >
                  W{(w % 4) + 1}
                </div>
              ))}
            </div>
          </div>

          {/* Today Indicator Line */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: colWidth * 6.5,
              width: 2,
              background: '#6366f1',
              zIndex: 5,
              pointerEvents: 'none'
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 2,
                left: -18,
                background: '#6366f1',
                color: '#fff',
                fontSize: 9,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 4
              }}
            >
              Today
            </div>
          </div>

          {/* Timeline Phase & Task Bars */}
          {phases.map((p) => {
            const phaseTasks = tasks.filter(t => t.phase.toLowerCase().includes(p.name.slice(3).toLowerCase()));
            const isExpanded = expandedPhases[p.name.slice(3).trim()] ?? true;
            const barLeft = p.startWeek * colWidth + 4;
            const barWidth = (p.endWeek - p.startWeek) * colWidth - 8;

            return (
              <React.Fragment key={`bar-${p.name}`}>
                {/* Phase Bar Row */}
                <div style={{ height: 42, borderBottom: '1px solid #f1f5f9', position: 'relative' }}>
                  <div
                    style={{
                      position: 'absolute',
                      top: 10,
                      left: barLeft,
                      width: barWidth,
                      height: 22,
                      background: p.color,
                      borderRadius: 6,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.06)'
                    }}
                  />
                  {/* Milestone diamond at Phase 2 boundary */}
                  {p.name.includes('System Design') && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 14,
                        left: barLeft + barWidth - 4,
                        width: 14,
                        height: 14,
                        background: '#ef4444',
                        transform: 'rotate(45deg)',
                        zIndex: 6
                      }}
                    />
                  )}
                </div>

                {/* Child Task Bar Rows */}
                {isExpanded && phaseTasks.map((t, idx) => {
                  const taskStartWeek = Math.min(22, p.startWeek + idx * 1.5);
                  const taskBarW = Math.max(35, colWidth * 2.2);

                  return (
                    <div key={`task-bar-${t.id}`} style={{ height: 38, borderBottom: '1px solid #f8fafc', position: 'relative' }}>
                      <div
                        style={{
                          position: 'absolute',
                          top: 9,
                          left: taskStartWeek * colWidth + 6,
                          width: taskBarW,
                          height: 18,
                          background: p.color,
                          opacity: 0.8,
                          borderRadius: 4
                        }}
                      />
                    </div>
                  );
                })}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Legend Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, padding: '12px 20px', borderTop: '1px solid var(--border-color)', background: 'var(--bg-subtle)', fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: '#10b981' }} /> Planning</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: '#3b82f6' }} /> Design</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: '#8b5cf6' }} /> Development</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: '#f97316' }} /> Testing</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, borderRadius: '50%', background: '#eab308' }} /> Launch</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, background: '#ef4444', transform: 'rotate(45deg)' }} /> Milestone</div>
      </div>
    </div>
  );
};
