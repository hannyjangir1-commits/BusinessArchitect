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
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSelectUser = (userId: string) => {
    setSelectedUserId(userId);
  };

  const handleSelectProject = (projectId: string) => {
    setSelectedProjectId(projectId);
  };

  const renderContent = () => {
    // If a specific user detail is open
    if (selectedUserId) {
      return (
        <AdminUserDetailPage
          userId={selectedUserId}
          onBack={() => setSelectedUserId(null)}
          onSelectProject={(projId) => {
            setSelectedUserId(null);
            setSelectedProjectId(projId);
          }}
        />
      );
    }

    // If a specific project detail is open
    if (selectedProjectId) {
      return (
        <AdminProjectDetailPage
          projectId={selectedProjectId}
          onBack={() => setSelectedProjectId(null)}
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
        return <AdminDashboardPage onNavigate={navigate} />;
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
