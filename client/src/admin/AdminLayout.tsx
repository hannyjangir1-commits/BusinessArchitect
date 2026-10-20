import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import { AdminChangePasswordModal } from './AdminChangePasswordModal';

interface AdminLayoutProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  children: React.ReactNode;
  adminUser: any;
  onLogout: () => void;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({
  currentPath,
  onNavigate,
  children,
  adminUser,
  onLogout
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [systemHealth, setSystemHealth] = useState<{ status: string; latency_ms: number } | null>(null);
  const [passwordModalOpen, setPasswordModalOpen] = useState<boolean>(false);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const h = await api.admin.system.getHealth();
        setSystemHealth({
          status: h.status,
          latency_ms: h.database_latency_ms
        });
      } catch {
        setSystemHealth({ status: 'unhealthy', latency_ms: -1 });
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // 30s background heartbeat
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="admin-shell" style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', backgroundColor: 'var(--bg-subtle)', fontFamily: 'var(--font-family)' }}>
      {/* Sidebar */}
      <AdminSidebar
        currentPath={currentPath}
        onNavigate={onNavigate}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        adminRole={adminUser?.role || 'user'}
      />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', backgroundColor: 'var(--bg-subtle)' }}>
        {/* Top Header */}
        <AdminHeader
          currentPath={currentPath}
          adminUser={adminUser}
          health={systemHealth}
          onLogout={onLogout}
          onChangePassword={() => setPasswordModalOpen(true)}
          onNavigate={onNavigate}
        />

        {/* Scrollable Content Viewport */}
        <main className="admin-content" style={{ flex: 1, overflowY: 'auto', padding: '28px 36px', position: 'relative' }}>
          {children}
        </main>
      </div>

      {/* Password Change Modal */}
      {passwordModalOpen && (
        <AdminChangePasswordModal
          onClose={() => setPasswordModalOpen(false)}
          onSuccess={() => {
            setPasswordModalOpen(false);
            alert('Password changed successfully.');
          }}
        />
      )}
    </div>
  );
};
