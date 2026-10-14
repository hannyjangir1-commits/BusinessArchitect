import React, { useState } from 'react';
import { RoadmapTask } from '../types';
import { Search, Plus, RotateCw, Edit3, Trash2, Copy, AlertCircle } from 'lucide-react';

interface Props {
  tasks: RoadmapTask[];
  onAddTask: (taskData: any) => Promise<void>;
  onUpdateTask: (taskId: string, taskData: any) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  onRegenerate: () => Promise<void>;
  isLoading: boolean;
}

export const AllTasksTable: React.FC<Props> = ({
  tasks,
  onAddTask,
  onUpdateTask,
  onDeleteTask,
  onRegenerate,
  isLoading
}) => {
  const [filterTimeline, setFilterTimeline] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingTask, setEditingTask] = useState<RoadmapTask | null>(null);
  const [formData, setFormData] = useState({
    task_code: '',
    title: '',
    description: '',
    phase: 'Planning & Research',
    timeline: '30-day',
    start_date: '2026-10-01',
    end_date: '2026-10-15',
    priority: 'Medium',
    status: 'Pending',
    dependencies: '',
    deliverables: '',
    effort: '1 week'
  });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter tasks
  const filteredTasks = tasks.filter(t => {
    if (filterTimeline !== 'all' && !t.timeline.toLowerCase().includes(filterTimeline.toLowerCase())) {
      return false;
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        t.title.toLowerCase().includes(q) ||
        t.task_code.toLowerCase().includes(q) ||
        (t.description && t.description.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const count30 = tasks.filter(t => t.timeline.includes('30')).length;
  const count60 = tasks.filter(t => t.timeline.includes('60')).length;
  const count90 = tasks.filter(t => t.timeline.includes('90')).length;

  const handleOpenAdd = () => {
    setEditingTask(null);
    setFormData({
      task_code: `TSK-${String(tasks.length + 1).padStart(2, '0')}`,
      title: '',
      description: '',
      phase: 'Planning & Research',
      timeline: '30-day',
      start_date: '2026-10-01',
      end_date: '2026-10-15',
      priority: 'Medium',
      status: 'Pending',
      dependencies: '',
      deliverables: '',
      effort: '1 week'
    });
    setErrorMessage(null);
    setModalOpen(true);
  };

  const handleOpenEdit = (task: RoadmapTask) => {
    setEditingTask(task);
    setFormData({
      task_code: task.task_code,
      title: task.title,
      description: task.description || '',
      phase: task.phase,
      timeline: task.timeline,
      start_date: task.start_date,
      end_date: task.end_date,
      priority: task.priority,
      status: task.status,
      dependencies: task.dependencies ? task.dependencies.join(', ') : '',
      deliverables: task.deliverables || '',
      effort: task.effort || ''
    });
    setErrorMessage(null);
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    try {
      const depsArray = formData.dependencies
        .split(',')
        .map(d => d.trim())
        .filter(Boolean);

      const payload = {
        ...formData,
        dependencies: depsArray
      };

      if (editingTask) {
        await onUpdateTask(editingTask.id, payload);
      } else {
        await onAddTask(payload);
      }
      setModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save task');
    }
  };

  const handleStatusChange = async (taskId: string, newStatus: string) => {
    try {
      await onUpdateTask(taskId, { status: newStatus });
    } catch (err: any) {
      alert(err.message || 'Failed to update status');
    }
  };

  const handleDelete = async (taskId: string, taskCode: string) => {
    if (!window.confirm(`Are you sure you want to delete task ${taskCode}?`)) return;
    try {
      await onDeleteTask(taskId);
    } catch (err: any) {
      alert(err.message || 'Cannot delete task. Other tasks may depend on it.');
    }
  };

  return (
    <div className="card" style={{ padding: 20 }}>
      {/* Header bar */}
      <div className="tasks-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
            All Tasks ({tasks.length})
          </h3>
          <div className="task-filter-group">
            <button
              className={`filter-chip ${filterTimeline === 'all' ? 'active' : ''}`}
              onClick={() => setFilterTimeline('all')}
            >
              All ({tasks.length})
            </button>
            <button
              className={`filter-chip ${filterTimeline === '30' ? 'active' : ''}`}
              onClick={() => setFilterTimeline('30')}
            >
              30-Day ({count30})
            </button>
            <button
              className={`filter-chip ${filterTimeline === '60' ? 'active' : ''}`}
              onClick={() => setFilterTimeline('60')}
            >
              60-Day ({count60})
            </button>
            <button
              className={`filter-chip ${filterTimeline === '90' ? 'active' : ''}`}
              onClick={() => setFilterTimeline('90')}
            >
              90-Day ({count90})
            </button>
          </div>
        </div>

        <div className="tasks-action-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '6px 10px' }}>
            <Search size={14} color="#94a3b8" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 12.5 }}
            />
          </div>

          <button onClick={handleOpenAdd} className="btn-primary" disabled={isLoading}>
            <Plus size={15} /> Add Task
          </button>
          <button onClick={onRegenerate} className="btn-secondary" disabled={isLoading} title="Regenerate roadmap with AI">
            <RotateCw size={14} /> Regenerate
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="table-responsive">
        <table className="enterprise-table">
          <thead>
            <tr>
              <th style={{ width: 36 }}><input type="checkbox" /></th>
              <th style={{ width: 85 }}>ID</th>
              <th style={{ width: 90 }}>Priority</th>
              <th style={{ width: 90 }}>Timeline</th>
              <th style={{ minWidth: 200 }}>Task Title</th>
              <th style={{ minWidth: 240 }}>Description</th>
              <th style={{ width: 110 }}>Dependencies</th>
              <th style={{ width: 130 }}>Status</th>
              <th style={{ width: 95, textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '30px 0', color: '#94a3b8' }}>
                  No tasks found matching your filter criteria.
                </td>
              </tr>
            ) : (
              filteredTasks.map((t) => (
                <tr key={t.id}>
                  <td><input type="checkbox" /></td>
                  <td style={{ fontWeight: 700, color: '#475569', fontSize: 12 }}>{t.task_code}</td>
                  <td>
                    <span className={`badge-priority ${t.priority.toLowerCase()}`}>
                      {t.priority}
                    </span>
                  </td>
                  <td>
                    <span className="badge-timeline">{t.timeline}</span>
                  </td>
                  <td style={{ fontWeight: 600, color: '#0f172a' }}>{t.title}</td>
                  <td style={{ color: '#64748b', fontSize: 12 }}>
                    {t.description || '—'}
                  </td>
                  <td style={{ color: '#6366f1', fontWeight: 600, fontSize: 12 }}>
                    {t.dependencies && t.dependencies.length > 0 ? t.dependencies.join(', ') : '—'}
                  </td>
                  <td>
                    <select
                      className="status-select"
                      value={t.status}
                      onChange={(e) => handleStatusChange(t.id, e.target.value)}
                    >
                      <option value="Pending">Pending</option>
                      <option value="Ongoing">Ongoing</option>
                      <option value="In Progress">In Progress</option>
                      <option value="Finished">Finished</option>
                    </select>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#64748b' }}>
                      <span title="Edit task" style={{ display: 'inline-flex', cursor: 'pointer' }} onClick={() => handleOpenEdit(t)}>
                        <Edit3 size={15} />
                      </span>
                      <span title="Clone task" style={{ display: 'inline-flex', cursor: 'pointer' }} onClick={() => onAddTask({ ...t, task_code: `${t.task_code}-copy`, title: `${t.title} (Copy)` })}>
                        <Copy size={14} />
                      </span>
                      <span title="Delete task" style={{ display: 'inline-flex', cursor: 'pointer', color: '#ef4444' }} onClick={() => handleDelete(t.id, t.task_code)}>
                        <Trash2 size={15} />
                      </span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add / Edit Task Modal */}
      {modalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3>{editingTask ? `Edit Task (${editingTask.task_code})` : 'Add New Task'}</h3>
              <button onClick={() => setModalOpen(false)} className="modal-close-btn">✕</button>
            </div>
            <form onSubmit={handleSave}>
              <div className="modal-body">
                {errorMessage && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: '#fee2e2', color: '#b91c1c', borderRadius: 8, fontSize: 13 }}>
                    <AlertCircle size={16} />
                    <span>{errorMessage}</span>
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Task Code</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.task_code}
                      onChange={(e) => setFormData({ ...formData, task_code: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Phase</label>
                    <select
                      className="form-select"
                      value={formData.phase}
                      onChange={(e) => setFormData({ ...formData, phase: e.target.value })}
                    >
                      <option value="Planning & Research">Planning & Research</option>
                      <option value="System Design">System Design</option>
                      <option value="Development">Development</option>
                      <option value="Testing & Deployment">Testing & Deployment</option>
                      <option value="Launch & Monitor">Launch & Monitor</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Task Title</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Timeline</label>
                    <select
                      className="form-select"
                      value={formData.timeline}
                      onChange={(e) => setFormData({ ...formData, timeline: e.target.value })}
                    >
                      <option value="30-day">30-day</option>
                      <option value="60-day">60-day</option>
                      <option value="90-day">90-day</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Priority</label>
                    <select
                      className="form-select"
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: e.target.value as any })}
                    >
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-select"
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
                    >
                      <option value="Pending">Pending</option>
                      <option value="Ongoing">Ongoing</option>
                      <option value="In Progress">In Progress</option>
                      <option value="Finished">Finished</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Start Date</label>
                    <input
                      type="date"
                      className="form-input"
                      value={formData.start_date}
                      onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">End Date</label>
                    <input
                      type="date"
                      className="form-input"
                      value={formData.end_date}
                      onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Dependencies (comma separated codes, e.g. TSK-01, TSK-02)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.dependencies}
                    onChange={(e) => setFormData({ ...formData, dependencies: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Deliverables</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.deliverables}
                    onChange={(e) => setFormData({ ...formData, deliverables: e.target.value })}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isLoading}>
                  {editingTask ? 'Save Changes' : 'Create Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
