import React, { useEffect, useState } from 'react';
import { Project, User } from '../types';
import { Search, Activity, Edit3, LogOut, ChevronDown, UserCheck, Shield, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react';
import { ProfileModal } from './ProfileModal';
import { LogoutConfirmModal } from './LogoutConfirmModal';
import { api } from '../services/api';

const searchableModules = [
  { id: 'overview', label: 'Overview' },
  { id: 'bmc', label: 'Business Model Canvas' },
  { id: 'tech_stack', label: 'Technology Stack' },
  { id: 'idea_validator', label: 'Idea Validator' },
  { id: 'market_research', label: 'Market Research' },
  { id: 'execution_roadmap', label: 'Roadmap & Execution Plan' },
  { id: 'blueprint_copilot', label: 'Planning Copilot' },
];

interface ProjectSearchResult {
  label: string;
  detail: string;
  module: string;
}

interface Props {
  project: Project;
  user: User;
  onLogout: () => Promise<void>;
  onEditProject?: () => void;
  onSelectModule?: (module: string) => void;
  onUserUpdated?: (user: User) => void;
}

export const Header: React.FC<Props> = ({ project, user, onLogout, onEditProject, onSelectModule, onUserUpdated }) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);
  const [serviceHealth, setServiceHealth] = useState<{ status: string; database_connected: boolean; generation_configured: boolean } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ProjectSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    const query = searchQuery.trim().toLowerCase();
    if (query.length < 2) return;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const results: ProjectSearchResult[] = searchableModules
        .filter((module) => module.label.toLowerCase().includes(query))
        .map((module) => ({ label: module.label, detail: 'Open workspace section', module: module.id }));

      const projectText = [project.name, project.description, project.industry, project.target_customers, project.goals, project.business_context, project.budget]
        .filter(Boolean).join(' ');
      if (projectText.toLowerCase().includes(query)) {
        results.push({ label: project.name, detail: 'Project details', module: 'overview' });
      }

      const generated = new Set((project.generated_modules || []).map((type) => type === 'detailed_roadmap' ? 'execution_roadmap' : type));
      if (project.active_module) generated.add(project.active_module);
      const readableModules = searchableModules.filter((module) => generated.has(module.id) && !['overview', 'blueprint_copilot'].includes(module.id));
      const [taskResult, ...moduleResults] = await Promise.allSettled([
        api.tasks.list(project.id, { search: searchQuery.trim() }),
        ...readableModules.map((module) => api.modules.get(project.id, module.id))
      ]);

      if (taskResult.status === 'fulfilled') {
        taskResult.value.slice(0, 4).forEach((task) => results.push({
          label: task.title,
          detail: `Roadmap task · ${task.phase}`,
          module: 'execution_roadmap'
        }));
      }

      moduleResults.forEach((result, index) => {
        if (result.status !== 'fulfilled' || !result.value.data) return;
        const content = JSON.stringify(result.value.data).replace(/[{},"]/g, ' ').replace(/\[/g, ' ').replace(/\]/g, ' ');
        const foundAt = content.toLowerCase().indexOf(query);
        if (foundAt < 0) return;
        const detail = content.slice(Math.max(0, foundAt - 32), Math.min(content.length, foundAt + 100)).replace(/\s+/g, ' ').trim();
        results.push({ label: `Match in ${readableModules[index].label}`, detail, module: readableModules[index].id });
      });

      if (!cancelled) {
        const unique = new Map(results.map((result) => [`${result.module}:${result.label}`, result]));
        setSearchResults(Array.from(unique.values()).slice(0, 7));
        setSearchLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchQuery, project.id, project.name, project.description, project.industry, project.target_customers, project.goals, project.business_context, project.budget, project.generated_modules, project.active_module]);

  const checkServiceHealth = async () => {
    setHealthOpen(true);
    setHealthLoading(true);
    try {
      setServiceHealth(await api.health());
    } catch {
      setServiceHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    const shouldSearch = value.trim().length >= 2;
    setSearchLoading(shouldSearch);
    if (!shouldSearch) setSearchResults([]);
  };

  const handleConfirmLogout = async () => {
    setIsLoggingOut(true);
    try {
      await onLogout();
    } finally {
      setIsLoggingOut(false);
      setLogoutModalOpen(false);
    }
  };

  return (
    <header className="top-header">
      {/* Left: Project title and details */}
      <div className="header-left">
        <div className="header-title-row">
          <h2>{project.name}</h2>
          <button type="button" title="Edit project details" aria-label="Edit project details" style={{ display: 'inline-flex', cursor: 'pointer', border: 0, padding: 3, background: 'transparent', color: 'var(--text-muted)' }} onClick={onEditProject}>
            <Edit3 size={14} color="var(--text-muted)" />
          </button>
          <span className="stage-badge-purple">
            {project.stage === 'Idea / MVP' ? 'MVP' : project.stage}
          </span>
        </div>
        <p className="header-subtitle">
          {project.description || `${project.industry || 'Technology'} venture blueprint`}
        </p>
      </div>

      {/* Right: Search, tools, and user account */}
      <div className="header-right">
        <div className="project-search-wrap">
          <div className="search-input-box">
            <Search size={15} color="var(--text-muted)" />
            <input
              type="search"
              placeholder="Search project content..."
              aria-label="Search project content"
              value={searchQuery}
              onChange={(event) => handleSearchChange(event.target.value)}
            />
            {searchQuery && <button type="button" aria-label="Clear search" onClick={() => setSearchQuery('')} className="search-clear-btn"><X size={13} /></button>}
          </div>
          {searchQuery.trim().length >= 2 && (
            <div className="project-search-results" role="listbox" aria-label="Project search results">
              {searchLoading ? <div className="project-search-empty">Searching this project…</div> : searchResults.length ? searchResults.map((result, index) => (
                <button key={`${result.module}:${result.label}:${index}`} type="button" className="project-search-result" onClick={() => { onSelectModule?.(result.module); setSearchQuery(''); }}>
                  <span>{result.label}</span><small>{result.detail}</small>
                </button>
              )) : <div className="project-search-empty">No matching project content found.</div>}
            </div>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <button
            className="header-icon-btn"
            title="Check service health"
            onClick={() => healthOpen ? setHealthOpen(false) : void checkServiceHealth()}
            aria-label="Check service health"
            aria-expanded={healthOpen}
          >
            {healthLoading ? <Loader2 size={16} className="animate-spin" /> : <Activity size={17} />}
          </button>

          {healthOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: 6,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                boxShadow: 'var(--shadow-md)',
                width: 260,
                zIndex: 100,
                padding: '12px 14px',
                color: 'var(--text-main)'
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>Service health</div>
              {healthLoading ? <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Checking the local service…</div> : serviceHealth ? (
                <div style={{ display: 'grid', gap: 5, fontSize: 11.5, color: 'var(--text-muted)' }} aria-live="polite">
                  <span><CheckCircle2 size={12} /> API {serviceHealth.status === 'healthy' ? 'available' : 'degraded'}</span>
                  <span>{serviceHealth.database_connected ? 'Database connected' : 'Database unavailable'}</span>
                  <span>{serviceHealth.generation_configured ? 'Generation provider configured' : 'Generation provider not configured'}</span>
                </div>
              ) : <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 11.5, color: 'var(--danger-text)' }}><AlertCircle size={13} /> Service health could not be checked.</div>}
              <button type="button" className="health-refresh-btn" onClick={() => void checkServiceHealth()}>Check again</button>
            </div>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <button
            type="button"
            className="user-profile-badge"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            aria-label="User menu"
            aria-expanded={userMenuOpen}
          >
            <div className="user-avatar-circle">
              {user.username.slice(0, 1).toUpperCase()}
            </div>
            <span className="user-name-text">{user.username}</span>
            <ChevronDown size={12} color="var(--text-muted)" />
          </button>

          {userMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: 6,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                boxShadow: 'var(--shadow-md)',
                width: 200,
                zIndex: 100,
                padding: 4
              }}
            >
              <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-color)', fontSize: 11, color: 'var(--text-muted)' }}>
                Signed in as <b>{user.username}</b>
              </div>

              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  setProfileModalOpen(true);
                }}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-main)',
                  fontSize: 12.5,
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                <UserCheck size={14} color="var(--primary-text)" /> Profile & Settings
              </button>

              {user.role && user.role !== 'user' && (
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    window.history.pushState({}, '', '/admin');
                    window.dispatchEvent(new PopStateEvent('popstate'));
                  }}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--primary-text)',
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <Shield size={14} /> Admin Center
                </button>
              )}

              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  setLogoutModalOpen(true);
                }}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--danger-text)',
                  fontSize: 12.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                  textAlign: 'left',
                  borderTop: '1px solid var(--border-color)'
                }}
              >
                <LogOut size={14} /> Log Out
              </button>
            </div>
          )}
        </div>
      </div>

      {/* User Profile & Preferences Modal */}
      <ProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        user={user}
        onUserUpdated={onUserUpdated}
      />

      {/* Logout Confirmation Modal */}
      <LogoutConfirmModal
        isOpen={logoutModalOpen}
        onClose={() => setLogoutModalOpen(false)}
        onConfirm={handleConfirmLogout}
        isLoading={isLoggingOut}
      />
    </header>
  );
};
