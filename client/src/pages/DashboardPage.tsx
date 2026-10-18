import React, { useState } from 'react';
import { Project, User } from '../types';
import {
  Layers, Plus, Search, ArrowRight, Trash2, Cpu, LogOut,
  FolderKanban, AlertTriangle, CheckCircle, Clock,
  CheckSquare, Square, Compass, ListTodo, Bot
} from 'lucide-react';
import { LogoutConfirmModal } from '../components/LogoutConfirmModal';
import { ProfileModal } from '../components/ProfileModal';
import { api } from '../services/api';

interface Props {
  user: User;
  projects: Project[];
  onOpenProject: (projectId: string, targetModule?: string) => void;
  onCreateNewProject: () => void;
  onDeleteProject: (projectId: string) => Promise<void>;
  onBulkDeleteProjects?: (projectIds: string[]) => Promise<void>;
  onLogout: () => Promise<void> | void;
  onUserUpdated?: (updatedUser: User) => void;
}

export const DashboardPage: React.FC<Props> = ({
  user,
  projects,
  onOpenProject,
  onCreateNewProject,
  onDeleteProject,
  onBulkDeleteProjects,
  onLogout,
  onUserUpdated
}) => {
  const [search, setSearch] = useState('');
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [deleteModalProject, setDeleteModalProject] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Bulk Management State
  const [isManageMode, setIsManageMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [bulkDeleteError, setBulkDeleteError] = useState<string | null>(null);

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.industry && p.industry.toLowerCase().includes(search.toLowerCase())) ||
    (p.description && p.description.toLowerCase().includes(search.toLowerCase()))
  );

  // Metric computations from real user data
  const totalProjects = projects.length;
  const maxProjects = 10;
  const isLimitReached = totalProjects >= maxProjects;

  const totalCompletedModules = projects.reduce((acc, p) => {
    return acc + (p.generated_modules?.length || 0);
  }, 0);

  const totalTasksCount = projects.reduce((acc, p) => acc + (p.tasks_count || 0), 0);
  const totalCompletedTasks = projects.reduce((acc, p) => acc + (p.completed_tasks_count || 0), 0);

  const handleConfirmDelete = async () => {
    if (!deleteModalProject) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await onDeleteProject(deleteModalProject.id);
      setDeleteModalProject(null);
    } catch (err: any) {
      setDeleteError(err.message || 'Failed to delete project. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedIds.length === filteredProjects.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredProjects.map(p => p.id));
    }
  };

  const handleToggleSelectProject = (projectId: string) => {
    setSelectedIds(prev =>
      prev.includes(projectId) ? prev.filter(id => id !== projectId) : [...prev, projectId]
    );
  };

  const handleConfirmBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    setIsBulkDeleting(true);
    setBulkDeleteError(null);
    try {
      if (onBulkDeleteProjects) {
        await onBulkDeleteProjects(selectedIds);
      } else {
        await api.projects.bulkDelete(selectedIds);
      }
      setSelectedIds([]);
      setBulkDeleteModalOpen(false);
      setIsManageMode(false);
    } catch (err: any) {
      setBulkDeleteError(err.message || 'Failed to delete selected projects.');
    } finally {
      setIsBulkDeleting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-workspace)', color: 'var(--text-main)', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <header style={{
        height: 64,
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-color)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #6d855f, #a68757)',
            color: 'var(--text-main)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 3px 10px rgba(109, 133, 95, 0.25)'
          }}>
            <Layers size={20} />
          </div>
          <div>
            <div style={{ fontSize: 14.5, fontWeight: 800, color: 'var(--text-main)' }}>Venture Atlas</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--primary)', letterSpacing: 0.6 }}>ENTERPRISE BLUEPRINT</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {user.role && user.role !== 'user' && (
            <button
              onClick={() => {
                window.history.pushState({}, '', '/admin');
                window.dispatchEvent(new PopStateEvent('popstate'));
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                backgroundColor: 'rgba(109, 133, 95, 0.12)',
                border: '1px solid rgba(109, 133, 95, 0.25)',
                borderRadius: 8,
                color: 'var(--primary)',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              <Cpu size={14} /> Admin Center
            </button>
          )}

          <button
            onClick={() => setProfileModalOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '5px 12px',
              background: 'var(--bg-subtle)',
              borderRadius: 8,
              border: '1px solid var(--border-color)',
              cursor: 'pointer'
            }}
            title="Profile & Account Settings"
          >
            <div style={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              background: 'var(--bg-subtle)',
              color: 'var(--text-main)',
              fontSize: 11,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {user.username.slice(0, 1).toUpperCase()}
            </div>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-main)' }}>{user.username}</span>
          </button>

          <button onClick={() => setLogoutModalOpen(true)} className="btn-secondary" style={{ padding: '6px 12px', fontSize: 12 }}>
            <LogOut size={13} /> Log Out
          </button>
        </div>
      </header>

      {/* Main Dashboard Area */}
      <main style={{ maxWidth: 1160, width: '100%', margin: '0 auto', padding: '36px 24px', flex: 1, display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Banner with Welcome & Create Project Button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-main)', letterSpacing: -0.3, margin: '0 0 4px 0' }}>
              Venture Architecture Portfolio
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
              Welcome back, <b>{user.username}</b>. Manage your enterprise business blueprints, technology stacks, and execution roadmaps.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {totalProjects > 0 && (
              <button
                onClick={() => {
                  setIsManageMode(!isManageMode);
                  setSelectedIds([]);
                }}
                className="btn-secondary"
                style={{ padding: '9px 16px', fontSize: 13 }}
              >
                {isManageMode ? 'Cancel Selection' : 'Manage Projects'}
              </button>
            )}

            <button
              onClick={onCreateNewProject}
              className="btn-primary"
              disabled={isLimitReached}
              title={isLimitReached ? 'Maximum limit of 10 projects reached. Please delete an older project first.' : 'Architect New Project'}
              style={{
                padding: '10px 18px',
                fontSize: 13.5,
                opacity: isLimitReached ? 0.6 : 1,
                cursor: isLimitReached ? 'not-allowed' : 'pointer'
              }}
            >
              <Plus size={16} /> Architect New Project
            </button>
          </div>
        </div>

        {/* Section B: Portfolio Overview Statistics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          {/* Projects Meter */}
          <div className="card" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Project Allocation</span>
              <span style={{
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 12,
                background: isLimitReached ? '#fee2e2' : 'rgba(109, 133, 95, 0.1)',
                color: isLimitReached ? '#dc2626' : 'var(--primary)'
              }}>
                {totalProjects} / {maxProjects} Limit
              </span>
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-main)' }}>
              {totalProjects} <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>Active {totalProjects === 1 ? 'Venture' : 'Ventures'}</span>
            </div>
            <div style={{ width: '100%', height: 6, background: 'var(--border-color)', borderRadius: 9999, overflow: 'hidden', marginTop: 4 }}>
              <div style={{
                width: `${Math.min(100, (totalProjects / maxProjects) * 100)}%`,
                height: '100%',
                background: isLimitReached ? '#dc2626' : 'linear-gradient(90deg, #6d855f, #a68757)',
                borderRadius: 9999,
                transition: 'width 0.3s ease'
              }} />
            </div>
            {isLimitReached && (
              <span style={{ fontSize: 11, color: '#dc2626', fontWeight: 600 }}>10 / 10 projects used. Delete a project to free a slot.</span>
            )}
          </div>

          {/* Synthesized Modules */}
          <div className="card" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Synthesized Modules</span>
              <CheckCircle size={16} color="#10b981" />
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-main)' }}>
              {totalCompletedModules} <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>Generated Modules</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
              Across BMC, Tech Stack, Validator, Market Research, and Roadmaps.
            </p>
          </div>

          {/* Execution Tasks */}
          <div className="card" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Execution Roadmap Progress</span>
              <Clock size={16} color="var(--primary)" />
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-main)' }}>
              {totalCompletedTasks} / {totalTasksCount} <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>Tasks Done</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
              {totalTasksCount > 0 ? `${Math.round((totalCompletedTasks / totalTasksCount) * 100)}% overall completion rate` : 'No tasks assigned yet'}
            </p>
          </div>
        </div>

        {/* Section F: Quick Module Shortcuts */}
        {totalProjects > 0 && (
          <div className="card" style={{ padding: '16px 20px', background: 'var(--bg-subtle)' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>
              Venture Architecture Modules
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {[
                { name: 'Business Model Canvas', icon: Compass, mod: 'bmc' },
                { name: 'Technology Stack', icon: Cpu, mod: 'tech_stack' },
                { name: 'Execution Roadmap', icon: ListTodo, mod: 'execution_roadmap' },
                { name: 'Planning Copilot', icon: Bot, mod: 'blueprint_copilot' }
              ].map(q => {
                const Icon = q.icon;
                return (
                  <button
                    key={q.mod}
                    onClick={() => onOpenProject(projects[0].id, q.mod)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 14px',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 8,
                      color: 'var(--text-main)',
                      fontSize: 12.5,
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <Icon size={14} color="var(--primary)" />
                    <span>{q.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Filter bar & Bulk Actions Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            padding: '8px 14px',
            width: '100%',
            maxWidth: 380
          }}>
            <Search size={15} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search by name, industry, or keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: 13,
                width: '100%',
                color: 'var(--text-main)'
              }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          {/* Manage Mode Toolbar */}
          {isManageMode ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                onClick={handleToggleSelectAll}
                className="btn-secondary"
                style={{ padding: '6px 12px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {selectedIds.length === filteredProjects.length && filteredProjects.length > 0 ? (
                  <><CheckSquare size={14} color="var(--primary)" /> Deselect All</>
                ) : (
                  <><Square size={14} /> Select All</>
                )}
              </button>

              <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-main)' }}>
                {selectedIds.length} selected
              </span>

              {selectedIds.length > 0 && (
                <button
                  onClick={() => setBulkDeleteModalOpen(true)}
                  className="btn-danger"
                  style={{ padding: '6px 14px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <Trash2 size={13} /> Delete Selected ({selectedIds.length})
                </button>
              )}
            </div>
          ) : (
            <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
              Showing <b>{filteredProjects.length}</b> {filteredProjects.length === 1 ? 'project' : 'projects'}
            </span>
          )}
        </div>

        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '64px 20px', marginTop: 12 }}>
            <div style={{
              width: 58,
              height: 58,
              borderRadius: '50%',
              background: 'rgba(109, 133, 95, 0.12)',
              color: 'var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto'
            }}>
              <FolderKanban size={28} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
              {projects.length === 0 ? 'No Venture Blueprints Yet' : 'No Matching Projects Found'}
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 460, margin: '0 auto 22px auto', lineHeight: 1.5 }}>
              {projects.length === 0
                ? 'Get started by creating your first business blueprint. Synthesize your Business Model Canvas, technology stack, and execution roadmap.'
                : `No projects match "${search}". Try clearing or refining your search query.`}
            </p>
            {projects.length === 0 ? (
              <button onClick={onCreateNewProject} className="btn-primary" style={{ margin: '0 auto' }}>
                <Plus size={16} /> Create Your First Project
              </button>
            ) : (
              <button onClick={() => setSearch('')} className="btn-secondary" style={{ margin: '0 auto' }}>
                Reset Search
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 20 }}>
            {filteredProjects.map((p) => {
              const isSelected = selectedIds.includes(p.id);
              const generatedCount = p.generated_modules?.length || 0;

              return (
                <div
                  key={p.id}
                  onClick={() => {
                    if (isManageMode) {
                      handleToggleSelectProject(p.id);
                    } else {
                      onOpenProject(p.id);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (isManageMode) {
                        handleToggleSelectProject(p.id);
                      } else {
                        onOpenProject(p.id);
                      }
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`${isManageMode ? 'Select' : 'Open'} project ${p.name}`}
                  className="card"
                  style={{
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                    transition: 'all 0.15s ease',
                    border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                    background: isSelected ? 'var(--bg-subtle)' : 'var(--bg-card)',
                    position: 'relative'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = 'var(--primary)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = 'var(--border-color)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                      {isManageMode && (
                        <div style={{ color: isSelected ? 'var(--primary)' : 'var(--text-muted)' }}>
                          {isSelected ? <CheckSquare size={18} /> : <Square size={18} />}
                        </div>
                      )}
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <h3 style={{
                          fontSize: 16,
                          fontWeight: 700,
                          color: 'var(--text-main)',
                          margin: 0,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {p.name}
                        </h3>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
                          {p.industry || 'Technology & Software'}
                        </div>
                      </div>
                    </div>
                    <span className="stage-badge-purple" style={{ flexShrink: 0 }}>
                      {p.stage}
                    </span>
                  </div>

                  <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, flex: 1, margin: 0 }}>
                    {p.description
                      ? (p.description.length > 120 ? p.description.slice(0, 115) + '...' : p.description)
                      : 'No description specified for this venture.'}
                  </p>

                  {/* Module Completion Indicators on Card */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--text-muted)' }}>
                    <span>Modules Synthesized:</span>
                    <span style={{ fontWeight: 700, color: generatedCount > 0 ? '#10b981' : 'var(--text-muted)' }}>
                      {generatedCount} / 6 modules
                    </span>
                  </div>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingTop: 12,
                    borderTop: '1px solid var(--border-color)',
                    marginTop: 6
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--text-light)' }}>
                      Updated {new Date(p.updated_at).toLocaleDateString()}
                    </span>

                    {!isManageMode && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteModalProject(p);
                          }}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: 4,
                            borderRadius: 4,
                            display: 'flex',
                            alignItems: 'center'
                          }}
                          title={`Delete ${p.name}`}
                          onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                        >
                          <Trash2 size={15} />
                        </button>
                        <span style={{
                          fontSize: 12.5,
                          fontWeight: 700,
                          color: 'var(--primary)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4
                        }}>
                          Open <ArrowRight size={13} />
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Bulk Delete Confirmation Dialog */}
      {bulkDeleteModalOpen && (
        <div className="modal-overlay" onClick={() => !isBulkDeleting && setBulkDeleteModalOpen(false)}>
          <div
            className="modal-card"
            style={{ maxWidth: 480 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 34,
                  height: 34,
                  borderRadius: '50%',
                  background: '#fee2e2',
                  color: '#dc2626',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <AlertTriangle size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0 }}>Delete {selectedIds.length} Selected Projects?</h3>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>Permanent bulk deletion</p>
                </div>
              </div>
              <button
                onClick={() => setBulkDeleteModalOpen(false)}
                className="modal-close-btn"
                disabled={isBulkDeleting}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {bulkDeleteError && (
                <div style={{
                  padding: 10,
                  background: '#fee2e2',
                  color: '#b91c1c',
                  borderRadius: 6,
                  fontSize: 12.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 12
                }}>
                  <AlertTriangle size={15} />
                  <span>{bulkDeleteError}</span>
                </div>
              )}
              <p style={{ fontSize: 13.5, color: 'var(--text-main)', lineHeight: 1.5, margin: 0 }}>
                Are you sure you want to permanently delete <b>{selectedIds.length} project(s)</b>?
              </p>
              <div style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                padding: 12,
                fontSize: 12.5,
                color: 'var(--text-muted)',
                lineHeight: 1.5,
                marginTop: 10
              }}>
                All associated module contents, version snapshots, execution roadmap tasks, and Planning Copilot conversations will be permanently deleted in an atomic transaction. This action cannot be undone.
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                onClick={() => setBulkDeleteModalOpen(false)}
                className="btn-secondary"
                disabled={isBulkDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmBulkDelete}
                className="btn-danger"
                disabled={isBulkDeleting}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Trash2 size={14} />
                {isBulkDeleting ? 'Deleting Selected...' : `Permanently Delete ${selectedIds.length} Projects`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User Profile & Account Settings Modal */}
      <ProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        user={user}
        onUserUpdated={onUserUpdated}
      />

      {/* Single Project Delete Modal */}
      {deleteModalProject && (
        <div className="modal-overlay" onClick={() => !isDeleting && setDeleteModalProject(null)}>
          <div
            className="modal-card"
            style={{ maxWidth: 460 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 34,
                  height: 34,
                  borderRadius: '50%',
                  background: '#fee2e2',
                  color: '#dc2626',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <AlertTriangle size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0 }}>Delete Project</h3>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>Permanent deletion action</p>
                </div>
              </div>
              <button
                onClick={() => setDeleteModalProject(null)}
                className="modal-close-btn"
                disabled={isDeleting}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {deleteError && (
                <div style={{
                  padding: 10,
                  background: '#fee2e2',
                  color: '#b91c1c',
                  borderRadius: 6,
                  fontSize: 12.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 10
                }}>
                  <AlertTriangle size={15} />
                  <span>{deleteError}</span>
                </div>
              )}
              <p style={{ fontSize: 13.5, color: 'var(--text-main)', lineHeight: 1.5, margin: 0 }}>
                Are you sure you want to permanently delete <b>"{deleteModalProject.name}"</b>?
              </p>
              <div style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                padding: 12,
                fontSize: 12.5,
                color: 'var(--text-muted)',
                lineHeight: 1.5,
                marginTop: 10
              }}>
                This will permanently remove the venture blueprint, all associated module versions, and all roadmap tasks. This action cannot be undone.
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                onClick={() => setDeleteModalProject(null)}
                className="btn-secondary"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="btn-danger"
                disabled={isDeleting}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Trash2 size={14} />
                {isDeleting ? 'Deleting...' : 'Permanently Delete Project'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logout Confirmation Modal */}
      <LogoutConfirmModal
        isOpen={logoutModalOpen}
        onClose={() => setLogoutModalOpen(false)}
        onConfirm={async () => {
          setIsLoggingOut(true);
          try {
            await onLogout();
          } finally {
            setIsLoggingOut(false);
            setLogoutModalOpen(false);
          }
        }}
        isLoading={isLoggingOut}
      />
    </div>
  );
};

