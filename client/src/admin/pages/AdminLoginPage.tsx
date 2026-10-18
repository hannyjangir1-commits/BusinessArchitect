import React, { useState } from 'react';
import { api } from '../../services/api';
import { Shield, Lock, User, Eye, EyeOff, Loader2, AlertCircle, ArrowLeft } from 'lucide-react';

interface AdminLoginPageProps {
  onLoginSuccess: (adminSession: any) => void;
}

export const AdminLoginPage: React.FC<AdminLoginPageProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please provide both administrator username and password');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const session = await api.admin.auth.login(username.trim(), password);
      onLoginSuccess(session);
    } catch (err: any) {
      // Safe generic error handling
      if (err.message && err.message.includes('429')) {
        setError('Too many login attempts. Please wait 60 seconds before trying again.');
      } else {
        setError(err.message || 'Invalid administrator credentials');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--bg-workspace)',
        backgroundImage: 'radial-gradient(circle at 50% 20%, rgba(109, 133, 95, 0.12), transparent 70%)',
        padding: '20px',
        fontFamily: 'var(--font-family)'
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '420px',
          backgroundColor: 'var(--bg-workspace)',
          borderRadius: '16px',
          border: '1px solid #e7e9df',
          boxShadow: '0 14px 36px -18px rgba(70, 78, 63, 0.2)',
          overflow: 'hidden'
        }}
      >
        {/* Top Header Card */}
        <div
          style={{
            padding: '32px 32px 24px',
            textAlign: 'center',
            borderBottom: '1px solid #e7e9df'
          }}
        >
          <div
            style={{
              width: '54px',
              height: '54px',
              margin: '0 auto 16px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, #6d855f 0%, #5d7550 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-main)',
              boxShadow: '0 0 20px rgba(109, 133, 95, 0.4)'
            }}
          >
            <Shield size={28} />
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 6px' }}>
            Enterprise Admin Portal
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Venture Atlas — Control Center
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ padding: '28px 32px 32px' }}>
          {error && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                padding: '12px 14px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: '#a94f43',
                fontSize: '13px'
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <div style={{ marginBottom: '18px' }}>
            <label
              htmlFor="admin-username"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}
            >
              Administrator Username
            </label>
            <div style={{ position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <User size={16} />
              </div>
              <input
                id="admin-username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter administrator username"
                style={{
                  width: '100%',
                  padding: '10px 12px 10px 38px',
                  backgroundColor: 'var(--bg-subtle)',
                  border: '1px solid #626b5f',
                  borderRadius: '8px',
                  color: 'var(--text-main)',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'border-color 0.15s'
                }}
                onFocus={e => (e.target.style.borderColor = '#6d855f')}
                onBlur={e => (e.target.style.borderColor = 'var(--text-main)')}
              />
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label
              htmlFor="admin-password"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}
            >
              Master Password
            </label>
            <div style={{ position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <Lock size={16} />
              </div>
              <input
                id="admin-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter password"
                style={{
                  width: '100%',
                  padding: '10px 40px 10px 38px',
                  backgroundColor: 'var(--bg-subtle)',
                  border: '1px solid #626b5f',
                  borderRadius: '8px',
                  color: 'var(--text-main)',
                  fontSize: '14px',
                  outline: 'none',
                  transition: 'border-color 0.15s'
                }}
                onFocus={e => (e.target.style.borderColor = '#6d855f')}
                onBlur={e => (e.target.style.borderColor = 'var(--text-main)')}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer'
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              backgroundColor: '#6d855f',
              color: 'var(--text-main)',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 12px rgba(109, 133, 95, 0.3)',
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={e => {
              if (!loading) e.currentTarget.style.backgroundColor = '#5d7550';
            }}
            onMouseLeave={e => {
              if (!loading) e.currentTarget.style.backgroundColor = '#6d855f';
            }}
          >
            {loading ? (
              <>
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>Sign In to Admin Center</span>
            )}
          </button>

          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <button
              type="button"
              onClick={() => (window.location.href = '/')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '12px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <ArrowLeft size={12} />
              <span>Back to Public Workspace</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
