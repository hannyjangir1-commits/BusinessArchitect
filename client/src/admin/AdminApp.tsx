import React, { useState, useEffect } from 'react';
import { AdminLayout } from './AdminLayout';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { AdminUserDetailPage } from './pages/AdminUserDetailPage';
import { AdminProjectsPage } from './pages/AdminProjectsPage';
import { AdminProjectDetailPage } from './pages/AdminProjectDetailPage';
import { AdminAIOperationsPage } from './pages/AdminAIOperationsPage';
import { AdminAccountPage } from './pages/AdminAccountPage';

interface AdminAppProps {
  adminUser: any;
  onLogout: () => void;
  initialPath?: string;
}

export const AdminApp: React.FC<AdminAppProps> = ({ adminUser, onLogout, initialPath = '/admin' }) => {
  const [currentPath, setCurrentPath] = useState<string>(initialPath);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // Sync browser URL bar without page reloads
  const navigate = (path: string) => {
    setCurrentPath(path);
    setSelectedUserId(null);
    setSelectedProjectId(null);
    window.history.pushState({}, '', path);
  };

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname || '/admin');
      setSelectedUserId(null);
      setSelectedProjectId(null);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSelectUser = (userId: string) => {
    navigate(`/admin/users/${encodeURIComponent(userId)}`);
  };

  const handleSelectProject = (projectId: string) => {
    navigate(`/admin/projects/${encodeURIComponent(projectId)}`);
  };

  const renderContent = () => {
    const routeUserId = currentPath.match(/^\/admin\/users\/([^/]+)$/)?.[1];
    const routeProjectId = currentPath.match(/^\/admin\/projects\/([^/]+)$/)?.[1];
    // If a specific user detail is open
    if (selectedUserId || routeUserId) {
      return (
        <AdminUserDetailPage
          userId={selectedUserId || decodeURIComponent(routeUserId!)}
          onBack={() => navigate('/admin/users')}
          onSelectProject={(projId) => {
            navigate(`/admin/projects/${encodeURIComponent(projId)}`);
          }}
        />
      );
    }

    // If a specific project detail is open
    if (selectedProjectId || routeProjectId) {
      return (
        <AdminProjectDetailPage
          projectId={selectedProjectId || decodeURIComponent(routeProjectId!)}
          onBack={() => navigate('/admin/projects')}
        />
      );
    }

    switch (currentPath) {
      case '/admin':
      case '/admin/dashboard':
        return <AdminDashboardPage onNavigate={navigate} />;
      case '/admin/users':
        return <AdminUsersPage onSelectUser={handleSelectUser} />;
      case '/admin/projects':
        return <AdminProjectsPage onSelectProject={handleSelectProject} />;
      case '/admin/ai-operations':
      case '/admin/ai-quality':
        return <AdminAIOperationsPage />;
      case '/admin/account':
        return <AdminAccountPage />;
      default:
        return <div className="card"><h1>This administration page is unavailable</h1><p>Choose an available area from the navigation.</p><button className="btn-secondary" onClick={() => navigate('/admin')}>Open dashboard</button></div>;
    }
  };

  return (
    <AdminLayout
      currentPath={currentPath}
      onNavigate={navigate}
      adminUser={adminUser}
      onLogout={onLogout}
    >
      {renderContent()}
    </AdminLayout>
  );
};
