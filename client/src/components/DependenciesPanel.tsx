import React, { useState } from 'react';
import { RoadmapTask } from '../types';
import { GitPullRequest, AlertTriangle, CheckCircle2, Clock, Filter } from 'lucide-react';

interface Props {
  tasks: RoadmapTask[];
}

export const DependenciesPanel: React.FC<Props> = ({ tasks }) => {
  const [filterType, setFilterType] = useState<'all' | 'blocked' | 'unblocked' | 'with-deps'>('all');

  const taskMap = new Map<string, RoadmapTask>();
  tasks.forEach(t => taskMap.set(t.task_code, t));

  // Determine blockers and dependents for each task
  const dependencyAnalysis = tasks.map(task => {
    const deps = task.dependencies || [];
    const prerequisites = deps.map(code => ({
      code,
      task: taskMap.get(code),
      isCompleted: taskMap.get(code)?.status === 'Finished'
    }));

    const isBlocked = prerequisites.some(p => !p.isCompleted);
    const hasDeps = prerequisites.length > 0;

    // Tasks that depend on this task
    const dependents = tasks.filter(t => (t.dependencies || []).includes(task.task_code));

    return {
      task,
      prerequisites,
      dependents,
      isBlocked,
      hasDeps
    };
  });

  const totalDependencies = tasks.reduce((sum, t) => sum + (t.dependencies?.length || 0), 0);
  const blockedTasksCount = dependencyAnalysis.filter(d => d.isBlocked && d.task.status !== 'Finished').length;
  const completedTasksCount = tasks.filter(t => t.status === 'Finished').length;

  const filtered = dependencyAnalysis.filter(item => {
    if (filterType === 'blocked') return item.isBlocked && item.task.status !== 'Finished';
    if (filterType === 'unblocked') return (!item.isBlocked || item.task.status === 'Finished') && item.hasDeps;
    if (filterType === 'with-deps') return item.hasDeps || item.dependents.length > 0;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Overview Metric Banner */}
      <div className="card" style={{ padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--bg-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 40, height: 40, borderRadius: 8, background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-main)' }}>
              <GitPullRequest size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Dependency Graph & Blocking Analysis
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                Upstream prerequisites, downstream blockers, and critical delivery paths
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--primary-text)' }}>{totalDependencies}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Relationships</div>
            </div>
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: blockedTasksCount > 0 ? 'var(--danger-text)' : 'var(--primary-text)' }}>{blockedTasksCount}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Blocked Tasks</div>
            </div>
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--primary-text)' }}>{completedTasksCount}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Finished</div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Filter size={13} /> Filter:
          </span>
          <button
            onClick={() => setFilterType('all')}
            className={`subtab-pill ${filterType === 'all' ? 'active' : ''}`}
            style={{ padding: '4px 12px', fontSize: 12 }}
          >
            All Tasks ({tasks.length})
          </button>
          <button
            onClick={() => setFilterType('blocked')}
            className={`subtab-pill ${filterType === 'blocked' ? 'active' : ''}`}
            style={{ padding: '4px 12px', fontSize: 12 }}
          >
            Blocked ({blockedTasksCount})
          </button>
          <button
            onClick={() => setFilterType('unblocked')}
            className={`subtab-pill ${filterType === 'unblocked' ? 'active' : ''}`}
            style={{ padding: '4px 12px', fontSize: 12 }}
          >
            Ready / Unblocked
          </button>
          <button
            onClick={() => setFilterType('with-deps')}
            className={`subtab-pill ${filterType === 'with-deps' ? 'active' : ''}`}
            style={{ padding: '4px 12px', fontSize: 12 }}
          >
            In Dependency Chain
          </button>
        </div>
      </div>

      {/* Dependency List Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {filtered.map(({ task, prerequisites, dependents, isBlocked, hasDeps }) => (
          <div
            key={task.id}
            className="card"
            style={{
              padding: '16px 20px',
              borderLeft: `4px solid ${
                task.status === 'Finished'
                  ? 'var(--primary-text)'
                  : isBlocked
                  ? 'var(--danger-text)'
                  : hasDeps
                  ? 'var(--primary-text)'
                  : 'var(--border-color)'
              }`
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary-text)', background: 'var(--bg-subtle)', padding: '2px 8px', borderRadius: 6 }}>
                    {task.task_code}
                  </span>
                  <span style={{ fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 600 }}>
                    {task.phase} • {task.timeline}
                  </span>
                  <span className={`badge-priority ${task.priority.toLowerCase()}`} style={{ fontSize: 11 }}>
                    {task.priority}
                  </span>
                </div>
                <h4 style={{ fontSize: 14.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                  {task.title}
                </h4>
                {task.description && (
                  <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
                    {task.description}
                  </p>
                )}
              </div>

              {/* Status Pill */}
              <div>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 9999,
                    fontSize: 12,
                    fontWeight: 700,
                    background:
                      task.status === 'Finished'
                        ? 'var(--bg-subtle)'
                        : task.status === 'Ongoing' || task.status === 'In Progress'
                        ? 'var(--bg-subtle)'
                        : 'var(--bg-subtle)',
                    color:
                      task.status === 'Finished'
                        ? 'var(--primary-text)'
                        : task.status === 'Ongoing' || task.status === 'In Progress'
                        ? 'var(--primary-text)'
                        : 'var(--text-main)'
                  }}
                >
                  {task.status === 'Finished' && <CheckCircle2 size={13} />}
                  {(task.status === 'Ongoing' || task.status === 'In Progress') && <Clock size={13} />}
                  {task.status}
                </span>
              </div>
            </div>

            {/* Prerequisite and Dependent Relationships */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--bg-subtle)' }}>
              {/* Upstream Prerequisites */}
              <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
                  Upstream Prerequisites (Depends On)
                </div>
                {prerequisites.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    No upstream prerequisites (can start immediately)
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {prerequisites.map(p => (
                      <div
                        key={p.code}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: 12,
                          background: 'var(--bg-card)',
                          padding: '6px 10px',
                          borderRadius: 6,
                          border: `1px solid ${p.isCompleted ? 'var(--border-color)' : 'var(--border-color)'}`
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 700, color: 'var(--primary-text)' }}>{p.code}</span>
                          <span style={{ color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
                            {p.task?.title || 'External reference'}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: p.isCompleted ? 'var(--primary-text)' : 'var(--danger-text)',
                            background: p.isCompleted ? 'var(--bg-subtle)' : 'var(--bg-subtle)',
                            padding: '2px 6px',
                            borderRadius: 4
                          }}
                        >
                          {p.isCompleted ? 'Finished' : (p.task?.status || 'Pending')}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Downstream Dependents */}
              <div style={{ background: 'var(--bg-subtle)', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
                  Downstream Dependents (Blocks)
                </div>
                {dependents.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    No other tasks depend on this task
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {dependents.map(d => (
                      <div
                        key={d.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: 12,
                          background: 'var(--bg-card)',
                          padding: '6px 10px',
                          borderRadius: 6,
                          border: '1px solid var(--border-color)'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 700, color: 'var(--primary-text)' }}>{d.task_code}</span>
                          <span style={{ color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
                            {d.title}
                          </span>
                        </div>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {d.timeline}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Condition alert banner */}
            {isBlocked && task.status !== 'Finished' && (
              <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', borderRadius: 6, fontSize: 12, color: 'var(--danger-text)' }}>
                <AlertTriangle size={14} />
                <span>
                  <b>Execution Blocked:</b> Prerequisite tasks are incomplete. Complete upstream items before advancing this task.
                </span>
              </div>
            )}
            {!isBlocked && hasDeps && task.status !== 'Finished' && (
              <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', borderRadius: 6, fontSize: 12, color: 'var(--primary-text)' }}>
                <CheckCircle2 size={14} />
                <span>
                  <b>Ready to Execute:</b> All upstream prerequisites have been completed.
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
