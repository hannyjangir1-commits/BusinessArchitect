import React, { useState } from 'react';
import { Project, User } from '../types';
import { Layers, Plus, Search, Calendar, ArrowRight, Trash2, LayoutDashboard, Compass, Cpu, LogOut } from 'lucide-react';

interface Props {
  user: User;
  projects: Project[];
  onOpenProject: (projectId: string) => void;
  onCreateNewProject: () => void;
  onDeleteProject: (projectId: string) => Promise<void>;
  onLogout: () => void;
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

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.industry && p.industry.toLowerCase().includes(search.toLowerCase())) ||
    (p.description && p.description.toLowerCase().includes(search.toLowerCase()))
  );

  const handleDelete = async (e: React.MouseEvent, p: Project) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete project "${p.name}"? This action will permanently delete all associated versions, roadmap tasks, and modules.`)) {
      await onDeleteProject(p.id);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <header style={{ height: 64, background: '#ffffff', borderBottom: '1px solid #e2e8f0', padding: '0 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={18} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: '#0f172a' }}>AI Business Architect</div>
            <div style={{ fontSize: 9.5, fontWeight: 700, color: '#6366f1' }}>ENTERPRISE BLUEPRINT</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 10px', background: '#f1f5f9', borderRadius: 8 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', background: '#1e293b', color: '#fff', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {user.username.slice(0, 1).toUpperCase()}
            </div>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: '#334155' }}>{user.username}</span>
          </div>

          <button onClick={onLogout} className="btn-secondary" style={{ padding: '6px 12px', fontSize: 12 }}>
            <LogOut size={13} /> Log Out
          </button>
        </div>
      </header>

      {/* Main Dashboard Area */}
      <main style={{ maxWidth: 1140, width: '100%', margin: '0 auto', padding: '36px 24px', flex: 1, display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Banner with Welcome & Create Project Button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: '#0f172a', letterSpacing: -0.3 }}>
              Venture Architecture Portfolio
            </h1>
            <p style={{ fontSize: 13, color: '#64748b', marginTop: 2 }}>
              Manage your business blueprints, Business Model Canvases, technology stacks, and execution roadmaps.
            </p>
          </div>

          <button onClick={onCreateNewProject} className="btn-primary" style={{ padding: '10px 18px', fontSize: 13.5 }}>
            <Plus size={16} /> Architect New Project
          </button>
        </div>

        {/* Filter bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 14px', width: 340 }}>
            <Search size={15} color="#94a3b8" />
            <input
              type="text"
              placeholder="Search projects by name, industry, or keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 13, width: '100%' }}
            />
          </div>
          <span style={{ fontSize: 12, color: '#64748b' }}>
            Showing <b>{filteredProjects.length}</b> {filteredProjects.length === 1 ? 'project' : 'projects'}
          </span>
        </div>

        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px', marginTop: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
              <Layers size={28} />
            </div>
            <h3 style={{ fontSize: 17, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
              {projects.length === 0 ? 'No Venture Blueprints Yet' : 'No Matching Projects Found'}
            </h3>
            <p style={{ fontSize: 13, color: '#64748b', maxWidth: 440, margin: '0 auto 20px auto' }}>
              {projects.length === 0
                ? 'Get started by creating your first business blueprint. Gemini will synthesize your Business Model Canvas, technology stack, and execution roadmap.'
                : 'Try refining your search terms to locate your project.'}
            </p>
            {projects.length === 0 && (
              <button onClick={onCreateNewProject} className="btn-primary" style={{ margin: '0 auto' }}>
                <Plus size={16} /> Create Your First Project
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
                  border: '1px solid #e2e8f0'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#c7d2fe';
                  e.currentTarget.style.boxShadow = '0 8px 20px rgba(99, 102, 241, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#e2e8f0';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a' }}>{p.name}</h3>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                      {p.industry || 'Technology'}
                    </div>
                  </div>
                  <span className="stage-badge-purple">
                    {p.stage}
                  </span>
                </div>

                <p style={{ fontSize: 12.5, color: '#475569', lineHeight: 1.4, flex: 1 }}>
                  {p.description ? (p.description.length > 110 ? p.description.slice(0, 105) + '...' : p.description) : 'No description provided.'}
                </p>

                {/* Progress Bar */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11.5, fontWeight: 600, color: '#64748b', marginBottom: 4 }}>
                    <span>Roadmap Progress</span>
                    <span>{p.progress_percentage || 50}%</span>
                  </div>
                  <div style={{ height: 6, background: '#f1f5f9', borderRadius: 9999, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${p.progress_percentage || 50}%`,
                        background: 'linear-gradient(90deg, #10b981, #6366f1)',
                        borderRadius: 9999
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 10, borderTop: '1px solid #f1f5f9', marginTop: 4 }}>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>
                    Last modified: {new Date(p.updated_at).toLocaleDateString()}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button
                      onClick={(e) => handleDelete(e, p)}
                      style={{ border: 'none', background: 'transparent', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
                      title="Delete project"
                      onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                      onMouseLeave={(e) => e.currentTarget.style.color = '#94a3b8'}
                    >
                      <Trash2 size={15} />
                    </button>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#6366f1', display: 'flex', alignItems: 'center', gap: 4 }}>
                      Open <ArrowRight size={13} />
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
