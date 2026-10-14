import React, { useState, useEffect } from 'react';
import { User, Project, ModuleDetail, RoadmapTask, RoadmapSummary, CopilotMessage } from './types';
import { api } from './services/api';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage } from './pages/DashboardPage';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewModule } from './components/OverviewModule';
import { BMCModule } from './components/BMCModule';
import { TechStackModule } from './components/TechStackModule';
import { IdeaValidatorModule } from './components/IdeaValidatorModule';
import { MarketResearchModule } from './components/MarketResearchModule';
import { ExecutionRoadmapModule } from './components/ExecutionRoadmapModule';
import { DetailedRoadmapModule } from './components/DetailedRoadmapModule';
import { BlueprintCopilotModule } from './components/BlueprintCopilotModule';
import { NewProjectWizard } from './components/NewProjectWizard';
import { VersionConflictModal } from './components/VersionConflictModal';
import { AdminApp } from './admin/AdminApp';
import { AdminLoginPage } from './admin/pages/AdminLoginPage';
import { Loader2 } from 'lucide-react';
import './styles/index.css';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);

  // Admin Portal State
  const [isAdminRoute, setIsAdminRoute] = useState<boolean>(() => window.location.pathname.startsWith('/admin'));
  const [adminUser, setAdminUser] = useState<any | null>(null);
  const [adminAuthChecking, setAdminAuthChecking] = useState<boolean>(() => window.location.pathname.startsWith('/admin'));

  // Projects & Navigation
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [activeModule, setActiveModule] = useState<string>('execution_roadmap');
  const [isWizardOpen, setIsWizardOpen] = useState<boolean>(false);

  // Active Module State
  const [moduleDetail, setModuleDetail] = useState<ModuleDetail | null>(null);
  const [tasks, setTasks] = useState<RoadmapTask[]>([]);
  const [summary, setSummary] = useState<RoadmapSummary>({
    milestone_30_progress: 67,
    milestone_30_completed: 2,
    milestone_30_total: 3,
    milestone_60_progress: 50,
    milestone_60_completed: 1,
    milestone_60_total: 2,
    milestone_90_progress: 0,
    milestone_90_completed: 0,
    milestone_90_total: 3,
    total_tasks: 8,
    completed_tasks: 3,
    overall_progress: 62
  });
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [moduleLoading, setModuleLoading] = useState<boolean>(false);

  // 5-Version Conflict State
  const [conflictModalOpen, setConflictModalOpen] = useState<boolean>(false);
  const [conflictData, setConflictData] = useState<{
    moduleTitle: string;
    existingVersions: any[];
    pendingInstruction?: string;
  } | null>(null);

  // Dynamic Badges & Race-Condition Guard Refs
  const activeProjectIdRef = React.useRef<string | null>(null);
  const activeModuleTypeRef = React.useRef<string>('execution_roadmap');

  const [moduleBadges, setModuleBadges] = useState<Record<string, { version: string; isGenerated: boolean }>>({
    overview: { version: 'V1', isGenerated: true },
    bmc: { version: 'V1', isGenerated: false },
    tech_stack: { version: 'V1', isGenerated: false },
    idea_validator: { version: 'V1', isGenerated: false },
    market_research: { version: 'V1', isGenerated: false },
    execution_roadmap: { version: 'V1', isGenerated: false },
    detailed_roadmap: { version: 'V1', isGenerated: false },
    blueprint_copilot: { version: 'V1', isGenerated: false }
  });

  const updateBadgeForModule = (moduleType: string, detail: ModuleDetail | null) => {
    if (!detail) return;
    const vStr = detail.active_version_name || (detail.active_version_number ? `V${detail.active_version_number}` : 'V1');
    setModuleBadges(prev => ({
      ...prev,
      [moduleType]: {
        version: vStr,
        isGenerated: !!detail.data
      }
    }));
  };

  // 1. Initial Authentication Check
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const session = await api.auth.getMe();
        if (session && session.user) {
          setCurrentUser(session.user);
          loadProjects();
        }
      } catch {
        setCurrentUser(null);
      } finally {
        setAuthChecking(false);
      }
    };
    checkAuth();

    // Check Admin Authentication if on admin route
    const checkAdminAuth = async () => {
      if (window.location.pathname.startsWith('/admin')) {
        if (window.location.pathname === '/admin/login') {
          setAdminAuthChecking(false);
          return;
        }
        try {
          const res = await api.admin.auth.getMe();
          if (res && res.user) {
            setAdminUser(res.user);
          } else {
            setAdminUser(null);
          }
        } catch {
          setAdminUser(null);
        } finally {
          setAdminAuthChecking(false);
        }
      }
    };
    checkAdminAuth();

    const handleAuthExpired = () => {
      setCurrentUser(null);
      setCurrentProject(null);
    };
    window.addEventListener('auth:expired', handleAuthExpired);

    const handlePopState = () => {
      const onAdmin = window.location.pathname.startsWith('/admin');
      setIsAdminRoute(onAdmin);
      if (onAdmin) {
        checkAdminAuth();
      }
    };
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  const loadProjects = async () => {
    try {
      const projs = await api.projects.list();
      setProjects(projs);
    } catch (e) {
      console.error('Failed to load projects', e);
    }
  };

  // 2. Open Project & Restore Navigation Memory (Part 25)
  const handleOpenProject = async (projectId: string) => {
    activeProjectIdRef.current = projectId;
    // Clear stale state immediately
    setModuleDetail(null);
    setTasks([]);
    setCopilotMessages([]);

    try {
      const proj = await api.projects.get(projectId);
      if (activeProjectIdRef.current !== projectId) return; // Prevent late race condition
      setCurrentProject(proj);
      // Restore the project's saved navigation module
      const targetModule = proj.active_module || 'execution_roadmap';
      activeModuleTypeRef.current = targetModule;
      setActiveModule(targetModule);
      loadModuleContent(proj.id, targetModule);
    } catch (err: any) {
      alert(err.message || 'Failed to open project');
    }
  };

  // 3. Switch Module and Persist Per-Project Navigation Memory
  const handleSelectModule = async (moduleId: string) => {
    if (!currentProject) return;
    activeModuleTypeRef.current = moduleId;
    setActiveModule(moduleId);
    setModuleDetail(null); // Clear stale module data immediately
    loadModuleContent(currentProject.id, moduleId);

    // Save navigation memory to backend
    try {
      await api.projects.updateActiveModule(currentProject.id, moduleId);
      setCurrentProject(prev => prev ? { ...prev, active_module: moduleId } : null);
    } catch (e) {
      console.error('Failed to persist navigation memory', e);
    }
  };

  // 4. Load Content for Active Module
  const loadModuleContent = async (projectId: string, moduleType: string) => {
    setModuleLoading(true);
    try {
      if (['overview', 'bmc', 'tech_stack', 'idea_validator', 'market_research', 'execution_roadmap', 'detailed_roadmap'].includes(moduleType)) {
        try {
          const detail = await api.modules.get(projectId, moduleType);
          if (activeProjectIdRef.current === projectId && activeModuleTypeRef.current === moduleType) {
            setModuleDetail(detail);
            updateBadgeForModule(moduleType, detail);
          }
        } catch {
          if (activeProjectIdRef.current === projectId && activeModuleTypeRef.current === moduleType) {
            setModuleDetail(null);
          }
        }
      }

      if (['execution_roadmap', 'detailed_roadmap'].includes(moduleType)) {
        const taskList = await api.tasks.list(projectId);
        if (activeProjectIdRef.current === projectId) {
          setTasks(taskList);
          try {
            const sum = await api.tasks.getSummary(projectId);
            setSummary(sum);
            setModuleBadges(prev => ({
              ...prev,
              execution_roadmap: { ...prev.execution_roadmap, isGenerated: taskList.length > 0 },
              detailed_roadmap: { ...prev.detailed_roadmap, isGenerated: taskList.length > 0 }
            }));
          } catch {
            // Fallback calculation
          }
        }
      }

      if (moduleType === 'blueprint_copilot') {
        const history = await api.copilot.getHistory(projectId);
        if (activeProjectIdRef.current === projectId) {
          setCopilotMessages(history);
        }
      }
    } catch (err) {
      console.error('Error loading module content', err);
    } finally {
      if (activeProjectIdRef.current === projectId) {
        setModuleLoading(false);
      }
    }
  };

  // 5. Generate Module via Gemini
  const handleGenerateModule = async (moduleType: string) => {
    if (!currentProject) return;
    setModuleLoading(true);
    try {
      const updated = await api.modules.generate(currentProject.id, moduleType);
      setModuleDetail(updated);
      updateBadgeForModule(moduleType, updated);

      if (['execution_roadmap', 'detailed_roadmap'].includes(moduleType)) {
        const taskList = await api.tasks.list(currentProject.id);
        setTasks(taskList);
        const sum = await api.tasks.getSummary(currentProject.id);
        setSummary(sum);
        setModuleBadges(prev => ({
          ...prev,
          execution_roadmap: { ...prev.execution_roadmap, isGenerated: taskList.length > 0 },
          detailed_roadmap: { ...prev.detailed_roadmap, isGenerated: taskList.length > 0 }
        }));
      }
    } catch (err: any) {
      alert(err.message || 'Gemini generation failed');
    } finally {
      setModuleLoading(false);
    }
  };

  // 6. Section AI Modification Chat with 5-Version Limit Handling
  const handleModifyModule = async (instruction: string) => {
    if (!currentProject) return;
    setModuleLoading(true);
    try {
      const updated = await api.modules.modify(currentProject.id, activeModule, instruction);
      setModuleDetail(updated);
      updateBadgeForModule(activeModule, updated);

      if (['execution_roadmap', 'detailed_roadmap'].includes(activeModule)) {
        const taskList = await api.tasks.list(currentProject.id);
        setTasks(taskList);
        const sum = await api.tasks.getSummary(currentProject.id);
        setSummary(sum);
      }
    } catch (err: any) {
      if (err.status === 409 && err.data?.error === 'VERSION_LIMIT_EXCEEDED') {
        // Enforce 5-version limit explicitly: prompt conflict resolution modal
        setConflictData({
          moduleTitle: activeModule.replace('_', ' ').toUpperCase(),
          existingVersions: err.data.existing_versions || moduleDetail?.versions || [],
          pendingInstruction: instruction
        });
        setConflictModalOpen(true);
      } else {
        alert(err.message || 'AI modification failed');
      }
    } finally {
      setModuleLoading(false);
    }
  };

  // 7. Resolve 5-Version Conflict
  const handleResolveReplace = async (replaceVersionId: string) => {
    if (!currentProject || !conflictData) return;
    setModuleLoading(true);
    try {
      // Execute the pending AI modification on the selected version slot
      const updated = await api.modules.resolveConflict(
        currentProject.id,
        activeModule,
        replaceVersionId,
        conflictData.pendingInstruction,
        undefined,
        `V${replaceVersionId.slice(-2)} (Updated)`,
        conflictData.pendingInstruction ? `Applied: ${conflictData.pendingInstruction.slice(0, 40)}` : undefined
      );
      setModuleDetail(updated);
      setConflictModalOpen(false);
      setConflictData(null);

      if (['execution_roadmap', 'detailed_roadmap'].includes(activeModule)) {
        const taskList = await api.tasks.list(currentProject.id);
        setTasks(taskList);
        const sum = await api.tasks.getSummary(currentProject.id);
        setSummary(sum);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to replace version');
    } finally {
      setModuleLoading(false);
    }
  };

  // 8. Version Management Actions
  const handleRenameVersion = async (newName: string) => {
    if (!currentProject || !moduleDetail?.active_version_id) return;
    try {
      await api.modules.renameVersion(currentProject.id, activeModule, moduleDetail.active_version_id, newName);
      loadModuleContent(currentProject.id, activeModule);
    } catch (err: any) {
      alert(err.message || 'Failed to rename version');
    }
  };

  const handleDeleteVersion = async (versionId: string) => {
    if (!currentProject) return;
    try {
      await api.modules.deleteVersion(currentProject.id, activeModule, versionId);
      loadModuleContent(currentProject.id, activeModule);
    } catch (err: any) {
      alert(err.message || 'Failed to delete version');
    }
  };

  const handleRestoreVersion = async (versionId: string) => {
    if (!currentProject) return;
    try {
      const restored = await api.modules.restoreVersion(currentProject.id, activeModule, versionId);
      setModuleDetail(restored);
    } catch (err: any) {
      if (err.status === 409) {
        alert('Cannot restore into a new version slot: Maximum 5 saved versions reached. Please delete an older version first.');
      } else {
        alert(err.message || 'Failed to restore version');
      }
    }
  };

  // 9. Roadmap Task Actions
  const handleAddTask = async (taskData: any) => {
    if (!currentProject) return;
    const created = await api.tasks.create(currentProject.id, taskData);
    setTasks(prev => [...prev, created]);
    const sum = await api.tasks.getSummary(currentProject.id);
    setSummary(sum);
  };

  const handleUpdateTask = async (taskId: string, taskData: any) => {
    if (!currentProject) return;
    const updated = await api.tasks.update(currentProject.id, taskId, taskData);
    setTasks(prev => prev.map(t => t.id === taskId ? updated : t));
    const sum = await api.tasks.getSummary(currentProject.id);
    setSummary(sum);
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!currentProject) return;
    await api.tasks.delete(currentProject.id, taskId);
    setTasks(prev => prev.filter(t => t.id !== taskId));
    const sum = await api.tasks.getSummary(currentProject.id);
    setSummary(sum);
  };

  // 10. Project Update / Fork
  const handleUpdateProject = async (data: any, createCopy: boolean) => {
    if (!currentProject) return;
    try {
      const updated = await api.projects.update(currentProject.id, { ...data, create_copy: createCopy });
      if (createCopy) {
        await loadProjects();
        setCurrentProject(updated);
      } else {
        setCurrentProject(updated);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to update project');
    }
  };

  // 11. Project Creation Wizard
  const handleProjectCreated = async (payload: any) => {
    try {
      const newProj = await api.projects.create(payload);
      setIsWizardOpen(false);
      await loadProjects();
      handleOpenProject(newProj.id);
    } catch (err: any) {
      alert(err.message || 'Failed to create project');
    }
  };

  // 12. Delete Project
  const handleDeleteProject = async (projectId: string) => {
    try {
      await api.projects.delete(projectId);
      await loadProjects();
      if (currentProject?.id === projectId) {
        setCurrentProject(null);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete project');
    }
  };

  // Admin Portal Routing
  if (isAdminRoute) {
    if (adminAuthChecking) {
      return (
        <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0f1d', color: '#ffffff', gap: 12 }}>
          <Loader2 size={24} className="animate-spin" color="#6366f1" />
          <span>Authenticating Admin Control Center...</span>
        </div>
      );
    }

    if (!adminUser || window.location.pathname === '/admin/login') {
      return (
        <AdminLoginPage
          onLoginSuccess={(session) => {
            setAdminUser(session.user);
            window.history.pushState({}, '', '/admin');
            setIsAdminRoute(true);
          }}
        />
      );
    }

    return (
      <AdminApp
        adminUser={adminUser}
        initialPath={window.location.pathname}
        onLogout={async () => {
          try {
            await api.admin.auth.logout();
          } catch {}
          setAdminUser(null);
          window.history.pushState({}, '', '/admin/login');
        }}
      />
    );
  }

  // Loading Screen
  if (authChecking) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d121f', color: '#ffffff', gap: 12 }}>
        <Loader2 size={24} className="animate-spin" color="#6366f1" />
        <span>Loading AI Business Architect...</span>
      </div>
    );
  }

  // If not logged in -> Landing Page
  if (!currentUser) {
    return <LandingPage onAuthenticated={(sess) => { setCurrentUser(sess.user); loadProjects(); }} />;
  }

  // If no project selected -> Dashboard
  if (!currentProject) {
    return (
      <>
        <DashboardPage
          user={currentUser}
          projects={projects}
          onOpenProject={handleOpenProject}
          onCreateNewProject={() => setIsWizardOpen(true)}
          onDeleteProject={handleDeleteProject}
          onLogout={async () => { await api.auth.logout(); setCurrentUser(null); }}
        />
        {isWizardOpen && (
          <NewProjectWizard
            onProjectCreated={handleProjectCreated}
            onCancel={() => setIsWizardOpen(false)}
          />
        )}
      </>
    );
  }

  // Main Application Workspace
  return (
    <div className="app-layout">
      {/* Sidebar with Navigation Memory */}
      <Sidebar
        currentProject={currentProject}
        activeModule={activeModule}
        onSelectModule={handleSelectModule}
        onBackToDashboard={() => setCurrentProject(null)}
        onCreateNewProject={() => setIsWizardOpen(true)}
        onExportFullPdf={() => api.exports.downloadFullProjectPdf(currentProject.id, currentProject.name)}
        moduleVersionBadges={moduleBadges}
      />

      <div className="main-wrapper">
        {/* Top Header */}
        <Header
          project={currentProject}
          user={currentUser}
          onLogout={async () => { await api.auth.logout(); setCurrentUser(null); setCurrentProject(null); }}
          onEditProject={() => handleSelectModule('overview')}
        />

        {/* Scrollable Workspace Body */}
        <div className="workspace-scroll-area">
          {activeModule === 'overview' && (
            <OverviewModule
              project={currentProject}
              onUpdateProject={handleUpdateProject}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'bmc' && (
            <BMCModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('bmc')}
              onModify={handleModifyModule}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'bmc', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'tech_stack' && (
            <TechStackModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('tech_stack')}
              onModify={handleModifyModule}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'tech_stack', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'idea_validator' && (
            <IdeaValidatorModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('idea_validator')}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'idea_validator', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'market_research' && (
            <MarketResearchModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('market_research')}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'market_research', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'execution_roadmap' && (
            <ExecutionRoadmapModule
              project={currentProject}
              moduleDetail={moduleDetail}
              tasks={tasks}
              summary={summary}
              onGenerate={() => handleGenerateModule('execution_roadmap')}
              onModify={handleModifyModule}
              onAddTask={handleAddTask}
              onUpdateTask={handleUpdateTask}
              onDeleteTask={handleDeleteTask}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'execution_roadmap', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'detailed_roadmap' && (
            <DetailedRoadmapModule
              project={currentProject}
              moduleDetail={moduleDetail}
              tasks={tasks}
              onUpdateStatus={(taskId, newStatus) => handleUpdateTask(taskId, { status: newStatus })}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'detailed_roadmap', currentProject.name)}
              isLoading={moduleLoading}
            />
          )}

          {activeModule === 'blueprint_copilot' && (
            <BlueprintCopilotModule
              project={currentProject}
              messages={copilotMessages}
              onSendMessage={async (msg) => {
                if (!currentProject) return;
                setModuleLoading(true);
                try {
                  const reply = await api.copilot.sendMessage(currentProject.id, msg);
                  setCopilotMessages(prev => [...prev, reply]);
                } catch (e: any) {
                  alert(e.message || 'Copilot error');
                } finally {
                  setModuleLoading(false);
                }
              }}
              isLoading={moduleLoading}
            />
          )}
        </div>
      </div>

      {/* New Project Wizard Modal */}
      {isWizardOpen && (
        <NewProjectWizard
          onProjectCreated={handleProjectCreated}
          onCancel={() => setIsWizardOpen(false)}
        />
      )}

      {/* 5-Version Conflict Resolution Modal */}
      {conflictModalOpen && conflictData && (
        <VersionConflictModal
          moduleTitle={conflictData.moduleTitle}
          existingVersions={conflictData.existingVersions}
          pendingInstruction={conflictData.pendingInstruction}
          onResolveReplace={handleResolveReplace}
          onCancel={() => setConflictModalOpen(false)}
          isLoading={moduleLoading}
        />
      )}
    </div>
  );
};
export default App;
