import React, { useState } from 'react';
import { User } from '../types';
import { UserCheck, Type, X, Check, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { Dialog } from './common/Dialog';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  user: User;
  onUserUpdated?: (updatedUser: User) => void;
}

export const ProfileModal: React.FC<Props> = ({
  isOpen,
  onClose,
  user,
  onUserUpdated
}) => {
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'preferences'>('profile');

  // Profile fields
  const [username, setUsername] = useState(user.username);
  const [email, setEmail] = useState(user.email);
  const [displayName, setDisplayName] = useState(() => user.display_name || user.username);
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

  // Preferences fields (honestly scoped to typography appearance)
  const [fontPref, setFontPref] = useState(() => user.preferences?.font || 'system');
  const [prefSuccess, setPrefSuccess] = useState(false);

  if (!isOpen) return null;

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUpdatingProfile(true);
    setProfileError(null);
    setProfileSuccess(null);

    try {
      const updated = await api.auth.updateProfile({
        display_name: displayName,
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

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    try {
      const updated = await api.auth.updateProfile({ preferences: { font: fontPref as 'system' | 'mono' } });
      onUserUpdated?.(updated);
      document.body.style.fontFamily = fontPref === 'mono'
        ? 'ui-monospace, Consolas, monospace' : 'var(--font-family)';
      setPrefSuccess(true);
    } catch (error: any) {
      setProfileError(error.message || 'Preferences could not be saved.');
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      showCloseButton={false}
      ariaLabelledBy="profile-modal-title"
      maxWidth={520}
    >
      <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '85vh' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: 'var(--bg-subtle)',
                color: 'var(--primary-text)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <UserCheck size={18} />
            </div>
            <div>
              <h3 id="profile-modal-title" style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                User Profile & Preferences
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Manage account details, password credentials, and workspace preferences
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close profile settings"
            className="modal-close-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div role="tablist" aria-label="Profile Sections" style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: 20 }}>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'profile'}
            aria-controls="profile-tab-panel"
            id="tab-profile"
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
            role="tab"
            aria-selected={activeTab === 'security'}
            aria-controls="security-tab-panel"
            id="tab-security"
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
            role="tab"
            aria-selected={activeTab === 'preferences'}
            aria-controls="preferences-tab-panel"
            id="tab-preferences"
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
          <form
            id="profile-tab-panel"
            role="tabpanel"
            aria-labelledby="tab-profile"
            onSubmit={handleUpdateProfile}
            style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}
          >
            {profileSuccess && (
              <div role="status" style={{ padding: '8px 12px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', border: '1px solid var(--border-color)', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Check size={14} /> {profileSuccess}
              </div>
            )}
            {profileError && (
              <div role="alert" style={{ padding: '8px 12px', background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--bg-subtle)', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {profileError}
              </div>
            )}

            <div>
              <label htmlFor="profile-username" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Username
              </label>
              <input
                id="profile-username"
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
              <label htmlFor="profile-email" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Email Address
              </label>
              <input
                id="profile-email"
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
              <label htmlFor="profile-display-name" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Display Name (Optional)
              </label>
              <input
                id="profile-display-name"
                type="text"
                placeholder="e.g. Alex Morgan"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
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
          <form
            id="security-tab-panel"
            role="tabpanel"
            aria-labelledby="tab-security"
            onSubmit={handleChangePassword}
            style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}
          >
            {passwordSuccess && (
              <div role="status" style={{ padding: '8px 12px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', border: '1px solid var(--border-color)', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Check size={14} /> {passwordSuccess}
              </div>
            )}
            {passwordError && (
              <div role="alert" style={{ padding: '8px 12px', background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--bg-subtle)', borderRadius: 6, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {passwordError}
              </div>
            )}

            <div>
              <label htmlFor="profile-current-password" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Current Password
              </label>
              <input
                id="profile-current-password"
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
              <label htmlFor="profile-new-password" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                New Password
              </label>
              <input
                id="profile-new-password"
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
              <label htmlFor="profile-confirm-password" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                Confirm New Password
              </label>
              <input
                id="profile-confirm-password"
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

        {/* Tab 3: Text Appearance Preferences */}
        {activeTab === 'preferences' && (
          <form
            id="preferences-tab-panel"
            role="tabpanel"
            aria-labelledby="tab-preferences"
            onSubmit={handleSavePreferences}
            style={{ display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}
          >
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                Typography Appearance
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
    </Dialog>
  );
};
