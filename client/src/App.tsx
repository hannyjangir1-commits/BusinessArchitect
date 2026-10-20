import React, { useState, useEffect } from 'react';
import { User, Project, ModuleDetail, RoadmapTask, RoadmapSummary, CopilotMessage, RoadmapPlanningInputs, TechStackPlanningInputs } from './types';
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
import { BlueprintCopilotModule } from './components/BlueprintCopilotModule';
import { NewProjectWizard } from './components/NewProjectWizard';
import { VersionConflictModal } from './components/VersionConflictModal';
import { AdminApp } from './admin/AdminApp';
import { AdminLoginPage } from './admin/pages/AdminLoginPage';
import { Loader2, AlertCircle, X } from 'lucide-react';
import './styles/index.css';

const MODULE_TYPES = new Set(['overview', 'bmc', 'tech_stack', 'idea_validator', 'market_research', 'execution_roadmap', 'blueprint_copilot']);
const normalizeModuleType = (moduleType: string) => {
  const canonical = moduleType === 'detailed_roadmap' ? 'execution_roadmap' : moduleType;
  return MODULE_TYPES.has(canonical) ? canonical : 'overview';
};
const EMPTY_SUMMARY: RoadmapSummary = {
  milestone_30_progress: 0, milestone_30_completed: 0, milestone_30_total: 0,
  milestone_60_progress: 0, milestone_60_completed: 0, milestone_60_total: 0,
  milestone_90_progress: 0, milestone_90_completed: 0, milestone_90_total: 0,
  total_tasks: 0, completed_tasks: 0, overall_progress: 0
};

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
  const [summary, setSummary] = useState<RoadmapSummary>(EMPTY_SUMMARY);
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [moduleLoading, setModuleLoading] = useState<boolean>(false);
  const [moduleError, setModuleError] = useState<string | null>(null);
  const navigationRef = React.useRef(0);
  const sessionEpochRef = React.useRef(0);
  const mutationKeysRef = React.useRef(new Set<string>());

  // 5-Version Conflict State
  const [conflictModalOpen, setConflictModalOpen] = useState<boolean>(false);
  const [conflictData, setConflictData] = useState<{
    projectId: string;
    moduleType: string;
    moduleTitle: string;
    existingVersions: any[];
    pendingInstruction?: string;
  } | null>(null);

  // Readiness Validation and Operation Progress State
  const [readinessError, setReadinessError] = useState<{
    moduleType: string;
    message: string;
    missingFields: string[];
    reasons: string[];
  } | null>(null);

  // Module-Scoped Generation Progress: keyed by `${projectId}:${moduleType}`
  const [generatingProgress, setGeneratingProgress] = useState<Record<string, {
    stageText: string;
    progressPercent: number;
  }>>({});

  const generationTimersRef = React.useRef<Record<string, any>>({});

  // Cleanup all timers on unmount
  useEffect(() => {
    return () => {
      Object.values(generationTimersRef.current).forEach(t => clearInterval(t));
      generationTimersRef.current = {};
    };
  }, []);

  // Dynamic Badges & Race-Condition Guard Refs
  const activeProjectIdRef = React.useRef<string | null>(null);
  const activeModuleTypeRef = React.useRef<string>('execution_roadmap');

  const isViewing = (projectId: string, moduleType?: string, navigation?: number) =>
    activeProjectIdRef.current === projectId &&
    (!moduleType || activeModuleTypeRef.current === moduleType) &&
    (navigation === undefined || navigationRef.current === navigation);

  const clearWorkspace = () => {
    activeProjectIdRef.current = null;
    navigationRef.current++;
    setCurrentProject(null);
    setModuleDetail(null);
    setTasks([]);
    setSummary(EMPTY_SUMMARY);
    setCopilotMessages([]);
    setReadinessError(null);
    setModuleError(null);
    setConflictModalOpen(false);
    setConflictData(null);
    setModuleLoading(false);
  };

  const clearSession = () => {
    sessionEpochRef.current++;
    clearWorkspace();
    setCurrentUser(null);
    setAdminUser(null);
    setProjects([]);
    setIsWizardOpen(false);
    Object.values(generationTimersRef.current).forEach(timer => clearInterval(timer));
    generationTimersRef.current = {};
    setGeneratingProgress({});
    mutationKeysRef.current.clear();
    document.body.style.removeProperty('font-family');
  };

  const logout = async () => {
    await api.auth.logout();
    clearSession();
    window.history.replaceState({}, '', '/');
  };

  const [moduleBadges, setModuleBadges] = useState<Record<string, { version: string; isGenerated: boolean }>>({
    overview: { version: 'V1', isGenerated: true },
    bmc: { version: 'V1', isGenerated: false },
    tech_stack: { version: 'V1', isGenerated: false },
    idea_validator: { version: 'V1', isGenerated: false },
    market_research: { version: 'V1', isGenerated: false },
    execution_roadmap: { version: 'V1', isGenerated: false },
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

  const loadProjects = React.useCallback(async () => {
    try {
      const epoch = sessionEpochRef.current;
      const projs = await api.projects.list();
      if (sessionEpochRef.current === epoch) setProjects(projs);
    } catch (e) {
      console.error('Failed to load projects', e);
    }
  }, []);

  // 1. Initial Authentication Check
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const session = await api.auth.getMe();
        if (session && session.user) {
          setCurrentUser(session.user);
          loadProjects();
          const route = new URLSearchParams(window.location.search);
          const projectId = route.get("project");
          if (projectId && !window.location.pathname.startsWith("/admin")) await handleOpenProject(projectId, route.get("module") || undefined, false);
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

    const handleAuthExpired = () => { clearSession(); };
    window.addEventListener('auth:expired', handleAuthExpired);

    const handlePopState = () => {
      const onAdmin = window.location.pathname.startsWith('/admin');
      setIsAdminRoute(onAdmin);
      if (onAdmin) {
        checkAdminAuth();
      } else {
        const route = new URLSearchParams(window.location.search);
        const projectId = route.get('project');
        if (projectId) void handleOpenProject(projectId, route.get('module') || undefined, false);
        else clearWorkspace();
      }
    };
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
      window.removeEventListener('popstate', handlePopState);
    };
  }, [loadProjects]);

  // 2. Open Project & Restore Navigation Memory (Part 25 & F-16)
  const handleOpenProject = async (projectId: string, targetModuleOverride?: string, writeHistory = true) => {
    clearWorkspace();
    activeProjectIdRef.current = projectId;
    // Clear stale state immediately
    setModuleDetail(null);
    setTasks([]);
    setCopilotMessages([]);

    try {
      const proj = await api.projects.get(projectId);
      if (activeProjectIdRef.current !== projectId) return; // Prevent late race condition
      setCurrentProject(proj);

      // Initialize module badges strictly scoped to this project
      const genModules = new Set(proj.generated_modules || []);
      setModuleBadges({
        overview: { version: 'V1', isGenerated: true },
        bmc: { version: 'V1', isGenerated: genModules.has('bmc') },
        tech_stack: { version: 'V1', isGenerated: genModules.has('tech_stack') },
        idea_validator: { version: 'V1', isGenerated: genModules.has('idea_validator') },
        market_research: { version: 'V1', isGenerated: genModules.has('market_research') },
        execution_roadmap: { version: 'V1', isGenerated: genModules.has('execution_roadmap') },
        blueprint_copilot: { version: 'V1', isGenerated: false }
      });

      // Restore the project's saved navigation module or use shortcut override (F-16)
      const targetModule = normalizeModuleType(targetModuleOverride || proj.active_module || 'execution_roadmap');
      activeModuleTypeRef.current = targetModule;
      setActiveModule(targetModule);
      if (writeHistory) window.history.pushState({}, '', `/?project=${encodeURIComponent(proj.id)}&module=${encodeURIComponent(targetModule)}`);
      loadModuleContent(proj.id, targetModule);

      if (targetModuleOverride && targetModule !== proj.active_module) {
        api.projects.updateActiveModule(proj.id, targetModule).catch(console.error);
      }
    } catch (err: any) {
      if (isViewing(projectId)) { clearWorkspace(); alert(err.message || 'Failed to open project'); }
    }
  };

  // 3. Switch Module and Persist Per-Project Navigation Memory
  const handleSelectModule = async (moduleId: string) => {
    if (!currentProject) return;
    const canonicalModuleId = normalizeModuleType(moduleId);
    activeModuleTypeRef.current = canonicalModuleId;
    setActiveModule(canonicalModuleId);
    window.history.pushState({}, '', `/?project=${encodeURIComponent(currentProject.id)}&module=${encodeURIComponent(canonicalModuleId)}`);
    setModuleDetail(null); // Clear stale module data immediately
    setReadinessError(null);
    setConflictModalOpen(false);
    setConflictData(null);
    loadModuleContent(currentProject.id, canonicalModuleId);

    // Save navigation memory to backend
    try {
      await api.projects.updateActiveModule(currentProject.id, canonicalModuleId);
      setCurrentProject(prev => prev?.id === currentProject.id && activeModuleTypeRef.current === canonicalModuleId ? { ...prev, active_module: canonicalModuleId } : prev);
    } catch (e) {
      console.error('Failed to persist navigation memory', e);
    }
  };

  // Keep every response scoped to the navigation that requested it.
  const loadModuleContent = async (projectId: string, moduleType: string) => {
    moduleType = normalizeModuleType(moduleType);
    const navigation = ++navigationRef.current;
    const viewing = () => isViewing(projectId, moduleType, navigation);
    setModuleLoading(true);
    setModuleError(null);
    try {
      if (!['overview', 'blueprint_copilot'].includes(moduleType)) {
        const detail = await api.modules.get(projectId, moduleType);
        if (!viewing()) return;
        setModuleDetail(detail);
        updateBadgeForModule(moduleType, detail);
      }
      if (moduleType === 'execution_roadmap') {
        const [taskList, sum] = await Promise.all([api.tasks.list(projectId), api.tasks.getSummary(projectId)]);
        if (!viewing()) return;
        setTasks(taskList);
        setSummary(sum);
      }
      if (moduleType === 'blueprint_copilot') {
        const history = await api.copilot.getHistory(projectId);
        if (viewing()) setCopilotMessages(history);
      }
    } catch (error: any) {
      if (viewing()) setModuleError(error.message || 'Could not load this section. Please retry.');
    } finally {
      if (viewing()) setModuleLoading(false);
    }
  };

  // 5. Generate Module with Readiness Validation and Module-Scoped Progress
  const handleGenerateModule = async (moduleType: string, planningInputs?: RoadmapPlanningInputs | TechStackPlanningInputs) => {
    if (!currentProject) return;
    const targetProjectId = currentProject.id;
    const targetModuleType = normalizeModuleType(moduleType);
    const genKey = `${targetProjectId}:${targetModuleType}`;
    const epoch = sessionEpochRef.current;

    // Prevent duplicate submissions if this module or another generation is already in flight
    if (Object.keys(generationTimersRef.current).length > 0 || mutationKeysRef.current.size > 0) {
      return;
    }

    setReadinessError(null);

    setGeneratingProgress(prev => ({
      ...prev,
      [genKey]: { stageText: 'Generating and validating your project output...', progressPercent: 0 }
    }));
    // This is an activity indicator. Only the server can report real pipeline progress.
    const progressTimer = setInterval(() => {}, 60000);

    generationTimersRef.current[genKey] = progressTimer;

    try {
      const updated = await api.modules.generate(targetProjectId, targetModuleType, planningInputs);
      if (sessionEpochRef.current !== epoch) return;
      
      // If the user is still viewing this exact project and module, update the live view
      if (activeProjectIdRef.current === targetProjectId && activeModuleTypeRef.current === targetModuleType) {
        setModuleDetail(updated);
        updateBadgeForModule(targetModuleType, updated);
      } else if (activeProjectIdRef.current === targetProjectId) {
        // User switched module within the same project; update badge without corrupting active module view
        updateBadgeForModule(targetModuleType, updated);
      }

      setCurrentProject(prev => prev?.id === targetProjectId ? { ...prev, generated_modules: Array.from(new Set([...(prev.generated_modules || []), targetModuleType])) } : prev);

      // Also update project list generated_modules so dashboard/sidebar stay accurate
      setProjects(prev => prev.map(p => {
        if (p.id === targetProjectId) {
          const set = new Set(p.generated_modules || []);
          set.add(targetModuleType);
          return { ...p, generated_modules: Array.from(set) };
        }
        return p;
      }));

      if (targetModuleType === 'execution_roadmap') {
        const taskList = await api.tasks.list(targetProjectId);
        if (activeProjectIdRef.current === targetProjectId) {
          setTasks(taskList);
          const sum = await api.tasks.getSummary(targetProjectId);
          setSummary(sum);
          setModuleBadges(prev => ({
            ...prev,
            execution_roadmap: { ...prev.execution_roadmap, isGenerated: taskList.length > 0 },
          }));
        }
      }
    } catch (err: any) {
      if (sessionEpochRef.current !== epoch) return;
      if (err.status === 422 && err.data?.error === 'READINESS_VALIDATION_FAILED') {
        if (activeProjectIdRef.current === targetProjectId && activeModuleTypeRef.current === targetModuleType) {
          setReadinessError({
            moduleType: targetModuleType,
            message: err.data.message || 'Project details are insufficient for blueprint generation.',
            missingFields: err.data.missing_fields || [],
            reasons: err.data.reasons || []
          });
        }
      } else if (err.status === 409 && (
        err.data?.error === 'VERSION_LIMIT_EXCEEDED' ||
        (err.message && err.message.includes('VERSION_LIMIT_EXCEEDED'))
      )) {
        alert('This module already has 5 saved versions. Use Delete to remove the current version, then generate again. Other versions will remain available.');
      } else {
        alert(err.message || 'Blueprint generation failed. Please try again.');
      }
    } finally {
      clearInterval(progressTimer);
      delete generationTimersRef.current[genKey];
      setGeneratingProgress(prev => {
        const next = { ...prev };
        delete next[genKey];
        return next;
      });
    }
  };

  // A mutation captures its destination before awaiting; later navigation never changes it.
  const runModuleMutation = async (work: (projectId: string, moduleType: string) => Promise<void>) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    const moduleType = activeModule;
    const key = `${projectId}:${moduleType}`;
    if (mutationKeysRef.current.has(key) || generationTimersRef.current[key]) throw new Error('This section is already being updated. Please wait.');
    const navigation = navigationRef.current;
    mutationKeysRef.current.add(key);
    setModuleLoading(true);
    try {
      await work(projectId, moduleType);
    } finally {
      mutationKeysRef.current.delete(key);
      if (isViewing(projectId, moduleType, navigation)) setModuleLoading(false);
    }
  };

  const handleModifyModule = async (instruction: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      try {
        await api.modules.modify(projectId, moduleType, instruction);
        if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType);
      } catch (err: any) {
        const details = typeof err.data === 'object' ? err.data : {};
        if (err.status === 409 && (details.error === 'VERSION_LIMIT_EXCEEDED' || err.message?.includes('5 saved versions') || err.message?.includes('VERSION_LIMIT_EXCEEDED'))) {
          if (isViewing(projectId, moduleType)) {
            setConflictData({ projectId, moduleType, moduleTitle: moduleType.replaceAll('_', ' '), existingVersions: details.existing_versions || moduleDetail?.versions || [], pendingInstruction: instruction });
            setConflictModalOpen(true);
          }
          return;
        }
        throw err;
      }
    });
  };

  const handleResolveReplace = async (replaceVersionId: string) => {
    if (!conflictData || !isViewing(conflictData.projectId, conflictData.moduleType)) return;
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.resolveConflict(projectId, moduleType, replaceVersionId, conflictData.pendingInstruction);
      setConflictModalOpen(false);
      setConflictData(null);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType);
    });
  };

  const handleRenameVersion = async (newName: string) => {
    if (!moduleDetail?.active_version_id) return;
    const versionId = moduleDetail.active_version_id;
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.renameVersion(projectId, moduleType, versionId, newName);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType);
    });
  };

  const handleDeleteVersion = async (versionId: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.deleteVersion(projectId, moduleType, versionId);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType);
    });
  };

  const handleDeleteModule = async (moduleType: string) => {
    if (normalizeModuleType(moduleType) !== activeModule) return;
    await runModuleMutation(async (projectId, targetModuleType) => {
      await api.modules.delete(projectId, targetModuleType);
      const removeGenerated = (project: Project) => ({ ...project, generated_modules: (project.generated_modules || []).filter(type => normalizeModuleType(type) !== targetModuleType) });
      setProjects(prev => prev.map(project => project.id === projectId ? removeGenerated(project) : project));
      setCurrentProject(prev => prev?.id === projectId ? removeGenerated(prev) : prev);
      if (isViewing(projectId)) {
        setModuleBadges(prev => ({ ...prev, [targetModuleType]: { version: 'V1', isGenerated: false } }));
        if (isViewing(projectId, targetModuleType)) setModuleDetail(null);
        if (targetModuleType === 'execution_roadmap') { setTasks([]); setSummary(EMPTY_SUMMARY); }
      }
    });
  };

  const handleRestoreVersion = async (versionId: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.restoreVersion(projectId, moduleType, versionId);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType);
    });
  };

  // Manual task edits are refreshed from the server so all derived roadmap views agree.
  const refreshTasks = async (projectId: string) => {
    const [taskList, sum] = await Promise.all([api.tasks.list(projectId), api.tasks.getSummary(projectId)]);
    if (isViewing(projectId)) { setTasks(taskList); setSummary(sum); }
  };
  const handleAddTask = async (taskData: any) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    await api.tasks.create(projectId, taskData);
    await refreshTasks(projectId);
  };
  const handleUpdateTask = async (taskId: string, taskData: any) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    await api.tasks.update(projectId, taskId, taskData);
    await refreshTasks(projectId);
  };
  const handleDeleteTask = async (taskId: string) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    await api.tasks.delete(projectId, taskId);
    await refreshTasks(projectId);
  };

  // 10. Project Update / Fork
  const handleUpdateProject = async (data: any, createCopy: boolean) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    const updated = await api.projects.update(projectId, { ...data, create_copy: createCopy });
    await loadProjects();
    if (!isViewing(projectId)) return;
    if (createCopy) await handleOpenProject(updated.id, 'overview');
    else setCurrentProject(updated);
  };

  // 11. Project Creation Wizard
  const handleProjectCreated = async (payload: any) => {
    const epoch = sessionEpochRef.current;
    const newProj = await api.projects.create(payload);
    if (sessionEpochRef.current !== epoch) return;
    setIsWizardOpen(false);
    await loadProjects();
    await handleOpenProject(newProj.id);
  };

  // 12. Delete Project
  const handleDeleteProject = async (projectId: string) => {
    try {
      await api.projects.delete(projectId);
      await loadProjects();
      if (currentProject?.id === projectId) {
        clearWorkspace();
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete project');
    }
  };

  // 13. Bulk Delete Projects (Part B4 & F-07)
  const handleBulkDeleteProjects = async (projectIds: string[]) => {
    await api.projects.bulkDelete(projectIds);
    await loadProjects();
    if (currentProject && projectIds.includes(currentProject.id)) {
      clearWorkspace();
    }
  };

  // Admin Portal Routing
  if (isAdminRoute) {
    if (adminAuthChecking) {
      return (
        <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-workspace)', color: 'var(--text-main)', gap: 12 }}>
          <Loader2 size={24} className="animate-spin" color="var(--primary-text)" />
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
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--sidebar-bg)', color: 'var(--text-main)', gap: 12 }}>
        <Loader2 size={24} className="animate-spin" color="var(--primary-text)" />
        <span>Loading Venture Atlas...</span>
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
          onBulkDeleteProjects={handleBulkDeleteProjects}
          onLogout={logout}
          onUserUpdated={(updated) => setCurrentUser(updated)}
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
        onBackToDashboard={() => { clearWorkspace(); window.history.pushState({}, '', '/'); }}
        onCreateNewProject={() => setIsWizardOpen(true)}
        onExportFullPdf={() => api.exports.downloadFullProjectPdf(currentProject.id, currentProject.name)}
        moduleVersionBadges={moduleBadges}
      />

      <div className="main-wrapper" key={currentProject.id}>
        {/* Top Header */}
        <Header
          project={currentProject}
          user={currentUser}
          onLogout={logout}
          onEditProject={() => handleSelectModule('overview')}
          onSelectModule={handleSelectModule}
          onUserUpdated={(updated) => setCurrentUser(updated)}
        />

        {/* Scrollable Workspace Body */}
        <div className="workspace-scroll-area">
          {moduleError && <div className="card" role="alert"><p>{moduleError}</p><button type="button" className="btn-secondary" onClick={() => loadModuleContent(currentProject.id, activeModule)}>Retry loading</button></div>}
          {/* Readiness Validation Failure Notification Banner */}
          {readinessError && (
            <div
              className="card"
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-color)',
                padding: '16px 20px',
                marginBottom: 20,
                borderRadius: 8
              }}
              role="alert"
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ color: 'var(--primary-text)', marginTop: 2, flexShrink: 0 }}>
                    <AlertCircle size={20} />
                  </div>
                  <div>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--primary-text)', margin: 0 }}>
                      {readinessError.message}
                    </h4>
                    <p style={{ fontSize: 12.5, color: 'var(--primary-text)', margin: '4px 0 8px 0' }}>
                      The blueprint generator requires clear, non-placeholder business parameters to synthesize actionable outputs.
                    </p>
                    <ul style={{ margin: '0 0 14px 18px', fontSize: 12.5, color: 'var(--primary-text)' }}>
                      {readinessError.reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                    <button
                      onClick={() => {
                        setReadinessError(null);
                        handleSelectModule('overview');
                      }}
                      className="btn-primary"
                      style={{ fontSize: 12.5, padding: '7px 16px', gap: 6 }}
                    >
                      Update Project in Overview &rarr;
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => setReadinessError(null)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--primary-text)', cursor: 'pointer', padding: 4 }}
                  title="Dismiss notice"
                  aria-label="Dismiss notice"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
          )}

          {activeModule === 'overview' && (
            <OverviewModule
              key={currentProject.id}
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
              onCreateNew={() => handleGenerateModule('bmc')}
              onDeleteModule={() => handleDeleteModule('bmc')}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'bmc', currentProject.name)}
              isLoading={moduleLoading}
              isGenerating={Boolean(generatingProgress[`${currentProject.id}:bmc`])}
              generationProgress={generatingProgress[`${currentProject.id}:bmc`] || null}
              isGenerateDisabled={Object.keys(generatingProgress).length > 0 && !generatingProgress[`${currentProject.id}:bmc`]}
            />
          )}

          {activeModule === 'tech_stack' && (
            <TechStackModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={(inputs) => handleGenerateModule('tech_stack', inputs)}
              onModify={handleModifyModule}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onCreateNew={() => handleGenerateModule('tech_stack')}
              onDeleteModule={() => handleDeleteModule('tech_stack')}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'tech_stack', currentProject.name)}
              isLoading={moduleLoading}
              isGenerating={Boolean(generatingProgress[`${currentProject.id}:tech_stack`])}
              generationProgress={generatingProgress[`${currentProject.id}:tech_stack`] || null}
              isGenerateDisabled={Object.keys(generatingProgress).length > 0 && !generatingProgress[`${currentProject.id}:tech_stack`]}
            />
          )}

          {activeModule === 'idea_validator' && (
            <IdeaValidatorModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('idea_validator')}
              onDeleteModule={() => handleDeleteModule('idea_validator')}
              onDeleteVersion={handleDeleteVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'idea_validator', currentProject.name)}
              isLoading={moduleLoading}
              isGenerating={Boolean(generatingProgress[`${currentProject.id}:idea_validator`])}
              generationProgress={generatingProgress[`${currentProject.id}:idea_validator`] || null}
              isGenerateDisabled={Object.keys(generatingProgress).length > 0 && !generatingProgress[`${currentProject.id}:idea_validator`]}
            />
          )}

          {activeModule === 'market_research' && (
            <MarketResearchModule
              project={currentProject}
              moduleDetail={moduleDetail as any}
              onGenerate={() => handleGenerateModule('market_research')}
              onDeleteModule={() => handleDeleteModule('market_research')}
              onDeleteVersion={handleDeleteVersion}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'market_research', currentProject.name)}
              isLoading={moduleLoading}
              isGenerating={Boolean(generatingProgress[`${currentProject.id}:market_research`])}
              generationProgress={generatingProgress[`${currentProject.id}:market_research`] || null}
              isGenerateDisabled={Object.keys(generatingProgress).length > 0 && !generatingProgress[`${currentProject.id}:market_research`]}
            />
          )}

          {activeModule === 'execution_roadmap' && (
            <ExecutionRoadmapModule
              project={currentProject}
              moduleDetail={moduleDetail}
              tasks={tasks}
              summary={summary}
              onGenerate={(inputs) => handleGenerateModule('execution_roadmap', inputs)}
              onModify={handleModifyModule}
              onAddTask={handleAddTask}
              onUpdateTask={handleUpdateTask}
              onDeleteTask={handleDeleteTask}
              onRenameVersion={handleRenameVersion}
              onDeleteVersion={handleDeleteVersion}
              onRestoreVersion={handleRestoreVersion}
              onDeleteModule={() => handleDeleteModule('execution_roadmap')}
              onExportPdf={() => api.exports.downloadModulePdf(currentProject.id, 'execution_roadmap', currentProject.name)}
              isLoading={moduleLoading}
              isGenerating={Boolean(generatingProgress[`${currentProject.id}:execution_roadmap`])}
              generationProgress={generatingProgress[`${currentProject.id}:execution_roadmap`] || null}
              isGenerateDisabled={Object.keys(generatingProgress).length > 0 && !generatingProgress[`${currentProject.id}:execution_roadmap`]}
            />
          )}

          {activeModule === 'blueprint_copilot' && (
            <BlueprintCopilotModule
              project={currentProject}
              messages={copilotMessages}
              onSendMessage={async (msg) => {
                const projectId = currentProject.id;
                await runModuleMutation(async () => {
                  await api.copilot.sendMessage(projectId, msg);
                  if (isViewing(projectId, 'blueprint_copilot')) {
                    const history = await api.copilot.getHistory(projectId);
                    if (isViewing(projectId, 'blueprint_copilot')) setCopilotMessages(history);
                  }
                });
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
