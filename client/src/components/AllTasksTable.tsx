import React, { useState } from 'react';
import { RoadmapTask } from '../types';
import { Search, Plus, RotateCw, Edit3, Trash2, Copy, AlertCircle, Loader2, X, Flag, CheckCircle2 } from 'lucide-react';
import { deriveAnchorDate, dueByDay, isTaskCompleted } from '../utils/taskMilestones';
import { Dialog } from './common/Dialog';

interface Props {
  tasks: RoadmapTask[];
  onAddTask: (taskData: any) => Promise<void>;
  onUpdateTask: (taskId: string, taskData: any) => Promise<void>;
  onDeleteTask: (taskId: string) => Promise<void>;
  onRegenerate: () => Promise<void>;
  isLoading: boolean;
  isGenerating?: boolean;
  isGenerateDisabled?: boolean;
  generationProgress?: { stageText: string; progressPercent?: number } | null;
  planningAnchor?: string | null;
}

export const AllTasksTable: React.FC<Props> = ({
  tasks,
  onAddTask,
  onUpdateTask,
  onDeleteTask,
  onRegenerate,
  isLoading,
  isGenerating = false,
  isGenerateDisabled = false,
  generationProgress = null,
  planningAnchor
}) => {
  const [filterMilestone, setFilterMilestone] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingTask, setEditingTask] = useState<RoadmapTask | null>(null);
  const [cloningId, setCloningId] = useState<string | null>(null);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [deleteConfirmTask, setDeleteConfirmTask] = useState<{ id: string; code: string; title: string } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Derive anchor date for cumulative milestone calculation
  const anchorDate = deriveAnchorDate(tasks, planningAnchor);

  // Cumulative milestone counts
  const count30 = tasks.filter(t => dueByDay(t, anchorDate, 30)).length;
  const count60 = tasks.filter(t => dueByDay(t, anchorDate, 60)).length;
  const count90 = tasks.filter(t => dueByDay(t, anchorDate, 90)).length;

  // Derive dynamic phases from existing tasks in this project
  const projectPhases = Array.from(new Set(tasks.map(t => t.phase).filter(Boolean)));
  const defaultPhases = projectPhases.length > 0 ? projectPhases : ['Planning & Setup', 'Execution', 'Launch & Operations'];

  const todayStr = new Date().toISOString().slice(0, 10);
  const twoWeeksLater = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString().slice(0, 10);

  const [formData, setFormData] = useState({
    task_code: '',
    title: '',
    description: '',
    phase: defaultPhases[0] || 'Planning',
    timeline: '30-day',
    start_date: todayStr,
    end_date: twoWeeksLater,
    priority: 'Medium',
    status: 'Pending',
    dependencies: '',
    deliverables: '',
    effort: '1 week',
    assigned_to: '',
    assigned_role: ''
  });
  const [showCustomCode, setShowCustomCode] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter tasks by cumulative milestone and search query
  const filteredTasks = tasks.filter(t => {
    if (filterMilestone === '30' && !dueByDay(t, anchorDate, 30)) return false;
    if (filterMilestone === '60' && !dueByDay(t, anchorDate, 60)) return false;
    if (filterMilestone === '90' && !dueByDay(t, anchorDate, 90)) return false;

    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        t.title.toLowerCase().includes(q) ||
        t.task_code.toLowerCase().includes(q) ||
        (t.description && t.description.toLowerCase().includes(q)) ||
        (t.assigned_to && t.assigned_to.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const handleOpenAdd = () => {
    setEditingTask(null);
    setShowCustomCode(false);
    const start = anchorDate || todayStr;
    const end = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString().slice(0, 10);

    setFormData({
      task_code: '', // Let backend allocate next monotonic code by default
      title: '',
      description: '',
      phase: defaultPhases[0] || 'Planning',
      timeline: '30-day',
      start_date: start,
      end_date: end,
      priority: 'Medium',
      status: 'Pending',
      dependencies: '',
      deliverables: '',
      effort: '1 week',
      assigned_to: '',
      assigned_role: ''
    });
    setErrorMessage(null);
    setModalOpen(true);
  };

  const handleOpenEdit = (task: RoadmapTask) => {
    setEditingTask(task);
    setShowCustomCode(true);
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
      effort: task.effort || '',
      assigned_to: task.assigned_to === 'Unassigned' ? '' : (task.assigned_to || ''),
      assigned_role: task.assigned_role || ''
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
        .map(d => d.trim().toUpperCase())
        .filter(Boolean);

      const payload: any = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        phase: formData.phase,
        timeline: formData.timeline,
        start_date: formData.start_date,
        end_date: formData.end_date,
        priority: formData.priority,
        status: formData.status,
        dependencies: depsArray,
        deliverables: formData.deliverables.trim(),
        effort: formData.effort.trim()
      };

      if (formData.task_code.trim()) {
        payload.task_code = formData.task_code.trim().toUpperCase();
      }

      if (formData.assigned_to.trim()) {
        payload.assigned_to = formData.assigned_to.trim();
      }
      if (formData.assigned_role.trim()) {
        payload.assigned_role = formData.assigned_role.trim();
      }

      if (editingTask) {
        await onUpdateTask(editingTask.id, payload);
      } else {
        await onAddTask(payload);
      }
      setModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save task. Verify dates and prerequisites.');
    }
  };

  const handleStatusChange = async (taskId: string, newStatus: string) => {
    try {
      await onUpdateTask(taskId, { status: newStatus });
    } catch (err: any) {
      alert(err.message || 'Failed to update task status.');
    }
  };

  const handleClone = async (task: RoadmapTask) => {
    setCloneError(null);
    setCloningId(task.id);
    try {
      const clonePayload = {
        title: `${task.title} (Copy)`,
        description: task.description || '',
        phase: task.phase,
        timeline: task.timeline,
        start_date: task.start_date,
        end_date: task.end_date,
        priority: task.priority,
        status: 'Pending',
        dependencies: task.dependencies ? [...task.dependencies] : [],
        deliverables: task.deliverables || '',
        effort: task.effort || '',
        assigned_to: task.assigned_to || '',
        assigned_role: task.assigned_role || '',
        department: task.department || ''
      };
      await onAddTask(clonePayload);
    } catch (err: any) {
      setCloneError(err.message || `Could not clone task ${task.task_code}.`);
    } finally {
      setCloningId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirmTask) return;
    setDeleteError(null);
    setIsDeleting(true);
    try {
      await onDeleteTask(deleteConfirmTask.id);
      setDeleteConfirmTask(null);
    } catch (err: any) {
      setDeleteError(err.message || `Cannot delete task ${deleteConfirmTask.code}. Other tasks depend on it.`);
    } finally {
      setIsDeleting(false);
    }
  };

  const getNormalizedStatus = (rawStatus: string): 'Pending' | 'In Progress' | 'Completed' => {
    const s = rawStatus.toLowerCase();
    if (s === 'completed' || s === 'finished') return 'Completed';
    if (s === 'in progress' || s === 'ongoing') return 'In Progress';
    return 'Pending';
  };

  return (
    <div className="card" style={{ padding: 20 }}>
      {/* Header bar */}
      <div className="tasks-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              All Tasks ({filteredTasks.length}{filteredTasks.length !== tasks.length ? ` of ${tasks.length}` : ''})
            </h3>
            {anchorDate && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Planning anchor: {anchorDate}
              </span>
            )}
          </div>

          <div className="task-filter-group" role="group" aria-label="Milestone Filters" style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className={`filter-chip ${filterMilestone === 'all' ? 'active' : ''}`}
              onClick={() => setFilterMilestone('all')}
            >
              All ({tasks.length})
            </button>
            <button
              type="button"
              className={`filter-chip ${filterMilestone === '30' ? 'active' : ''}`}
              onClick={() => setFilterMilestone('30')}
              title="Cumulative: tasks due by day 30 from planning anchor"
            >
              Due by Day 30 ({count30})
            </button>
            <button
              type="button"
              className={`filter-chip ${filterMilestone === '60' ? 'active' : ''}`}
              onClick={() => setFilterMilestone('60')}
              title="Cumulative: tasks due by day 60 from planning anchor"
            >
              Due by Day 60 ({count60})
            </button>
            <button
              type="button"
              className={`filter-chip ${filterMilestone === '90' ? 'active' : ''}`}
              onClick={() => setFilterMilestone('90')}
              title="Cumulative: tasks due by day 90 from planning anchor"
            >
              Due by Day 90 ({count90})
            </button>
          </div>
        </div>

        <div className="tasks-action-group" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '6px 10px' }}>
            <Search size={14} color="var(--text-muted)" />
            <input
              type="text"
              aria-label="Search tasks"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 12.5, color: 'var(--text-main)', width: 140 }}
            />
          </div>

          <button
            type="button"
            onClick={handleOpenAdd}
            className="btn-primary"
            style={{ padding: '7px 14px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Plus size={15} /> Add Task
          </button>

          <button
            type="button"
            onClick={onRegenerate}
            className="btn-secondary"
            disabled={isLoading || isGenerating || isGenerateDisabled}
            title="Generate new roadmap version"
            aria-live="polite"
            style={{ padding: '7px 14px', fontSize: 13 }}
          >
            {isGenerating ? (
              <span role="status" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Loader2 size={14} className="animate-spin" />
                {generationProgress?.stageText || 'Generating roadmap…'}
              </span>
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <RotateCw size={14} /> Generate new version
              </span>
            )}
          </button>
        </div>
      </div>

      {cloneError && (
        <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--border-color)', borderRadius: 6, fontSize: 12.5, marginTop: 12 }}>
          <AlertCircle size={15} />
          <span>{cloneError}</span>
        </div>
      )}

      {/* Table (inert checkboxes removed) */}
      <div className="table-responsive" style={{ marginTop: 14 }}>
        <table className="enterprise-table">
          <thead>
            <tr>
              <th style={{ width: 90 }}>Task Code</th>
              <th style={{ width: 85 }}>Priority</th>
              <th style={{ minWidth: 200 }}>Task Title</th>
              <th style={{ width: 140 }}>Assignee</th>
              <th style={{ width: 110 }}>Due Date</th>
              <th style={{ width: 130 }}>Status</th>
              <th style={{ width: 110, textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '36px 0', color: 'var(--text-muted)' }}>
                  No tasks found matching your filter criteria.
                </td>
              </tr>
            ) : (
              filteredTasks.map((t) => {
                const normStatus = getNormalizedStatus(t.status);
                const isCloningThis = cloningId === t.id;

                return (
                  <tr key={t.id}>
                    <td style={{ fontWeight: 700, color: 'var(--text-main)', fontSize: 12, whiteSpace: 'nowrap' }}>
                      {t.task_code}
                    </td>
                    <td>
                      <span className={`badge-priority ${t.priority.toLowerCase()}`}>
                        {t.priority}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: 13 }}>{t.title}</div>
                      {t.deliverables && (
                        <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>
                          Deliverable: {t.deliverables}
                        </div>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: t.assigned_to ? 'var(--text-main)' : 'var(--text-muted)' }}>
                      {t.assigned_to || (t.assigned_role ? `${t.assigned_role} (Role unassigned)` : 'Unassigned')}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {t.end_date || '—'}
                    </td>
                    <td>
                      <select
                        aria-label={`Status for ${t.task_code}`}
                        className="status-select"
                        value={normStatus}
                        onChange={(e) => handleStatusChange(t.id, e.target.value)}
                        style={{ fontSize: 12, padding: '4px 8px', borderRadius: 6 }}
                      >
                        <option value="Pending">Pending</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Completed">Completed</option>
                      </select>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)' }}>
                        <button
                          type="button"
                          aria-label={`Edit task ${t.task_code}`}
                          title="Edit task"
                          style={{ display: 'inline-flex', cursor: 'pointer', border: 0, padding: 4, color: 'var(--text-muted)', background: 'transparent' }}
                          onClick={() => handleOpenEdit(t)}
                        >
                          <Edit3 size={15} />
                        </button>
                        <button
                          type="button"
                          aria-label={`Clone task ${t.task_code}`}
                          title="Clone task (allocates new code)"
                          disabled={isCloningThis}
                          style={{ display: 'inline-flex', cursor: isCloningThis ? 'wait' : 'pointer', border: 0, padding: 4, color: 'var(--text-muted)', background: 'transparent' }}
                          onClick={() => void handleClone(t)}
                        >
                          {isCloningThis ? <Loader2 size={14} className="animate-spin" /> : <Copy size={14} />}
                        </button>
                        <button
                          type="button"
                          aria-label={`Delete task ${t.task_code}`}
                          title="Delete task"
                          style={{ display: 'inline-flex', cursor: 'pointer', border: 0, padding: 4, color: 'var(--danger-text)', background: 'transparent' }}
                          onClick={() => setDeleteConfirmTask({ id: t.id, code: t.task_code, title: t.title })}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Add / Edit Task Modal using common Dialog */}
      <Dialog
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingTask ? `Edit Task (${editingTask.task_code})` : 'Add New Task'}
        maxWidth={580}
      >
        <form onSubmit={handleSave}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '8px 0' }}>
            {errorMessage && (
              <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 13 }}>
                <AlertCircle size={16} />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="task-form-title" className="form-label">Task Title *</label>
              <input
                id="task-form-title"
                type="text"
                className="form-input"
                placeholder="e.g. Set up WhatsApp business account or register business name"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label htmlFor="task-form-phase" className="form-label">Project Phase</label>
                <select
                  id="task-form-phase"
                  className="form-select"
                  value={formData.phase}
                  onChange={(e) => setFormData({ ...formData, phase: e.target.value })}
                >
                  {defaultPhases.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                  {!defaultPhases.includes(formData.phase) && formData.phase && (
                    <option value={formData.phase}>{formData.phase}</option>
                  )}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="task-form-priority" className="form-label">Priority</label>
                <select
                  id="task-form-priority"
                  className="form-select"
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                >
                  <option value="Critical">Critical</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label htmlFor="task-form-start-date" className="form-label">Start Date *</label>
                <input
                  id="task-form-start-date"
                  type="date"
                  className="form-input"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="task-form-end-date" className="form-label">End Date (Due Date) *</label>
                <input
                  id="task-form-end-date"
                  type="date"
                  className="form-input"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label htmlFor="task-form-assignee" className="form-label">Assigned Person (Optional)</label>
                <input
                  id="task-form-assignee"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Sarah or Solo Founder"
                  value={formData.assigned_to}
                  onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label htmlFor="task-form-role" className="form-label">Role Responsibility</label>
                <input
                  id="task-form-role"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Lead Mechanic, Operations, Owner"
                  value={formData.assigned_role}
                  onChange={(e) => setFormData({ ...formData, assigned_role: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="task-form-deliverables" className="form-label">Deliverable / Expected Outcome</label>
              <input
                id="task-form-deliverables"
                type="text"
                className="form-input"
                placeholder="e.g. WhatsApp booking catalog live with service pricing"
                value={formData.deliverables}
                onChange={(e) => setFormData({ ...formData, deliverables: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="task-form-deps" className="form-label">Prerequisites (Task Codes, comma separated)</label>
              <input
                id="task-form-deps"
                type="text"
                className="form-input"
                placeholder="e.g. TSK-01, TSK-02"
                value={formData.dependencies}
                onChange={(e) => setFormData({ ...formData, dependencies: e.target.value })}
              />
              <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '3px 0 0 0' }}>
                Handover invariant: start date must be on or after prerequisite end date.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="task-form-desc" className="form-label">Description</label>
              <textarea
                id="task-form-desc"
                className="form-textarea"
                rows={2}
                placeholder="Specific operational steps and details..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>

            {/* Optional custom code disclosure */}
            {!editingTask && (
              <div>
                {!showCustomCode ? (
                  <button
                    type="button"
                    onClick={() => setShowCustomCode(true)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--primary)', fontSize: 12, cursor: 'pointer', padding: 0 }}
                  >
                    + Specify custom task code (otherwise allocated automatically)
                  </button>
                ) : (
                  <div className="form-group" style={{ marginTop: 6 }}>
                    <label htmlFor="task-form-code" className="form-label">Custom Task Code</label>
                    <input
                      id="task-form-code"
                      type="text"
                      className="form-input"
                      placeholder="e.g. TSK-10"
                      value={formData.task_code}
                      onChange={(e) => setFormData({ ...formData, task_code: e.target.value })}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="modal-footer" style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isLoading}>
              {editingTask ? 'Save Changes' : 'Create Task'}
            </button>
          </div>
        </form>
      </Dialog>

      {/* Shared Delete Confirmation Dialog replacing window.confirm */}
      {deleteConfirmTask && (
        <Dialog
          isOpen={true}
          onClose={() => setDeleteConfirmTask(null)}
          title={`Delete Task ${deleteConfirmTask.code}?`}
          maxWidth={460}
          dismissible={!isDeleting}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '6px 0' }}>
            <p style={{ fontSize: 13, color: 'var(--text-main)', margin: 0 }}>
              Are you sure you want to delete <b>{deleteConfirmTask.title}</b> ({deleteConfirmTask.code})?
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
              To protect schedule integrity, tasks cannot be deleted if other tasks depend on them.
            </p>
            {deleteError && (
              <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--border-color)', borderRadius: 6, fontSize: 12.5 }}>
                <AlertCircle size={16} />
                <span>{deleteError}</span>
              </div>
            )}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12 }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setDeleteConfirmTask(null)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={isDeleting}
                style={{
                  padding: '8px 18px',
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-main)',
                  background: 'var(--danger-text)',
                  border: 'none',
                  borderRadius: 6,
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                {isDeleting ? 'Deleting...' : 'Delete Task'}
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
};
