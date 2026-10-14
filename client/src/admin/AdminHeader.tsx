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
    users: 'Users',
    projects: 'Projects',
    'ai-operations': 'Gemini Operations',
    'ai-quality': 'AI Quality',
    analytics: 'Analytics',
    reports: 'Reports & Exports',
    'system-health': 'System Health',
    database: 'Database & Schema',
    'data-integrity': 'Data Integrity',
    maintenance: 'Maintenance',
    security: 'Security Center',
    'audit-logs': 'Audit Logs',
    configuration: 'Configuration',
    account: 'Account'
  };

  const isHealthy = health?.status === 'healthy';

  return (
    <header
      style={{
        height: '64px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        flexShrink: 0,
        zIndex: 10
      }}
    >
      {/* Breadcrumb Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#64748b' }}>
        <Shield size={16} style={{ color: '#6366f1' }} />
        {segments.map((seg, idx) => {
          const isLast = idx === segments.length - 1;
          const label = breadcrumbLabels[seg] || seg;
          return (
            <React.Fragment key={idx}>
              {idx > 0 && <ChevronRight size={14} style={{ color: '#94a3b8' }} />}
              <span style={{ fontWeight: isLast ? 600 : 400, color: isLast ? '#0f172a' : '#64748b' }}>
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
            <span style={{ color: '#64748b', fontWeight: 400, fontSize: '11px' }}>
              ({health.latency_ms}ms)
            </span>
          )}
        </div>

        {/* Refresh button */}
        <button
          onClick={() => window.location.reload()}
          title="Reload operational metrics"
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            padding: '6px 8px',
            color: '#475569',
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
              background: '#f1f5f9',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '6px 12px',
              cursor: 'pointer',
              color: '#0f172a'
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                backgroundColor: '#6366f1',
                color: '#ffffff',
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
              <div style={{ fontSize: '10px', color: '#6366f1', fontWeight: 700, textTransform: 'uppercase' }}>
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
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
                padding: '6px',
                zIndex: 50
              }}
            >
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', marginBottom: '4px' }}>
                <div style={{ fontSize: '11px', color: '#64748b' }}>Signed in as</div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>{adminUser?.email || 'admin'}</div>
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
                  color: '#334155',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#f8fafc')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <KeyRound size={16} style={{ color: '#6366f1' }} />
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
                  color: '#334155',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#f8fafc')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <UserIcon size={16} style={{ color: '#6366f1' }} />
                <span>Account Profile</span>
              </button>

              <div style={{ borderTop: '1px solid #f1f5f9', margin: '4px 0' }} />

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
