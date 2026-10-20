import React, { useState } from 'react';
import { Project, ModuleDetail, RoadmapTask, RoadmapSummary, RoadmapPlanningInputs } from '../types';
import { RoadmapMindMap } from './RoadmapMindMap';
import { GanttChart } from './GanttChart';
import { MilestoneCards } from './MilestoneCards';
import { AllTasksTable } from './AllTasksTable';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import { DependenciesPanel } from './DependenciesPanel';
import {
  Calendar, GitPullRequest, Milestone, ListTodo, SlidersHorizontal,
  Workflow, RefreshCw, X, ShieldAlert, Sparkles
} from 'lucide-react';
import { RoadmapPlanningForm } from './RoadmapPlanningForm';

const TODAY_DATE = new Date().toISOString().slice(0, 10);

interface Props {
  project: Project;
  moduleDetail: ModuleDetail | null;
  tasks: RoadmapTask[];
  summary: RoadmapSummary;
  onGenerate: (inputs: RoadmapPlanningInputs) => Promise<void>;
  onModify: (instruction: string) => Promise<void>;
  onAddTask: (taskData: any) => Promise<void>;
  onUpdateTask: (taskId: string, taskData: any) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  onRenameVersion: (newName: string) => Promise<void>;
  onDeleteVersion: (versionId: string) => Promise<void>;
  onRestoreVersion: (versionId: string) => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
  isGenerating?: boolean;
  generationProgress?: { stageText: string; progressPercent: number } | null;
  isGenerateDisabled?: boolean;
}

export const ExecutionRoadmapModule: React.FC<Props> = ({
  project,
  moduleDetail,
  tasks,
  summary,
  onGenerate,
  onModify,
  onAddTask,
  onUpdateTask,
  onDeleteTask,
  onRenameVersion,
  onDeleteVersion,
  onRestoreVersion,
  onDeleteModule,
  onExportPdf,
  isLoading,
  isGenerating = false,
  generationProgress = null,
  isGenerateDisabled = false
}) => {
  // Mind Map is the primary generated view (ROAD-002)
  const [activeSubTab, setActiveSubTab] = useState<'mindmap' | 'tasks' | 'gantt' | 'milestones' | 'dependencies'>('mindmap');
  const [planningOpenForVersion, setPlanningOpenForVersion] = useState<string | null | false>(false);
  const [staleDismissed, setStaleDismissed] = useState<boolean>(false);
  const [showAssistant, setShowAssistant] = useState<boolean>(false);

  const isPlanningOpen = !moduleDetail?.active_version_id || planningOpenForVersion === moduleDetail.active_version_id;
  const feasibility = moduleDetail?.data?.feasibility_evaluation;
  const isStale = !!moduleDetail?.is_stale && !staleDismissed;
  const hasExpiredTimeline = tasks.length > 0 && tasks.every((task) => task.end_date && task.end_date < TODAY_DATE);

  const planningForm = (
    <RoadmapPlanningForm
      key={moduleDetail?.active_version_id || 'new-roadmap'}
      stage={project.stage}
      initialValues={moduleDetail?.data?.planning_inputs}
      isGenerating={isGenerating}
      isDisabled={isGenerateDisabled}
      progress={generationProgress}
      onSubmit={onGenerate}
      onCancel={moduleDetail?.active_version_id ? () => setPlanningOpenForVersion(false) : undefined}
    />
  );
  const openPlanning = async () => { setPlanningOpenForVersion(moduleDetail?.active_version_id || null); };

  // Handle scope reduction quick-accept (ROAD-013)
  const handleReduceScope = async () => {
    const prevInputs = moduleDetail?.data?.planning_inputs || {
      start_date: new Date().toISOString().slice(0, 10),
      horizon_weeks: 12,
      checklist: []
    };
    await onGenerate({
      ...prevInputs,
      reduce_mvp_scope: true,
      constraints: (prevInputs.constraints ? prevInputs.constraints + ' | ' : '') + 'Scope reduced to core MVP'
    });
  };

  // Handle accept update from stale tech stack (SYNC-006)
  const handleAcceptStaleUpdate = async () => {
    const prevInputs = moduleDetail?.data?.planning_inputs || {
      start_date: new Date().toISOString().slice(0, 10),
      horizon_weeks: 12,
      checklist: []
    };
    await onGenerate(prevInputs);
    setStaleDismissed(true);
  };

  if (tasks.length === 0 && !moduleDetail?.data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>Build a roadmap for {project.name}</h2>
          <p style={{ marginTop: 4, fontSize: 13, color: 'var(--text-muted)' }}>
            Answer a few stage-specific questions and specify capacity so the plan reflects your real team and current progress.
          </p>
        </div>
        {planningForm}
      </div>
    );
  }

  const phases = moduleDetail?.data?.phases || [
    { name: 'Phase 1: Foundation & Architecture', color: 'var(--text-muted)' },
    { name: 'Phase 2: Core Implementation', color: 'var(--primary-text)' },
    { name: 'Phase 3: Launch & Feedback', color: 'var(--primary-text)' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Module View Header */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <Calendar size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Roadmap & Execution Plan
              <span className="version-pill-dropdown">
                {moduleDetail?.active_version_name || `V${moduleDetail?.active_version_number || 1}`}
              </span>
            </h2>
            <p>Unified delivery plan: Interactive mind map, task assignments, and timeline</p>
          </div>
        </div>

        <button className="btn-secondary" onClick={() => isPlanningOpen ? setPlanningOpenForVersion(false) : setPlanningOpenForVersion(moduleDetail?.active_version_id || null)} disabled={isGenerating}>
          <SlidersHorizontal size={14} /> {isPlanningOpen ? 'Close planning parameters' : 'Replan roadmap'}
        </button>

        <VersionToolbar
          moduleType="execution_roadmap"
          moduleTitle="Roadmap & Execution Plan"
          activeVersionName={moduleDetail?.active_version_name}
          activeVersionNumber={moduleDetail?.active_version_number}
          versions={moduleDetail?.versions || []}
          onRename={onRenameVersion}
          onDelete={onDeleteVersion}
          onRestore={onRestoreVersion}
          onExportPdf={onExportPdf}
          onCreateNew={openPlanning}
          onDeleteModule={onDeleteModule}
          createLabel="Create New Roadmap"
          isBusy={isLoading || isGenerating}
          isCreateDisabled={isGenerateDisabled}
        />
      </div>

      {hasExpiredTimeline && (
        <div
          role="status"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            padding: '12px 16px',
            border: '1px solid var(--border-color)',
            borderRadius: 10,
            background: 'var(--bg-subtle)',
            color: 'var(--text-main)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Calendar size={18} color="var(--primary-text)" aria-hidden="true" />
            <span style={{ fontSize: 13 }}>
              This roadmap has ended dates. Replan it to anchor the timeline to today ({TODAY_DATE}) and keep the Gantt chart current.
            </span>
          </div>
          <button className="btn-secondary" onClick={openPlanning} disabled={isGenerating}>
            <RefreshCw size={14} /> Replan from today
          </button>
        </div>
      )}

      {/* Freshness / Staleness Notification Banner (SYNC-004 to SYNC-006) */}
      {isStale && (
        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Sparkles size={18} color="var(--primary-text)" />
            <div style={{ fontSize: 13, color: 'var(--primary-text)' }}>
              <b>New Architecture Available:</b> {moduleDetail?.stale_reason || "Tech Stack was recently updated. Would you like to refresh your roadmap?"}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleAcceptStaleUpdate}
              className="btn-primary"
              style={{ fontSize: 12, padding: '5px 12px', background: 'var(--bg-subtle)', borderColor: 'var(--primary-text)' }}
              disabled={isGenerating}
            >
              <RefreshCw size={12} className={isGenerating ? "animate-spin" : ""} /> Update Roadmap
            </button>
            <button
              onClick={() => setStaleDismissed(true)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
              title="Dismiss notification"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Feasibility Alert Banner for Solo Dev / Unrealistic Deadlines (ROAD-012, ROAD-013) */}
      {feasibility && !feasibility.is_realistic && (
        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', borderRadius: 8, padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ShieldAlert size={20} color="var(--danger-text)" />
            <div>
              <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: 'var(--danger-text)' }}>
                Unrealistic Scope & Timeline Warning
              </h4>
              <p style={{ margin: '2px 0 0 0', fontSize: 12.5, color: 'var(--danger-text)' }}>
                {feasibility.feasibility_issues?.[0] || "Solo developer requested full enterprise scope within 12 weeks. High risk of schedule overrun and burnout."}
              </p>
            </div>
          </div>

          <div style={{ background: 'var(--bg-card)', borderRadius: 6, padding: '10px 14px', border: '1px solid var(--bg-subtle)' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--danger-text)', display: 'block', marginBottom: 6 }}>
              Recommended Realistic Alternatives:
            </span>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--danger-text)', lineHeight: 1.5 }}>
              {feasibility.recommended_alternatives?.map((alt: string, aIdx: number) => (
                <li key={aIdx} style={{ marginBottom: 4 }}>{alt}</li>
              ))}
            </ul>
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 2 }}>
            <button
              onClick={handleReduceScope}
              className="btn-primary"
              style={{ fontSize: 12, padding: '6px 14px', background: 'var(--danger-text)', borderColor: 'var(--danger-text)' }}
              disabled={isGenerating}
            >
              Reduce to Core MVP Scope ➔
            </button>
            <button
              onClick={openPlanning}
              className="btn-secondary"
              style={{ fontSize: 12, padding: '6px 14px' }}
              disabled={isGenerating}
            >
              Extend Timeline / Add Capacity
            </button>
          </div>
        </div>
      )}

      {isPlanningOpen && planningForm}

      {/* Primary Subtabs Navigation (ROAD-002, ROAD-003) */}
      <div className="subtabs-bar">
        <button
          className={`subtab-pill ${activeSubTab === 'mindmap' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('mindmap')}
          aria-label="Mind Map Primary View"
        >
          <Workflow size={14} /> Mind Map (Primary)
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'tasks' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('tasks')}
          aria-label="Detailed Execution Breakdown"
        >
          <ListTodo size={14} /> Detailed Breakdown ({tasks.length})
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'gantt' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('gantt')}
          aria-label="Gantt Timeline View"
        >
          <Calendar size={14} /> Gantt Timeline
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'milestones' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('milestones')}
          aria-label="Milestone Cards"
        >
          <Milestone size={14} /> Milestones
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'dependencies' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('dependencies')}
          aria-label="Dependencies View"
        >
          <GitPullRequest size={14} /> Dependencies
        </button>

        <div style={{ marginLeft: 'auto' }}>
          <button
            className={`subtab-pill ${showAssistant ? 'active' : ''}`}
            onClick={() => setShowAssistant(!showAssistant)}
            aria-label="Toggle Plan Assistant"
            style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}
          >
            <Sparkles size={14} /> {showAssistant ? 'Hide Plan Assistant' : 'Plan Assistant'}
          </button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="workspace-grid">
        <div className="workspace-main-column">
          {/* Primary View: Interactive Mind Map (ROAD-002) */}
          {activeSubTab === 'mindmap' && (
            <RoadmapMindMap
              projectName={project.name}
              stage={project.stage}
              phases={phases}
              tasks={tasks}
            />
          )}

          {/* Detailed Execution Breakdown (ROAD-003) */}
          {activeSubTab === 'tasks' && (
            <AllTasksTable
              tasks={tasks}
              onAddTask={onAddTask}
              onUpdateTask={onUpdateTask}
              onDeleteTask={onDeleteTask}
              onRegenerate={openPlanning}
              isLoading={isLoading}
              isGenerating={isGenerating}
              isGenerateDisabled={isGenerateDisabled}
              generationProgress={generationProgress}
            />
          )}

          {/* Gantt Timeline */}
          {activeSubTab === 'gantt' && (
            <>
              <GanttChart tasks={tasks} />
              <MilestoneCards summary={summary} />
            </>
          )}

          {/* Milestones */}
          {activeSubTab === 'milestones' && (
            <>
              <MilestoneCards summary={summary} />
              <div className="card" style={{ padding: 20 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Milestone size={18} color="var(--primary-text)" /> Key Milestone Deliverables
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                  {tasks.filter(t => t.deliverables).map((t, idx) => (
                    <div key={t.id || idx} style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--primary-text)' }}>{t.task_code}</span>
                        <span className={`badge-priority ${(t.priority || 'medium').toLowerCase()}`}>{t.priority}</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>{t.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--primary-text)', background: 'var(--bg-subtle)', padding: '6px 10px', borderRadius: 6 }}>
                        <b>Deliverable:</b> {t.deliverables}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 8 }}>
                        Target: {t.end_date} • Phase: {t.phase} {t.assigned_to ? `• Assigned: ${t.assigned_to}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Dependencies Panel */}
          {activeSubTab === 'dependencies' && (
            <DependenciesPanel tasks={tasks} />
          )}
        </div>

        {/* Blueprint Copilot Contextual Assistant: rendered only when requested */}
        {showAssistant && (
          <ContextualAssistant
            moduleTitle="Roadmap & Execution Plan"
            moduleType="execution_roadmap"
            onModify={onModify}
            onClose={() => setShowAssistant(false)}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  );
};
