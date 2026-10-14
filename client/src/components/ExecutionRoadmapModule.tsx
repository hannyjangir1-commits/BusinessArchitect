import React, { useState } from 'react';
import { Project, ModuleDetail, RoadmapTask, RoadmapSummary } from '../types';
import { GanttChart } from './GanttChart';
import { MilestoneCards } from './MilestoneCards';
import { AllTasksTable } from './AllTasksTable';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import { DependenciesPanel } from './DependenciesPanel';
import { Calendar, GitPullRequest, Milestone, ListTodo, Sparkles, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail | null;
  tasks: RoadmapTask[];
  summary: RoadmapSummary;
  onGenerate: () => Promise<void>;
  onModify: (instruction: string) => Promise<void>;
  onAddTask: (taskData: any) => Promise<void>;
  onUpdateTask: (taskId: string, taskData: any) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  onRenameVersion: (newName: string) => Promise<void>;
  onDeleteVersion: (versionId: string) => Promise<void>;
  onRestoreVersion: (versionId: string) => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
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
  onExportPdf,
  isLoading
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'gantt' | 'tasks' | 'milestones' | 'dependencies'>('gantt');

  if (tasks.length === 0 && !moduleDetail?.data) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <Calendar size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
          Execution Roadmap Not Yet Generated
        </h3>
        <p style={{ fontSize: 13, color: '#64748b', maxWidth: 480, margin: '0 auto 20px auto' }}>
          Generate a realistic execution roadmap with 5 delivery phases, tasks, dependencies, and milestone tracking for {project.name}.
        </p>
        <button onClick={onGenerate} className="btn-primary" disabled={isLoading} style={{ margin: '0 auto' }}>
          {isLoading ? <><Loader2 size={16} className="animate-spin" /> Synthesizing Timeline...</> : <><Sparkles size={16} /> Generate Execution Roadmap</>}
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Module View Header matching screenshot */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <Calendar size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Execution Roadmap
              <span className="version-pill-dropdown">
                {moduleDetail?.active_version_name || `V${moduleDetail?.active_version_number || 2}`}
              </span>
            </h2>
            <p>Project execution plan with timeline, milestones and tasks</p>
          </div>
        </div>

        <VersionToolbar
          moduleType="execution_roadmap"
          moduleTitle="Execution Roadmap"
          activeVersionName={moduleDetail?.active_version_name}
          activeVersionNumber={moduleDetail?.active_version_number}
          versions={moduleDetail?.versions || []}
          onRename={onRenameVersion}
          onDelete={onDeleteVersion}
          onRestore={onRestoreVersion}
          onExportPdf={onExportPdf}
        />
      </div>

      {/* Subtabs bar matching screenshot */}
      <div className="subtabs-bar">
        <button
          className={`subtab-pill ${activeSubTab === 'gantt' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('gantt')}
        >
          <Calendar size={14} /> Gantt Chart
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'tasks' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('tasks')}
        >
          <ListTodo size={14} /> Task List
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'milestones' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('milestones')}
        >
          <Milestone size={14} /> Milestones
        </button>
        <button
          className={`subtab-pill ${activeSubTab === 'dependencies' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('dependencies')}
        >
          <GitPullRequest size={14} /> Dependencies
        </button>
      </div>

      {/* Main Grid: Left Column + Right AI Assistant */}
      <div className="workspace-grid">
        <div className="workspace-main-column">
          {activeSubTab === 'gantt' && (
            <>
              {/* Gantt Chart Component */}
              <GanttChart tasks={tasks} />

              {/* 30-Day, 60-Day, 90-Day Milestone Cards */}
              <MilestoneCards summary={summary} />

              {/* All Tasks Table */}
              <AllTasksTable
                tasks={tasks}
                onAddTask={onAddTask}
                onUpdateTask={onUpdateTask}
                onDeleteTask={onDeleteTask}
                onRegenerate={onGenerate}
                isLoading={isLoading}
              />
            </>
          )}

          {activeSubTab === 'tasks' && (
            <AllTasksTable
              tasks={tasks}
              onAddTask={onAddTask}
              onUpdateTask={onUpdateTask}
              onDeleteTask={onDeleteTask}
              onRegenerate={onGenerate}
              isLoading={isLoading}
            />
          )}

          {activeSubTab === 'milestones' && (
            <>
              <MilestoneCards summary={summary} />
              <div className="card" style={{ padding: 20 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Milestone size={18} color="#6366f1" /> Key Milestone Deliverables
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
                  {tasks.filter(t => t.deliverables).map(t => (
                    <div key={t.id} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: '#6366f1' }}>{t.task_code}</span>
                        <span className={`badge-priority ${t.priority.toLowerCase()}`}>{t.priority}</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>{t.title}</div>
                      <div style={{ fontSize: 12, color: '#059669', background: '#ecfdf5', padding: '6px 10px', borderRadius: 6 }}>
                        <b>Deliverable:</b> {t.deliverables}
                      </div>
                      <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 8 }}>
                        Target: {t.end_date} • Phase: {t.phase}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {activeSubTab === 'dependencies' && (
            <DependenciesPanel tasks={tasks} />
          )}
        </div>

        {/* Contextual AI Assistant Panel on the right matching screenshot */}
        <ContextualAssistant
          moduleTitle="Execution Roadmap"
          moduleType="execution_roadmap"
          onModify={onModify}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
};
