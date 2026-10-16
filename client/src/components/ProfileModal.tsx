import React, { useState } from 'react';
import { User } from '../types';
import { UserCheck, Moon, Sun, Type, X, Check, AlertCircle, Loader2 } from 'lucide-react';

import { api } from '../services/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  user: User;
  onThemeChange: (theme: 'light' | 'dark') => void;
  currentTheme: 'light' | 'dark';
  onUserUpdated?: (updatedUser: User) => void;
}

export const ProfileModal: React.FC<Props> = ({
  isOpen,
  onClose,
  user,
  onThemeChange,
  currentTheme,
  onUserUpdated
}) => {
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'preferences'>('profile');

  // Profile fields
  const [username, setUsername] = useState(user.username);
  const [email, setEmail] = useState(user.email);
  const [displayName, setDisplayName] = useState(() => localStorage.getItem('aba_fullname') || user.username);
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Password fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Preferences fields
  const [fontPref, setFontPref] = useState(() => localStorage.getItem('aba_font') || 'system');
  const [themePref, setThemePref] = useState<'light' | 'dark'>(currentTheme);
  const [prefSuccess, setPrefSuccess] = useState(false);

  if (!isOpen) return null;

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUpdatingProfile(true);
    setProfileError(null);
    setProfileSuccess(null);

    try {
      localStorage.setItem('aba_fullname', displayName);
      const updated = await api.auth.updateProfile({
        username: username !== user.username ? username : undefined,
        email: email !== user.email ? email : undefined
      });
      if (onUserUpdated && updated) {
        onUserUpdated(updated);
      }
      setProfileSuccess('Profile details successfully updated.');
    } catch (err: any) {
      setProfileError(err.message || 'Failed to update profile. Please verify your inputs.');
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters with letters and numbers.');
      return;
    }

    setIsChangingPassword(true);
    setPasswordError(null);
    setPasswordSuccess(null);

    try {
      await api.auth.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_new_password: confirmPassword
      });
      setPasswordSuccess('Password successfully updated. All other active sessions have been invalidated.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.message || 'Failed to change password. Please verify your current password.');
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleSavePreferences = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('aba_font', fontPref);
    localStorage.setItem('aba_theme', themePref);
    onThemeChange(themePref);

    if (fontPref === 'mono') {
      document.body.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
    } else {
      document.body.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    }

    setPrefSuccess(true);
    setTimeout(() => {
      setPrefSuccess(false);
      onClose();
    }, 800);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: 16
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        style={{
          background: 'var(--bg-card)',
          color: 'var(--text-main)',
          borderRadius: 12,
          padding: 24,
          maxWidth: 520,
          width: '100%',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-color)',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: '#ede9fe',
                color: '#6366f1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <UserCheck size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                User Profile & Preferences
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Manage account details, password credentials, and workspace preferences
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: 20 }}>
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            style={{
              padding: '8px 16px',
              border: 'none',
              background: 'transparent',
              color: activeTab === 'profile' ? 'var(--primary)' : 'var(--text-muted)',
              borderBottom: activeTab === 'profile' ? '2px solid var(--primary)' : '2px solid transparent',
              fontWeight: activeTab === 'profile' ? 700 : 500,
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Profile Info
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('security')}
            style={{
              padding: '8px 16px',
              border: 'none',
              background: 'transparent',
              color: activeTab === 'security' ? 'var(--primary)' : 'var(--text-muted)',
              borderBottom: activeTab === 'security' ? '2px solid var(--primary)' : '2px solid transparent',
              fontWeight: activeTab === 'security' ? 700 : 500,
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Password & Security
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('preferences')}
            style={{
              padding: '8px 16px',
              border: 'none',
              background: 'transparent',
              color: activeTab === 'preferences' ? 'var(--primary)' : 'var(--text-muted)',
              borderBottom: activeTab === 'preferences' ? '2px solid var(--primary)' : '2px solid transparent',
              fontWeight: activeTab === 'preferences' ? 700 : 500,
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            Preferences
          </button>
        </div>

        {/* Tab 1: Profile Information */}
        {activeTab === 'profile' && (
          <form onSubmit={handleUpdateProfile} style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
            {profileSuccess && (
              <div style={{ padding: '8px 12px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Check size={14} /> {profileSuccess}
              </div>
            )}
            {profileError && (
              <div style={{ padding: '8px 12px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {profileError}
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Letters, numbers, underscores, and dashes (3-32 chars).</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Display / Full Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Alex Morgan"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
              <button type="button" className="btn-secondary" onClick={onClose} style={{ padding: '8px 16px', fontSize: 13 }}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={isUpdatingProfile} style={{ padding: '8px 18px', fontSize: 13 }}>
                {isUpdatingProfile ? <Loader2 size={14} className="animate-spin" /> : 'Update Profile'}
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: Password & Security */}
        {activeTab === 'security' && (
          <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
            {passwordSuccess && (
              <div style={{ padding: '8px 12px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Check size={14} /> {passwordSuccess}
              </div>
            )}
            {passwordError && (
              <div style={{ padding: '8px 12px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {passwordError}
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Current Password
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>At least 8 characters with letters and numbers.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-main)',
                  fontSize: 13,
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
              <button type="button" className="btn-secondary" onClick={onClose} style={{ padding: '8px 16px', fontSize: 13 }}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={isChangingPassword} style={{ padding: '8px 18px', fontSize: 13 }}>
                {isChangingPassword ? <Loader2 size={14} className="animate-spin" /> : 'Change Password'}
              </button>
            </div>
          </form>
        )}

        {/* Tab 3: Workspace Preferences */}
        {activeTab === 'preferences' && (
          <form onSubmit={handleSavePreferences} style={{ display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                Workspace Theme
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setThemePref('light')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 6,
                    border: themePref === 'light' ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                    background: themePref === 'light' ? 'var(--bg-subtle)' : 'var(--bg-card)',
                    color: themePref === 'light' ? 'var(--primary)' : 'var(--text-muted)',
                    fontWeight: 600,
                    fontSize: 12.5,
                    cursor: 'pointer'
                  }}
                >
                  <Sun size={15} /> Light Theme
                </button>

                <button
                  type="button"
                  onClick={() => setThemePref('dark')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    padding: '10px 14px',
                    borderRadius: 6,
                    border: themePref === 'dark' ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                    background: themePref === 'dark' ? 'var(--bg-subtle)' : 'var(--bg-card)',
                    color: themePref === 'dark' ? 'var(--primary)' : 'var(--text-muted)',
                    fontWeight: 600,
                    fontSize: 12.5,
                    cursor: 'pointer'
                  }}
                >
                  <Moon size={15} /> Dark Theme
                </button>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                Typography Preference
              </label>
              <div style={{ display: 'flex', gap: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-main)', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="fontPref"
                    value="system"
                    checked={fontPref === 'system'}
                    onChange={() => setFontPref('system')}
                  />
                  <Type size={14} /> Modern Sans-Serif
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-main)', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="fontPref"
                    value="mono"
                    checked={fontPref === 'mono'}
                    onChange={() => setFontPref('mono')}
                  />
                  Monospace / Code
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={onClose}
                style={{ padding: '8px 16px', fontSize: 13 }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary"
                style={{ padding: '8px 18px', fontSize: 13, gap: 6 }}
              >
                {prefSuccess ? <><Check size={14} /> Saved!</> : 'Save Preferences'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

