import React, { useState, useEffect } from 'react';
import { Project, User } from '../types';
import {
  Layers, Plus, Search, ArrowRight, Trash2, Cpu, LogOut,
  FolderKanban, AlertTriangle, Moon, Sun
} from 'lucide-react';
import { LogoutConfirmModal } from '../components/LogoutConfirmModal';

interface Props {
  user: User;
  projects: Project[];
  onOpenProject: (projectId: string) => void;
  onCreateNewProject: () => void;
  onDeleteProject: (projectId: string) => Promise<void>;
  onLogout: () => Promise<void> | void;
}

export const DashboardPage: React.FC<Props> = ({
  user,
  projects,
  onOpenProject,
  onCreateNewProject,
  onDeleteProject,
  onLogout
}) => {
  const [search, setSearch] = useState('');
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [deleteModalProject, setDeleteModalProject] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('aba_theme') as 'light' | 'dark') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('aba_theme', nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
  };

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.industry && p.industry.toLowerCase().includes(search.toLowerCase())) ||
    (p.description && p.description.toLowerCase().includes(search.toLowerCase()))
  );

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
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 3px 10px rgba(99, 102, 241, 0.25)'
          }}>
            <Layers size={20} />
          </div>
          <div>
            <div style={{ fontSize: 14.5, fontWeight: 800, color: 'var(--text-main)' }}>Business Architect</div>
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
                backgroundColor: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
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
            className="header-icon-btn"
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Moon size={16} color="#a5b4fc" /> : <Sun size={16} color="#64748b" />}
          </button>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '4px 10px',
            background: 'var(--bg-subtle)',
            borderRadius: 8,
            border: '1px solid var(--border-color)'
          }}>
            <div style={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              background: '#1e293b',
              color: '#fff',
              fontSize: 11,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {user.username.slice(0, 1).toUpperCase()}
            </div>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-main)' }}>{user.username}</span>
          </div>

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
              Welcome back, <b>{user.username}</b>. Manage your business blueprints, architecture designs, and execution roadmaps.
            </p>
          </div>

          <button onClick={onCreateNewProject} className="btn-primary" style={{ padding: '10px 18px', fontSize: 13.5 }}>
            <Plus size={16} /> Architect New Project
          </button>
        </div>

        {/* Filter bar */}
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
            <Search size={15} color="#94a3b8" />
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
          <span style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
            Showing <b>{filteredProjects.length}</b> {filteredProjects.length === 1 ? 'project' : 'projects'}
          </span>
        </div>

        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '64px 20px', marginTop: 12 }}>
            <div style={{
              width: 58,
              height: 58,
              borderRadius: '50%',
              background: 'rgba(99, 102, 241, 0.12)',
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
            {filteredProjects.map((p) => (
              <div
                key={p.id}
                onClick={() => onOpenProject(p.id)}
                className="card"
                style={{
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                  transition: 'all 0.15s ease',
                  border: '1px solid var(--border-color)',
                  position: 'relative'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--primary)';
                  e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-color)';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
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
                  <span className="stage-badge-purple" style={{ flexShrink: 0 }}>
                    {p.stage}
                  </span>
                </div>

                <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, flex: 1, margin: 0 }}>
                  {p.description
                    ? (p.description.length > 120 ? p.description.slice(0, 115) + '...' : p.description)
                    : 'No description specified for this venture.'}
                </p>

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
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Styled Project Delete Confirmation Dialog */}
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
                  gap: 8
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
                lineHeight: 1.5
              }}>
                This will permanently remove the venture blueprint, all associated module versions (BMC, Tech Stack, Idea Validation, Market Research), and all roadmap tasks. This action cannot be undone.
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
