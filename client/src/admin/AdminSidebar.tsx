import React from 'react';
import {
  LayoutDashboard, Users, FolderKanban, Cpu,
  UserCircle2, ChevronLeft, ChevronRight, Sparkles, ExternalLink
} from 'lucide-react';

interface AdminSidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  adminRole: string;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  path: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const ROLE_PERMISSIONS: Record<string, string[]> = {
  super_admin: [
    'view_dashboard', 'manage_users', 'manage_projects', 'view_ai_ops',
    'retry_ai_ops', 'view_analytics', 'view_system_health', 'view_database',
    'run_integrity_scan', 'execute_repair', 'view_security', 'revoke_sessions',
    'view_audit_logs', 'manage_configuration', 'manage_maintenance', 'export_reports'
  ],
  operations_admin: [
    'view_dashboard', 'manage_projects', 'view_ai_ops', 'retry_ai_ops',
    'view_analytics', 'view_system_health', 'view_database', 'run_integrity_scan',
    'execute_repair', 'view_security', 'revoke_sessions', 'view_audit_logs',
    'manage_maintenance', 'export_reports'
  ],
  security_admin: [
    'view_dashboard', 'view_security', 'revoke_sessions', 'view_audit_logs', 'export_reports'
  ],
  support_admin: [
    'view_dashboard', 'manage_users', 'manage_projects', 'view_ai_ops', 'view_system_health'
  ],
  auditor: [
    'view_dashboard', 'view_ai_ops', 'view_analytics', 'view_system_health', 'view_audit_logs', 'export_reports'
  ]
};

const ITEM_PERMISSIONS: Record<string, string> = {
  'dashboard': 'view_dashboard',
  'users': 'manage_users',
  'projects': 'manage_projects',
  'ai-ops': 'view_ai_ops',
  'account': 'view_account'
};

export const AdminSidebar: React.FC<AdminSidebarProps> = ({
  currentPath,
  onNavigate,
  collapsed,
  onToggleCollapse,
  adminRole
}) => {
  const allowedPerms = ROLE_PERMISSIONS[adminRole] || [];

  const rawNavGroups: NavGroup[] = [
    {
      title: 'Overview',
      items: [
        { id: 'dashboard', label: 'Admin Dashboard', icon: LayoutDashboard, path: '/admin' }
      ]
    },
    {
      title: 'Application Management',
      items: [
        { id: 'users', label: 'User Directory', icon: Users, path: '/admin/users' },
        { id: 'projects', label: 'Projects Console', icon: FolderKanban, path: '/admin/projects' }
      ]
    },
    {
      title: 'Generation Operations',
      items: [
        { id: 'ai-ops', label: 'Generation Activity & Quality', icon: Cpu, path: '/admin/ai-operations' }
      ]
    },
    {
      title: 'Administration',
      items: [
        { id: 'account', label: 'Admin Account', icon: UserCircle2, path: '/admin/account' }
      ]
    }
  ];

  const navGroups: NavGroup[] = rawNavGroups
    .map(group => ({
      ...group,
      items: group.items.filter(item => {
        const required = ITEM_PERMISSIONS[item.id];
        if (!required || required === 'view_account') return true;
        return allowedPerms.includes(required);
      })
    }))
    .filter(group => group.items.length > 0);

  return (
    <aside
      style={{
        width: collapsed ? '72px' : '260px',
        minWidth: collapsed ? '72px' : '260px',
        transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        backgroundColor: 'var(--sidebar-bg)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        color: 'var(--text-muted)',
        zIndex: 20
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '20px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          borderBottom: '1px solid var(--border-color)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              background: 'var(--bg-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-main)',
              boxShadow: '0 1px 3px rgb(69 60 55 / 0.1)'
            }}
          >
            <Sparkles size={18} />
          </div>
          {!collapsed && (
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ color: 'var(--text-main)', fontWeight: 700, fontSize: '14px', letterSpacing: '0.02em' }}>
                ADMIN CONTROL
              </div>
              <div style={{ color: 'var(--primary-text)', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Workspace administration
              </div>
            </div>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation Groups */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 8px' }}>
        {navGroups.map((group, gIdx) => (
          <div key={gIdx} style={{ marginBottom: '18px' }}>
            {!collapsed && (
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  color: 'var(--text-main)',
                  letterSpacing: '0.05em',
                  padding: '6px 12px',
                  marginBottom: '4px'
                }}
              >
                {group.title}
              </div>
            )}
            {group.items.map(item => {
              const Icon = item.icon;
              const isActive = currentPath === item.path || (item.path !== '/admin' && currentPath.startsWith(item.path));
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.path)}
                  title={collapsed ? item.label : undefined}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: collapsed ? '10px 0' : '9px 12px',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    borderRadius: '8px',
                    border: 'none',
                    background: isActive ? 'var(--bg-subtle)' : 'transparent',
                    color: isActive ? 'var(--primary-text)' : 'var(--primary-text)',
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '13px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                    marginBottom: '2px',
                    borderLeft: isActive ? '3px solid var(--primary-text)' : '3px solid transparent'
                  }}
                  onMouseEnter={e => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'var(--sidebar-hover)';
                      e.currentTarget.style.color = 'var(--text-muted)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = 'var(--text-muted)';
                    }
                  }}
                >
                  <Icon size={18} style={{ color: isActive ? 'var(--text-muted)' : 'var(--text-main)', flexShrink: 0 }} />
                  {!collapsed && <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Return to Public Portal */}
      <div style={{ padding: '12px', borderTop: '1px solid var(--border-color)' }}>
        <button
          onClick={() => (window.location.href = '/')}
          title="Return to Venture Atlas App"
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '10px',
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid var(--text-main)',
            background: 'var(--bg-card)',
            color: 'var(--text-muted)',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          <ExternalLink size={14} style={{ color: 'var(--text-muted)' }} />
          {!collapsed && <span>User Application</span>}
        </button>
      </div>
    </aside>
  );
};
