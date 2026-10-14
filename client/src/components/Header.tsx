import React, { useState } from 'react';
import { Project, User } from '../types';
import { Search, Sun, Bell, Edit3, LogOut, ChevronDown } from 'lucide-react';

interface Props {
  project: Project;
  user: User;
  onLogout: () => void;
  onEditProject?: () => void;
}

export const Header: React.FC<Props> = ({ project, user, onLogout, onEditProject }) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [themeDark, setThemeDark] = useState(false);

  const toggleTheme = () => {
    setThemeDark(!themeDark);
  };

  return (
    <header className="top-header">
      {/* Left: Project title and details */}
      <div className="header-left">
        <div className="header-title-row">
          <h2>{project.name}</h2>
          <span title="Edit project details" style={{ display: 'inline-flex', cursor: 'pointer' }} onClick={onEditProject}>
            <Edit3 size={14} color="#64748b" />
          </span>
          <span className="stage-badge-purple">
            {project.stage.includes('Growth') ? 'Growth Stage' : project.stage}
          </span>
        </div>
        <p className="header-subtitle">
          {project.description || `${project.industry || 'Technology'} venture blueprint`}
        </p>
      </div>

      {/* Right: Search, tools, and user account */}
      <div className="header-right">
        <div className="search-input-box">
          <Search size={15} color="#94a3b8" />
          <input type="text" placeholder="Search projects, tasks, or modules..." />
          <span className="kbd-shortcut">Ctrl K</span>
        </div>

        <button className="header-icon-btn" title="Toggle theme" onClick={toggleTheme}>
          <Sun size={17} color={themeDark ? '#6366f1' : 'currentColor'} />
        </button>

        <div style={{ position: 'relative' }}>
          <button className="header-icon-btn" title="Notifications" onClick={() => setNotificationsOpen(!notificationsOpen)}>
            <Bell size={17} />
            <span className="notification-dot" />
          </button>

          {notificationsOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: 6,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
                width: 240,
                zIndex: 100,
                padding: '10px 14px'
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>System Notifications</div>
              <div style={{ fontSize: 11.5, color: '#64748b' }}>AI Business Architect is fully operational. All modules active.</div>
            </div>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <div
            className="user-profile-badge"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
          >
            <div className="user-avatar-circle">
              {user.username.slice(0, 1).toUpperCase()}
            </div>
            <span className="user-name-text">{user.username}</span>
            <ChevronDown size={12} color="#64748b" />
          </div>

          {userMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: 6,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
                width: 170,
                zIndex: 100,
                padding: 4
              }}
            >
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', fontSize: 11, color: '#64748b' }}>
                Signed in as <b>{user.username}</b>
              </div>
              {user.role && user.role !== 'user' && (
                <button
                  onClick={() => {
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
                    color: '#6366f1',
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <Search size={14} /> Admin Center
                </button>
              )}
              <button
                onClick={onLogout}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  border: 'none',
                  background: 'transparent',
                  color: '#ef4444',
                  fontSize: 12.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                <LogOut size={14} /> Log Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
