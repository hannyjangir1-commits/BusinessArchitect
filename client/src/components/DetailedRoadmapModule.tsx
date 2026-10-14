import React from 'react';
import { Project, RoadmapTask, ModuleDetail } from '../types';
import { VersionToolbar } from './VersionToolbar';
import { ListTodo, CheckCircle2, Clock, AlertCircle } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail?: ModuleDetail | null;
  tasks: RoadmapTask[];
  onUpdateStatus: (taskId: string, status: string) => Promise<void>;
  onRenameVersion?: (newName: string) => Promise<void>;
  onDeleteVersion?: (versionId: string) => Promise<void>;
  onRestoreVersion?: (versionId: string) => Promise<void>;
  onExportPdf?: () => void;
  isLoading: boolean;
}

export const DetailedRoadmapModule: React.FC<Props> = ({
  project,
  moduleDetail,
  tasks,
  onUpdateStatus,
  onRenameVersion,
  onDeleteVersion,
  onRestoreVersion,
  onExportPdf,
  isLoading
}) => {
  // Dynamically group tasks by Month periods based on start dates
  const groups: Record<string, RoadmapTask[]> = {};

  tasks.forEach((t) => {
    // Determine month group or fallback to timeline
    const date = t.start_date ? new Date(t.start_date) : null;
    let periodKey = 'Month 1';
    if (date && !isNaN(date.getTime())) {
      const monthName = date.toLocaleString('default', { month: 'short', year: 'numeric' });
      periodKey = monthName;
    } else if (t.timeline) {
      periodKey = t.timeline;
    }

    if (!groups[periodKey]) groups[periodKey] = [];
    groups[periodKey].push(t);
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <ListTodo size={22} />
          </div>
          <div className="module-titles">
            <h2>Detailed Operational Roadmap</h2>
            <p>Chronological delivery breakdown grouped by execution intervals</p>
          </div>
        </div>

        {onRenameVersion && onDeleteVersion && onRestoreVersion && onExportPdf && (
          <VersionToolbar
            moduleType="detailed_roadmap"
            moduleTitle="Detailed Roadmap"
            activeVersionName={moduleDetail?.active_version_name}
            activeVersionNumber={moduleDetail?.active_version_number}
            versions={moduleDetail?.versions || []}
            onRename={onRenameVersion}
            onDelete={onDeleteVersion}
            onRestore={onRestoreVersion}
            onExportPdf={onExportPdf}
          />
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {Object.keys(groups).length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
            No roadmap tasks available. Please generate or add tasks in Execution Roadmap.
          </div>
        ) : (
          Object.entries(groups).map(([period, periodTasks]) => (
            <div key={period} className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, borderBottom: '1px solid #f1f5f9', paddingBottom: 10 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Clock size={16} color="#6366f1" />
                  <span>{period}</span>
                </h3>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>
                  {periodTasks.length} {periodTasks.length === 1 ? 'task' : 'tasks'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
                {periodTasks.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: 10,
                      padding: 14,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 11.5, fontWeight: 700, color: '#6366f1' }}>{t.task_code}</span>
                      <span className={`badge-priority ${t.priority.toLowerCase()}`}>{t.priority}</span>
                    </div>

                    <h4 style={{ fontSize: 13.5, fontWeight: 700, color: '#0f172a' }}>{t.title}</h4>

                    {t.description && (
                      <p style={{ fontSize: 12, color: '#64748b', lineHeight: 1.4 }}>{t.description}</p>
                    )}

                    <div style={{ fontSize: 11.5, color: '#475569', marginTop: 4 }}>
                      <b>Timeline:</b> {t.start_date} to {t.end_date}
                    </div>

                    {t.deliverables && (
                      <div style={{ fontSize: 11.5, color: '#059669', background: '#ecfdf5', padding: '4px 8px', borderRadius: 6 }}>
                        <b>Deliverable:</b> {t.deliverables}
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: 8, borderTop: '1px solid #e2e8f0' }}>
                      <span style={{ fontSize: 11, color: '#94a3b8' }}>Phase: {t.phase}</span>
                      <select
                        className="status-select"
                        value={t.status === 'In Progress' ? 'Ongoing' : t.status}
                        onChange={(e) => onUpdateStatus(t.id, e.target.value)}
                        disabled={isLoading}
                      >
                        <option value="Pending">Pending</option>
                        <option value="Ongoing">Ongoing</option>
                        <option value="Finished">Finished</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
