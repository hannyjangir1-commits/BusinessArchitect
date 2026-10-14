import React from 'react';
import {
  LayoutDashboard, Users, FolderKanban, Cpu, CheckCircle2,
  BarChart3, FileSpreadsheet, Activity, Database, ShieldAlert,
  Wrench, ShieldCheck, ClipboardList, Sliders, UserCircle2,
  ChevronLeft, ChevronRight, Sparkles, ExternalLink
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

export const AdminSidebar: React.FC<AdminSidebarProps> = ({
  currentPath,
  onNavigate,
  collapsed,
  onToggleCollapse,
  adminRole
}) => {
  const navGroups: NavGroup[] = [
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
      title: 'AI Operations',
      items: [
        { id: 'ai-ops', label: 'Gemini Operations', icon: Cpu, path: '/admin/ai-operations' },
        { id: 'ai-quality', label: 'AI Quality & Reliability', icon: CheckCircle2, path: '/admin/ai-quality' }
      ]
    },
    {
      title: 'Analytics & Reporting',
      items: [
        { id: 'analytics', label: 'Product Analytics', icon: BarChart3, path: '/admin/analytics' },
        { id: 'reports', label: 'Reports & Exports', icon: FileSpreadsheet, path: '/admin/reports' }
      ]
    },
    {
      title: 'Infrastructure',
      items: [
        { id: 'system-health', label: 'System Health', icon: Activity, path: '/admin/system-health' },
        { id: 'database', label: 'Database & Schema', icon: Database, path: '/admin/database' },
        { id: 'data-integrity', label: 'Data Integrity Scan', icon: ShieldAlert, path: '/admin/data-integrity' },
        { id: 'maintenance', label: 'Maintenance Center', icon: Wrench, path: '/admin/maintenance' }
      ]
    },
    {
      title: 'Security & Governance',
      items: [
        { id: 'security', label: 'Security Center', icon: ShieldCheck, path: '/admin/security' },
        { id: 'audit-logs', label: 'Audit Trail', icon: ClipboardList, path: '/admin/audit-logs' }
      ]
    },
    {
      title: 'Administration',
      items: [
        { id: 'configuration', label: 'Configuration Center', icon: Sliders, path: '/admin/configuration' },
        { id: 'account', label: 'Admin Account', icon: UserCircle2, path: '/admin/account' }
      ]
    }
  ];

  return (
    <aside
      style={{
        width: collapsed ? '72px' : '260px',
        minWidth: collapsed ? '72px' : '260px',
        transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        backgroundColor: '#0d121f',
        borderRight: '1px solid #1e293b',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        color: '#94a3b8',
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
          borderBottom: '1px solid #1e293b'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)'
            }}
          >
            <Sparkles size={18} />
          </div>
          {!collapsed && (
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ color: '#ffffff', fontWeight: 700, fontSize: '14px', letterSpacing: '0.02em' }}>
                ADMIN CONTROL
              </div>
              <div style={{ color: '#6366f1', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Level 3 Enterprise
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
            color: '#64748b',
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
                  color: '#475569',
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
                    background: isActive ? 'linear-gradient(90deg, rgba(99, 102, 241, 0.15), rgba(99, 102, 241, 0.05))' : 'transparent',
                    color: isActive ? '#ffffff' : '#94a3b8',
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '13px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                    marginBottom: '2px',
                    borderLeft: isActive ? '3px solid #6366f1' : '3px solid transparent'
                  }}
                  onMouseEnter={e => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = '#161f36';
                      e.currentTarget.style.color = '#cbd5e1';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#94a3b8';
                    }
                  }}
                >
                  <Icon size={18} style={{ color: isActive ? '#818cf8' : '#64748b', flexShrink: 0 }} />
                  {!collapsed && <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Return to Public Portal */}
      <div style={{ padding: '12px', borderTop: '1px solid #1e293b' }}>
        <button
          onClick={() => (window.location.href = '/')}
          title="Return to Business Architect App"
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '10px',
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid #334155',
            background: '#151c2e',
            color: '#cbd5e1',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          <ExternalLink size={14} style={{ color: '#818cf8' }} />
          {!collapsed && <span>User Application</span>}
        </button>
      </div>
    </aside>
  );
};
