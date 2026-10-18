import React, { useState } from 'react';
import {
  Shield, KeyRound, LogOut, RefreshCw, ChevronRight,
  User as UserIcon
} from 'lucide-react';

interface AdminHeaderProps {
  currentPath: string;
  adminUser: any;
  health: { status: string; latency_ms: number } | null;
  onLogout: () => void;
  onChangePassword: () => void;
  onNavigate: (path: string) => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({
  currentPath,
  adminUser,
  health,
  onLogout,
  onChangePassword,
  onNavigate
}) => {
  const [profileMenuOpen, setProfileMenuOpen] = useState<boolean>(false);

  // Format breadcrumb segments
  const segments = currentPath.split('/').filter(Boolean);
  const breadcrumbLabels: Record<string, string> = {
    admin: 'Admin Center',
    users: 'Users Directory',
    projects: 'Projects Console',
    'ai-operations': 'Generation Activity & Quality',
    account: 'Admin Account'
  };

  const isHealthy = health?.status === 'healthy';

  return (
    <header
      style={{
        height: '64px',
        backgroundColor: 'var(--bg-card)',
        borderBottom: '1px solid #dfe2d6',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        flexShrink: 0,
        zIndex: 10
      }}
    >
      {/* Breadcrumb Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
        <Shield size={16} style={{ color: '#6d855f' }} />
        {segments.map((seg, idx) => {
          const isLast = idx === segments.length - 1;
          const label = breadcrumbLabels[seg] || seg;
          return (
            <React.Fragment key={idx}>
              {idx > 0 && <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
              <span style={{ fontWeight: isLast ? 600 : 400, color: isLast ? '#626b5f' : '#687164' }}>
                {label}
              </span>
            </React.Fragment>
          );
        })}
      </div>

      {/* Right controls: Health status, profile & actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* System Health Status Indicator */}
        <div
          title={`Database Latency: ${health?.latency_ms ?? 0}ms`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: isHealthy ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${isHealthy ? '#bbf7d0' : '#fecaca'}`,
            padding: '5px 12px',
            borderRadius: '9999px',
            fontSize: '12px',
            fontWeight: 600,
            color: isHealthy ? '#166534' : '#991b1b'
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isHealthy ? '#22c55e' : '#ef4444',
              display: 'inline-block',
              boxShadow: isHealthy ? '0 0 6px rgba(34, 197, 94, 0.6)' : 'none'
            }}
          />
          <span>{isHealthy ? 'Operational' : 'Degraded'}</span>
          {health?.latency_ms !== undefined && health.latency_ms >= 0 && (
            <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '11px' }}>
              ({health.latency_ms}ms)
            </span>
          )}
        </div>

        {/* Refresh button */}
        <button
          onClick={() => window.location.reload()}
          title="Reload operational metrics"
          style={{
            background: '#f7f6ef',
            border: '1px solid #dfe2d6',
            borderRadius: '6px',
            padding: '6px 8px',
            color: 'var(--text-main)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <RefreshCw size={15} />
        </button>

        {/* Admin Profile Dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setProfileMenuOpen(prev => !prev)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: '#f0f1e9',
              border: '1px solid #dfe2d6',
              borderRadius: '8px',
              padding: '6px 12px',
              cursor: 'pointer',
              color: 'var(--text-main)'
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                backgroundColor: '#6d855f',
                color: 'var(--text-main)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700
              }}
            >
              {adminUser?.username ? adminUser.username.slice(0, 2).toUpperCase() : 'AD'}
            </div>
            <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>{adminUser?.username || 'Admin'}</div>
              <div style={{ fontSize: '10px', color: '#6d855f', fontWeight: 700, textTransform: 'uppercase' }}>
                {adminUser?.role ? adminUser.role.replace('_', ' ') : 'Super Admin'}
              </div>
            </div>
          </button>

          {profileMenuOpen && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: '46px',
                width: '220px',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid #dfe2d6',
                borderRadius: '8px',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
                padding: '6px',
                zIndex: 50
              }}
            >
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f1e9', marginBottom: '4px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Signed in as</div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>{adminUser?.email || 'admin'}</div>
              </div>

              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  onChangePassword();
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#f7f6ef')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <KeyRound size={16} style={{ color: '#6d855f' }} />
                <span>Change Password</span>
              </button>

              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  onNavigate('/admin/account');
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#f7f6ef')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <UserIcon size={16} style={{ color: '#6d855f' }} />
                <span>Account Profile</span>
              </button>

              <div style={{ borderTop: '1px solid #f0f1e9', margin: '4px 0' }} />

              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  onLogout();
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'transparent',
                  color: '#ef4444',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#fef2f2')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <LogOut size={16} />
                <span>Log out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
