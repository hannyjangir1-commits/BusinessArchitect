import React, { useState } from 'react';
import { User } from '../types';
import { UserCheck, Moon, Sun, Type, X, Check } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  user: User;
  onThemeChange: (theme: 'light' | 'dark') => void;
  currentTheme: 'light' | 'dark';
}

export const ProfileModal: React.FC<Props> = ({
  isOpen,
  onClose,
  user,
  onThemeChange,
  currentTheme
}) => {
  const [fullName, setFullName] = useState(() => localStorage.getItem('aba_fullname') || user.username);
  const [fontPref, setFontPref] = useState(() => localStorage.getItem('aba_font') || 'system');
  const [themePref, setThemePref] = useState<'light' | 'dark'>(currentTheme);
  const [savedSuccess, setSavedSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('aba_fullname', fullName);
    localStorage.setItem('aba_font', fontPref);
    localStorage.setItem('aba_theme', themePref);

    onThemeChange(themePref);

    // Apply font preference to body
    if (fontPref === 'mono') {
      document.body.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
    } else {
      document.body.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    }

    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
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
          maxWidth: 480,
          width: '100%',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-color)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
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
              <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                User Profile & Preferences
              </h3>
              <p style={{ fontSize: 12, color: '#64748b', margin: '2px 0 0 0' }}>
                Manage personal profile details, theme settings, and workspace preferences
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Username
            </label>
            <input
              type="text"
              value={user.username}
              disabled
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 6,
                border: '1px solid #e2e8f0',
                background: '#f8fafc',
                color: '#64748b',
                fontSize: 13
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Email Address
            </label>
            <input
              type="email"
              value={user.email}
              disabled
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 6,
                border: '1px solid #e2e8f0',
                background: '#f8fafc',
                color: '#64748b',
                fontSize: 13
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Display / Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Alex Morgan"
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 6,
                border: '1px solid #cbd5e1',
                fontSize: 13,
                outline: 'none'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
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
                  border: themePref === 'light' ? '2px solid #6366f1' : '1px solid #e2e8f0',
                  background: themePref === 'light' ? '#f5f3ff' : '#ffffff',
                  color: themePref === 'light' ? '#6366f1' : '#475569',
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
                  border: themePref === 'dark' ? '2px solid #6366f1' : '1px solid #e2e8f0',
                  background: themePref === 'dark' ? '#f5f3ff' : '#ffffff',
                  color: themePref === 'dark' ? '#6366f1' : '#475569',
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
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Typography Preference
            </label>
            <div style={{ display: 'flex', gap: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#334155', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="fontPref"
                  value="system"
                  checked={fontPref === 'system'}
                  onChange={() => setFontPref('system')}
                />
                <Type size={14} /> Modern Sans-Serif
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#334155', cursor: 'pointer' }}>
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
              {savedSuccess ? <><Check size={14} /> Saved!</> : 'Save Preferences'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
