import React, { useState, useEffect } from 'react';
import { RoadmapTask, RoadmapPhase } from '../types';
import {
  CheckCircle2, AlertTriangle, User,
  GitPullRequest, ListChecks, X, Sparkles
} from 'lucide-react';

interface Props {
  projectName: string;
  stage: string;
  phases: RoadmapPhase[];
  tasks: RoadmapTask[];
}

export const RoadmapMindMap: React.FC<Props> = ({ projectName, stage, phases, tasks }) => {
  const [selectedTask, setSelectedTask] = useState<RoadmapTask | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<RoadmapPhase | null>(null);

  // Close drawer on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedTask(null);
        setSelectedPhase(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Group tasks by phase name
  const groupedTasks: Record<string, RoadmapTask[]> = {};
  phases.forEach(p => { groupedTasks[p.name] = []; });
  tasks.forEach(t => {
    if (!groupedTasks[t.phase]) {
      groupedTasks[t.phase] = [];
    }
    groupedTasks[t.phase].push(t);
  });

  const getStatusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'finished':
      case 'completed':
        return { bg: 'var(--bg-subtle)', text: 'var(--primary-text)', border: 'var(--border-color)' };
      case 'in progress':
      case 'ongoing':
        return { bg: 'var(--bg-subtle)', text: 'var(--primary-text)', border: 'var(--border-color)' };
      default:
        return { bg: 'var(--bg-card)', text: 'var(--primary-text)', border: 'var(--bg-subtle)' };
    }
  };

  const getPriorityBadge = (priority?: string) => {
    switch (priority?.toLowerCase()) {
      case 'critical':
        return { bg: 'var(--bg-subtle)', text: 'var(--danger-text)' };
      case 'high':
        return { bg: 'var(--bg-subtle)', text: 'var(--primary-text)' };
      default:
        return { bg: 'var(--bg-card)', text: 'var(--primary-text)' };
    }
  };

  return (
    <div style={{ position: 'relative', width: '100%', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--bg-subtle)', padding: 20 }}>
      {/* Mind Map Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={18} color="var(--primary-text)" /> Interactive Delivery Roadmap
          </h3>
          <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
            Select a task to see steps, assignment, and dependencies.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 11.5, color: 'var(--primary-text)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--bg-subtle)' }} /> Completed
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--bg-subtle)' }} /> In Progress
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--bg-subtle)' }} /> Pending
          </span>
        </div>
      </div>

      {/* Visual Mind Map Flow */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, overflowX: 'auto', paddingBottom: 10 }}>
        {/* Central Venture Root */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-main)',
              borderRadius: 8,
              padding: '14px 22px',
              boxShadow: '0 1px 3px rgb(69 60 55 / 0.1)',
              minWidth: 220,
              cursor: 'pointer'
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase', opacity: 0.85 }}>
              Venture Root ({stage})
            </div>
            <div style={{ fontSize: 16, fontWeight: 800, marginTop: 2 }}>{projectName}</div>
            <div style={{ fontSize: 11, opacity: 0.85, marginTop: 4 }}>
              {phases.length} Phases • {tasks.length} Actionable Tasks
            </div>
          </div>
        </div>

        {/* Phase Branches & Associated Task Nodes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, paddingLeft: 24, borderLeft: '2px dashed var(--border-color)' }}>
          {phases.map((phase, pIdx) => {
            const phaseTasks = groupedTasks[phase.name] || [];
            const completedCount = phaseTasks.filter(t => t.status === 'Finished').length;
            const phaseColor = phase.color || 'var(--text-muted)';

            return (
              <div key={pIdx} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {/* Phase Node */}
                <div
                  tabIndex={0}
                  role="button"
                  aria-label={`Inspect phase: ${phase.name}`}
                  onClick={() => { setSelectedPhase(phase); setSelectedTask(null); }}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedPhase(phase); } }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: 'var(--bg-subtle)',
                    border: `1.5px solid ${phaseColor}`,
                    borderRadius: 8,
                    padding: '10px 16px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: '0 1px 3px rgb(69 60 55 / 0.04)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: phaseColor }} />
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>{phase.name}</span>
                    <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                      ({phase.start_date || 'Start'} ➔ {phase.end_date || 'Target'})
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, background: 'var(--bg-subtle)', color: 'var(--primary-text)', padding: '2px 8px', borderRadius: 12, fontWeight: 600 }}>
                      {completedCount}/{phaseTasks.length} Done
                    </span>
                    <span style={{ fontSize: 11, color: phaseColor, fontWeight: 600 }}>Inspect ➔</span>
                  </div>
                </div>

                {/* Sub-tasks Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, paddingLeft: 18 }}>
                  {phaseTasks.map((task, tIdx) => {
                    const stColor = getStatusColor(task.status);
                    const prColor = getPriorityBadge(task.priority);
                    const isSelected = selectedTask?.task_code === task.task_code;

                    return (
                      <div
                        key={tIdx}
                        tabIndex={0}
                        role="button"
                        aria-label={`Inspect task: ${task.title}`}
                        onClick={() => { setSelectedTask(task); setSelectedPhase(null); }}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedTask(task); } }}
                        style={{
                          background: 'var(--bg-card)',
                          border: `1.5px solid ${isSelected ? 'var(--primary-text)' : stColor.border}`,
                          borderRadius: 8,
                          padding: 12,
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                          boxShadow: isSelected ? '0 4px 12px rgb(69 60 55 / 0.15)' : '0 1px 3px rgb(69 60 55 / 0.03)',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {/* Top: Code + Priority + Status */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--primary-text)' }}>{task.task_code}</span>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <span style={{ fontSize: 10, background: prColor.bg, color: prColor.text, padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>
                              {task.priority || 'Medium'}
                            </span>
                            <span style={{ fontSize: 10, background: stColor.bg, color: stColor.text, padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>
                              {task.status || 'Pending'}
                            </span>
                          </div>
                        </div>

                        {/* Task Title */}
                        <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.4 }}>
                          {task.title}
                        </div>

                        {/* Assignee & Department */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <User size={13} color={task.is_overloaded ? 'var(--danger-text)' : 'var(--primary-text)'} />
                            <span style={{ fontWeight: 600, color: task.is_overloaded ? 'var(--danger-text)' : 'var(--text-main)' }}>
                              {task.assigned_to || 'Unassigned'}
                            </span>
                            {task.assigned_role && (
                              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>({task.assigned_role})</span>
                            )}
                          </div>
                          {task.is_overloaded && (
                            <span title="Contributor is overloaded with simultaneous critical deliverables" style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--danger-text)', fontSize: 10, fontWeight: 700 }}>
                              <AlertTriangle size={12} /> Overloaded
                            </span>
                          )}
                        </div>

                        {/* Dates & Dependencies */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--bg-subtle)', paddingTop: 6, fontSize: 10.5, color: 'var(--text-muted)' }}>
                          <span>{task.start_date} ➔ {task.end_date}</span>
                          {task.dependencies && task.dependencies.length > 0 && (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: 'var(--primary-text)', fontWeight: 600 }}>
                              <GitPullRequest size={11} /> {task.dependencies.join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Task Inspection Drawer (ROAD-004) */}
      {selectedTask && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            bottom: 0,
            width: 'min(480px, 95%)',
            background: 'var(--bg-card)',
            boxShadow: '-8px 0 24px rgb(69 60 55 / 0.15)',
            borderTopRightRadius: 12,
            borderBottomRightRadius: 12,
            borderLeft: '1px solid var(--border-color)',
            zIndex: 40,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto'
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="task-detail-title"
        >
          {/* Drawer Header */}
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--bg-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: 'var(--bg-subtle)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary-text)', background: 'var(--bg-subtle)', padding: '2px 8px', borderRadius: 4 }}>
                  {selectedTask.task_code}
                </span>
                <span className={`badge-priority ${(selectedTask.priority || 'medium').toLowerCase()}`}>
                  {selectedTask.priority}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--primary-text)', background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: 4 }}>
                  {selectedTask.status}
                </span>
              </div>
              <h4 id="task-detail-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-main)' }}>
                {selectedTask.title}
              </h4>
            </div>
            <button
              onClick={() => setSelectedTask(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, borderRadius: 4 }}
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>

          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Phase & Timeline */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, background: 'var(--bg-subtle)', padding: 12, borderRadius: 8 }}>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>Phase</span>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-main)' }}>{selectedTask.phase}</span>
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>Dates</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-main)' }}>{selectedTask.start_date} to {selectedTask.end_date}</span>
              </div>
            </div>

            {/* Description */}
            <div>
              <h5 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 6px 0' }}>
                Work Description
              </h5>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--text-main)' }}>
                {selectedTask.description || "Core deliverable scheduled under active sprint phase."}
              </p>
            </div>

            {/* Steps Breakdown (ROAD-003) */}
            {selectedTask.steps && selectedTask.steps.length > 0 && (
              <div>
                <h5 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 8px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ListChecks size={14} color="var(--primary-text)" /> Execution Steps ({selectedTask.steps.length})
                </h5>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {selectedTask.steps.map((step, sIdx) => (
                    <div key={sIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12.5, color: 'var(--text-main)', background: 'var(--bg-subtle)', padding: '8px 10px', borderRadius: 6 }}>
                      <span style={{ fontWeight: 700, color: 'var(--primary-text)' }}>{sIdx + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Assignments & Capacity (ROAD-015 to ROAD-019) */}
            <div style={{ background: selectedTask.is_overloaded ? 'var(--bg-subtle)' : 'var(--bg-subtle)', border: `1px solid ${selectedTask.is_overloaded ? 'var(--bg-subtle)' : 'var(--border-color)'}`, borderRadius: 8, padding: 12 }}>
              <h5 style={{ fontSize: 12.5, fontWeight: 700, color: selectedTask.is_overloaded ? 'var(--danger-text)' : 'var(--primary-text)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <User size={15} color={selectedTask.is_overloaded ? 'var(--danger-text)' : 'var(--primary-text)'} />
                Assignment & Team Capacity
              </h5>
              <div style={{ fontSize: 12.5, color: selectedTask.is_overloaded ? 'var(--danger-text)' : 'var(--primary-text)', lineHeight: 1.5 }}>
                <b>Assigned to:</b> {selectedTask.assigned_to || 'Unassigned'}
                {selectedTask.assigned_role && <> • <b>Role:</b> {selectedTask.assigned_role}</>}
                {selectedTask.department && <> • <b>Dept:</b> {selectedTask.department}</>}
                {selectedTask.effort && <> • <b>Effort:</b> {selectedTask.effort}</>}
              </div>
              {selectedTask.is_overloaded && (
                <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--danger-text)', fontWeight: 600 }}>
                  ⚠️ Contributor capacity alert: Member has multiple critical tasks concurrently. Consider reassigning or extending timeline.
                </div>
              )}
            </div>

            {/* Deliverables */}
            {selectedTask.deliverables && (
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
                <h5 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CheckCircle2 size={14} color="var(--primary-text)" /> Deliverable Outcome
                </h5>
                <p style={{ margin: 0, fontSize: 12.5, color: 'var(--text-main)', lineHeight: 1.5 }}>
                  {selectedTask.deliverables}
                </p>
              </div>
            )}

            {/* Dependencies */}
            {selectedTask.dependencies && selectedTask.dependencies.length > 0 && (
              <div>
                <h5 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <GitPullRequest size={14} color="var(--primary-text)" /> Prerequisites & Dependencies
                </h5>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {selectedTask.dependencies.map((dep, dIdx) => (
                    <span key={dIdx} style={{ background: 'var(--bg-subtle)', color: 'var(--text-main)', fontSize: 11, padding: '4px 8px', borderRadius: 4, fontWeight: 600 }}>
                      Requires {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Phase Inspection Drawer */}
      {selectedPhase && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            bottom: 0,
            width: 'min(440px, 95%)',
            background: 'var(--bg-card)',
            boxShadow: '-8px 0 24px rgb(69 60 55 / 0.15)',
            borderTopRightRadius: 12,
            borderBottomRightRadius: 12,
            borderLeft: '1px solid var(--border-color)',
            zIndex: 40,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto'
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="phase-detail-title"
        >
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--bg-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: 'var(--bg-subtle)' }}>
            <div>
              <span style={{ fontSize: 11, color: selectedPhase.color || 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Delivery Milestone Phase
              </span>
              <h4 id="phase-detail-title" style={{ margin: '4px 0 0 0', fontSize: 16, fontWeight: 700, color: 'var(--text-main)' }}>
                {selectedPhase.name}
              </h4>
            </div>
            <button
              onClick={() => setSelectedPhase(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>

          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <h5 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', margin: '0 0 6px 0' }}>
                Phase Objective
              </h5>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--text-main)' }}>
                {selectedPhase.description || "Core operational and delivery phase."}
              </p>
            </div>

            <div style={{ background: 'var(--bg-subtle)', padding: 12, borderRadius: 8, fontSize: 12.5, color: 'var(--text-main)' }}>
              <div><b>Schedule:</b> {selectedPhase.start_date || 'Start'} to {selectedPhase.end_date || 'End'}</div>
              <div style={{ marginTop: 4 }}><b>Tasks:</b> {(groupedTasks[selectedPhase.name] || []).length} scheduled deliverables</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
