import React, { useState, useEffect } from 'react';
import { Project, User } from '../types';
import { Search, Sun, Moon, Bell, Edit3, LogOut, ChevronDown, UserCheck, Shield } from 'lucide-react';
import { ProfileModal } from './ProfileModal';
import { LogoutConfirmModal } from './LogoutConfirmModal';

interface Props {
  project: Project;
  user: User;
  onLogout: () => Promise<void>;
  onEditProject?: () => void;
  onUserUpdated?: (user: User) => void;
}

export const Header: React.FC<Props> = ({ project, user, onLogout, onEditProject, onUserUpdated }) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
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
          <input
            type="text"
            placeholder="Search within this project..."
            aria-label="Search within project"
          />
        </div>

        <button
          className="header-icon-btn"
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Moon size={17} color="#a5b4fc" /> : <Sun size={17} color="#64748b" />}
        </button>

        <div style={{ position: 'relative' }}>
          <button
            className="header-icon-btn"
            title="Notifications"
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            aria-label="Notifications"
          >
            <Bell size={17} />
          </button>

          {notificationsOpen && (
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
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)', marginBottom: 4 }}>System Status</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>System operational. All blueprint planning features ready.</div>
            </div>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <div
            className="user-profile-badge"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            role="button"
            tabIndex={0}
            aria-label="User menu"
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
                <UserCheck size={14} color="#6366f1" /> Profile & Settings
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
                    color: '#6366f1',
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
                  color: '#ef4444',
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
        onThemeChange={(newTheme) => {
          setTheme(newTheme);
          document.documentElement.setAttribute('data-theme', newTheme);
        }}
        currentTheme={theme}
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
