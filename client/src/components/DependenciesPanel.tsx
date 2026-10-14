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
      <div className="card" style={{ padding: '20px 24px', background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
              <GitPullRequest size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                Dependency Graph & Blocking Analysis
              </h3>
              <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 0 0' }}>
                Upstream prerequisites, downstream blockers, and critical delivery paths
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#6366f1' }}>{totalDependencies}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>Relationships</div>
            </div>
            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: blockedTasksCount > 0 ? '#ef4444' : '#10b981' }}>{blockedTasksCount}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>Blocked Tasks</div>
            </div>
            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#10b981' }}>{completedTasksCount}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>Finished</div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 18, paddingTop: 14, borderTop: '1px solid #e2e8f0' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#475569', display: 'flex', alignItems: 'center', gap: 4 }}>
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
                  ? '#10b981'
                  : isBlocked
                  ? '#ef4444'
                  : hasDeps
                  ? '#6366f1'
                  : '#cbd5e1'
              }`
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#6366f1', background: '#ede9fe', padding: '2px 8px', borderRadius: 6 }}>
                    {task.task_code}
                  </span>
                  <span style={{ fontSize: 11.5, color: '#64748b', fontWeight: 600 }}>
                    {task.phase} • {task.timeline}
                  </span>
                  <span className={`badge-priority ${task.priority.toLowerCase()}`} style={{ fontSize: 11 }}>
                    {task.priority}
                  </span>
                </div>
                <h4 style={{ fontSize: 14.5, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                  {task.title}
                </h4>
                {task.description && (
                  <p style={{ fontSize: 12.5, color: '#64748b', margin: '4px 0 0 0', lineHeight: 1.4 }}>
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
                        ? '#dcfce7'
                        : task.status === 'Ongoing' || task.status === 'In Progress'
                        ? '#fef3c7'
                        : '#f1f5f9',
                    color:
                      task.status === 'Finished'
                        ? '#166534'
                        : task.status === 'Ongoing' || task.status === 'In Progress'
                        ? '#92400e'
                        : '#475569'
                  }}
                >
                  {task.status === 'Finished' && <CheckCircle2 size={13} />}
                  {(task.status === 'Ongoing' || task.status === 'In Progress') && <Clock size={13} />}
                  {task.status}
                </span>
              </div>
            </div>

            {/* Prerequisite and Dependent Relationships */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginTop: 14, paddingTop: 12, borderTop: '1px solid #f1f5f9' }}>
              {/* Upstream Prerequisites */}
              <div style={{ background: '#f8fafc', padding: '10px 14px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
                  Upstream Prerequisites (Depends On)
                </div>
                {prerequisites.length === 0 ? (
                  <div style={{ fontSize: 12, color: '#94a3b8', fontStyle: 'italic' }}>
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
                          background: '#ffffff',
                          padding: '6px 10px',
                          borderRadius: 6,
                          border: `1px solid ${p.isCompleted ? '#bbf7d0' : '#fed7aa'}`
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 700, color: '#4338ca' }}>{p.code}</span>
                          <span style={{ color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
                            {p.task?.title || 'External reference'}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: p.isCompleted ? '#166534' : '#c2410c',
                            background: p.isCompleted ? '#dcfce7' : '#ffedd5',
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
              <div style={{ background: '#f8fafc', padding: '10px 14px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
                  Downstream Dependents (Blocks)
                </div>
                {dependents.length === 0 ? (
                  <div style={{ fontSize: 12, color: '#94a3b8', fontStyle: 'italic' }}>
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
                          background: '#ffffff',
                          padding: '6px 10px',
                          borderRadius: 6,
                          border: '1px solid #e2e8f0'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 700, color: '#6366f1' }}>{d.task_code}</span>
                          <span style={{ color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
                            {d.title}
                          </span>
                        </div>
                        <span style={{ fontSize: 11, color: '#64748b' }}>
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
              <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: 6, fontSize: 12, color: '#b91c1c' }}>
                <AlertTriangle size={14} />
                <span>
                  <b>Execution Blocked:</b> Prerequisite tasks are incomplete. Complete upstream items before advancing this task.
                </span>
              </div>
            )}
            {!isBlocked && hasDeps && task.status !== 'Finished' && (
              <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f0fdf4', border: '1px solid #dcfce7', borderRadius: 6, fontSize: 12, color: '#15803d' }}>
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
