import React, { useState, useEffect, lazy, useRef, useCallback } from 'react';
import { User, Project, ModuleDetail, RoadmapTask, RoadmapSummary, CopilotMessage, RoadmapPlanningInputs, TechStackPlanningInputs } from './types';
import { api } from './services/api';
import { queryCache } from './services/queryCache';
import { saveNavDestination, getNavDestination, clearNavDestination, clearAllNavDestinations, clearOtherUserNavDestinations } from './services/navigationStorage';
import { prefetchModule, prefetchProjectData, cancelPrefetchQueue } from './services/prefetch';
import { clearAllDrafts, clearOtherUserDrafts } from './services/draftStorage';

import { ModuleSkeleton } from './components/Skeletons';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage, RequestStatus } from './pages/DashboardPage';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewModule } from './components/OverviewModule';

// Route-level lazy features with local suspense
const BMCModule = lazy(() => import('./components/BMCModule').then(module => ({ default: module.BMCModule })));
const TechStackModule = lazy(() => import('./components/TechStackModule').then(module => ({ default: module.TechStackModule })));
const IdeaValidatorModule = lazy(() => import('./components/IdeaValidatorModule').then(module => ({ default: module.IdeaValidatorModule })));
const MarketResearchModule = lazy(() => import('./components/MarketResearchModule').then(module => ({ default: module.MarketResearchModule })));
const ExecutionRoadmapModule = lazy(() => import('./components/ExecutionRoadmapModule').then(module => ({ default: module.ExecutionRoadmapModule })));
const BlueprintCopilotModule = lazy(() => import('./components/BlueprintCopilotModule').then(module => ({ default: module.BlueprintCopilotModule })));
const NewProjectWizard = lazy(() => import('./components/NewProjectWizard').then(module => ({ default: module.NewProjectWizard })));
const VersionConflictModal = lazy(() => import('./components/VersionConflictModal').then(module => ({ default: module.VersionConflictModal })));
const AdminApp = lazy(() => import('./admin/AdminApp').then(module => ({ default: module.AdminApp })));
const AdminLoginPage = lazy(() => import('./admin/pages/AdminLoginPage').then(module => ({ default: module.AdminLoginPage })));

import { Loader2, AlertCircle, X } from 'lucide-react';
import { WizardLoadingShell, WizardErrorBoundary } from './components/WizardLoadingShell';
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

export type AuthState = 'pending' | 'authenticated' | 'rejected';
export type DestinationState = 'idle' | 'pending' | 'valid' | 'invalid';
export type ModuleLoadState = 'idle' | 'loading' | 'loaded' | 'failed';
export type ModuleBadgeStatus = 'unknown' | 'loading' | 'generated' | 'not-generated' | 'error';

export interface ModuleBadgeState {
  version: string;
  isGenerated?: boolean;
  status: ModuleBadgeStatus;
}

const INITIAL_MODULE_BADGES: Record<string, ModuleBadgeState> = {
  overview: { version: 'V1', isGenerated: true, status: 'generated' },
  bmc: { version: 'V1', status: 'unknown' },
  tech_stack: { version: 'V1', status: 'unknown' },
  idea_validator: { version: 'V1', status: 'unknown' },
  market_research: { version: 'V1', status: 'unknown' },
  execution_roadmap: { version: 'V1', status: 'unknown' },
  blueprint_copilot: { version: 'V1', status: 'generated' }
};

const PENDING_USER_SHELL: User = {
  id: 'pending',
  username: '',
  email: '',
  role: 'user',
  created_at: ''
};

const NEUTRAL_PROJECT_SHELL: Project = {
  id: '',
  name: 'Workspace',
  stage: '' as any,
  description: '',
  industry: '',
  target_customers: '',
  goals: '',
  business_context: '',
  budget: '',
  active_module: 'execution_roadmap',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: [],
  created_at: '',
  updated_at: '',
};

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const currentUserRef = useRef<User | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [_authState, setAuthState] = useState<AuthState>('pending');

  const [destinationState, setDestinationState] = useState<DestinationState>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('project') ? 'pending' : 'idle';
  });
  const [requestedDestination, setRequestedDestination] = useState<{ projectId: string; module: string } | null>(() => {
    const params = new URLSearchParams(window.location.search);
    const pId = params.get('project');
    if (pId) {
      return { projectId: pId, module: normalizeModuleType(params.get('module') || 'execution_roadmap') };
    }
    return null;
  });

  // Track explicit user intent to view workspace vs public landing page
  const [userIntendsWorkspace, setUserIntendsWorkspace] = useState<boolean>(() => {
    const params = new URLSearchParams(window.location.search);
    return Boolean(params.get('project')) || params.get('workspace') === 'true';
  });

  // Admin Portal State
  const [isAdminRoute, setIsAdminRoute] = useState<boolean>(() => window.location.pathname.startsWith('/admin'));
  const [adminUser, setAdminUser] = useState<any | null>(null);
  const [adminAuthChecking, setAdminAuthChecking] = useState<boolean>(() => window.location.pathname.startsWith('/admin'));

  // Projects & Navigation
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsStatus, setProjectsStatus] = useState<RequestStatus>('idle');
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [activeModule, setActiveModule] = useState<string>('execution_roadmap');
  const [isWizardOpen, setIsWizardOpen] = useState<boolean>(false);
  const [restorationError, setRestorationError] = useState<{ projectId: string; module: string; message: string } | null>(null);

  // Active Module State
  const [moduleDetail, setModuleDetail] = useState<ModuleDetail | null>(null);
  const [moduleStatus, setModuleStatus] = useState<RequestStatus>('idle');
  const [tasks, setTasks] = useState<RoadmapTask[]>([]);
  const [summary, setSummary] = useState<RoadmapSummary>(EMPTY_SUMMARY);
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [hasMoreCopilot, setHasMoreCopilot] = useState<boolean>(false);
  const [loadingOlderCopilot, setLoadingOlderCopilot] = useState<boolean>(false);
  const [copilotOlderCursor, setCopilotOlderCursor] = useState<string | null>(null);
  const [moduleLoading, setModuleLoading] = useState<boolean>(false);
  const [moduleError, setModuleError] = useState<string | null>(null);

  const navigationRef = useRef(0);
  const sessionEpochRef = useRef(0);
  const mutationKeysRef = useRef(new Set<string>());

  // Asynchronous Debounced Navigation Persistence (Section 12)
  const navPersistTimerRef = useRef<any>(null);
  const lastPersistedModuleRef = useRef<{ projectId: string; module: string } | null>(null);

  const persistNavigationToServer = useCallback((projectId: string, moduleId: string) => {
    if (navPersistTimerRef.current) {
      clearTimeout(navPersistTimerRef.current);
    }
    navPersistTimerRef.current = setTimeout(async () => {
      if (
        lastPersistedModuleRef.current?.projectId === projectId &&
        lastPersistedModuleRef.current?.module === moduleId
      ) {
        return;
      }
      try {
        await api.projects.updateActiveModule(projectId, moduleId);
        lastPersistedModuleRef.current = { projectId, module: moduleId };
      } catch (e) {
        console.warn('Asynchronous navigation persistence skipped:', e);
      }
    }, 700);
  }, []);

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

  const activeGenerationsRef = useRef<Set<string>>(new Set());

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeGenerationsRef.current.clear();
      if (navPersistTimerRef.current) clearTimeout(navPersistTimerRef.current);
    };
  }, []);

  // Dynamic Badges & Race-Condition Guard Refs
  const activeProjectIdRef = useRef<string | null>(null);
  const activeModuleTypeRef = useRef<string>('execution_roadmap');
  const openProjectRef = useRef<(projectId: string, targetModuleOverride?: string, writeHistory?: boolean) => Promise<void>>(async () => {});

  const isViewing = (projectId: string, moduleType?: string, navigation?: number) =>
    activeProjectIdRef.current === projectId &&
    (!moduleType || activeModuleTypeRef.current === moduleType) &&
    (navigation === undefined || navigationRef.current === navigation);

  const clearWorkspace = () => {
    activeProjectIdRef.current = null;
    navigationRef.current++;
    setCurrentProject(null);
    setModuleDetail(null);
    setModuleStatus('idle');
    setTasks([]);
    setSummary(EMPTY_SUMMARY);
    setCopilotMessages([]);
    setHasMoreCopilot(false);
    setLoadingOlderCopilot(false);
    setCopilotOlderCursor(null);
    setReadinessError(null);
    setModuleError(null);
    setConflictModalOpen(false);
    setConflictData(null);
    setModuleLoading(false);
    setModuleBadges(INITIAL_MODULE_BADGES);
    setRestorationError(null);
    setRequestedDestination(null);
    setDestinationState('idle');
  };

  const clearSession = () => {
    sessionEpochRef.current++;
    clearWorkspace();
    setCurrentUser(null);
    setAdminUser(null);
    setProjects([]);
    setProjectsStatus('idle');
    setProjectsError(null);
    setIsWizardOpen(false);
    activeGenerationsRef.current.clear();
    if (navPersistTimerRef.current) clearTimeout(navPersistTimerRef.current);
    setGeneratingProgress({});
    mutationKeysRef.current.clear();
    setModuleBadges(INITIAL_MODULE_BADGES);
    setAuthState('rejected');
    setDestinationState('idle');
    setRequestedDestination(null);
    setRestorationError(null);
    document.body.style.removeProperty('font-family');
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch {}
    queryCache.clearAll();
    clearAllDrafts();
    clearAllNavDestinations();
    cancelPrefetchQueue();
    currentUserRef.current = null;
    clearSession();
    setUserIntendsWorkspace(false);
    window.history.replaceState({}, '', '/');
  };


  const [moduleBadges, setModuleBadges] = useState<Record<string, ModuleBadgeState>>(INITIAL_MODULE_BADGES);

  const updateBadgeForModule = (moduleType: string, detail: ModuleDetail | null) => {
    if (!detail) return;
    const vStr = detail.active_version_name || (detail.active_version_number ? `V${detail.active_version_number}` : 'V1');
    const isGen = !!detail.data;
    setModuleBadges(prev => {
      const prevMod = prev[moduleType];
      const isConfirmedGenerated = prevMod?.status === 'generated' || isGen;
      return {
        ...prev,
        [moduleType]: {
          version: vStr,
          isGenerated: isConfirmedGenerated,
          status: isConfirmedGenerated ? 'generated' : 'not-generated'
        }
      };
    });
  };

  // Cached, Deduplicated Project Loading (Section 6 & 7)
  const loadProjects = useCallback(async (userScope?: string, forceFresh = false): Promise<Project[] | null> => {
    const epoch = sessionEpochRef.current;
    const cached = queryCache.getCached<Project[]>('projects:list', userScope);

    if (cached && !forceFresh) {
      setProjects(cached);
      setProjectsStatus(cached.length === 0 ? 'success-empty' : 'success-with-data');
      setProjectsError(null);
    } else if (!cached) {
      setProjectsStatus('loading');
    }

    try {
      const projs = await queryCache.fetchWithCache(
        'projects:list',
        () => api.projects.list(),
        { staleTimeMs: 60000, userScope, forceFresh }
      );
      if (sessionEpochRef.current === epoch) {
        setProjects(projs);
        setProjectsStatus(projs.length === 0 ? 'success-empty' : 'success-with-data');
        setProjectsError(null);
      }
      return projs;
    } catch (error: any) {
      if (sessionEpochRef.current === epoch) {
        if (!queryCache.getCached('projects:list', userScope)) {
          setProjectsStatus('error');
        }
        setProjectsError(error?.message || 'Your projects could not be loaded. Please retry.');
      }
      return null;
    }
  }, []);


  // 1. Initial Authentication Check in Background (Section 3)
  useEffect(() => {
    let isCancelled = false;

    const checkAuth = async () => {
      try {
        const session = await api.auth.getMe();
        if (isCancelled) return;
        if (session && session.user) {
          setAuthState('authenticated');
          const newUserId = session.user.id;
          if (currentUserRef.current && currentUserRef.current.id !== newUserId) {
            queryCache.clearAll();
            clearAllDrafts();
            clearAllNavDestinations();
            cancelPrefetchQueue();
            clearWorkspace();
            setModuleBadges(INITIAL_MODULE_BADGES);
          } else {
            queryCache.enforceUserScope(newUserId);
            clearOtherUserNavDestinations(newUserId);
            clearOtherUserDrafts(newUserId);
          }
          currentUserRef.current = session.user;
          setCurrentUser(session.user);
          const userScope = session.user.id;

          // Background preloading of projects
          const projs = await loadProjects(userScope);
          if (isCancelled) return;


          // Destination Restoration Sequence (Section 5)
          const route = new URLSearchParams(window.location.search);
          const deepProjectId = route.get('project');
          const onAdmin = window.location.pathname.startsWith('/admin');

          if (deepProjectId && !onAdmin) {
            if (projs !== null) {
              const projectExists = projs.some(p => p.id === deepProjectId);
              if (projectExists) {
                setDestinationState('valid');
                setUserIntendsWorkspace(true);
                await openProjectRef.current(deepProjectId, route.get('module') || undefined, false);
              } else {
                setDestinationState('invalid');
                setRequestedDestination(null);
                setUserIntendsWorkspace(true);
                window.history.replaceState({}, '', '/?workspace=true');
              }
            } else {
              // Transient failure when preloading project list!
              // Deep-link intent is retained, show inline recoverable error in the neutral workspace shell
              setDestinationState('pending');
              setUserIntendsWorkspace(true);
              setRestorationError({
                projectId: deepProjectId,
                module: normalizeModuleType(route.get('module') || 'execution_roadmap'),
                message: 'Failed to load projects. Please check your connection and retry.'
              });
            }
          } else if (!onAdmin && route.get('workspace') === 'true') {
            setUserIntendsWorkspace(true);
            setDestinationState('idle');
            setRequestedDestination(null);
            // Restore last valid saved destination
            const savedDest = getNavDestination(userScope);
            if (savedDest && projs && projs.some(p => p.id === savedDest.projectId)) {
              await openProjectRef.current(savedDest.projectId, savedDest.module, true);
            } else if (savedDest && projs !== null) {
              clearNavDestination(userScope);
            }
          } else {
            setDestinationState('idle');
            setRequestedDestination(null);
          }
        } else {
          setAuthState('rejected');
          setCurrentUser(null);
          setRequestedDestination(null);
          setDestinationState('invalid');
        }
      } catch {
        if (!isCancelled) {
          setAuthState('rejected');
          setCurrentUser(null);
          setRequestedDestination(null);
          setDestinationState('invalid');
        }
      } finally {
        if (!isCancelled) setAuthChecking(false);
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
      queryCache.clearAll();
      clearAllDrafts();
      clearSession();
      setUserIntendsWorkspace(false);
      window.history.replaceState({}, '', '/');
    };
    window.addEventListener('auth:expired', handleAuthExpired);

    const handlePopState = () => {
      const onAdmin = window.location.pathname.startsWith('/admin');
      setIsAdminRoute(onAdmin);
      if (onAdmin) {
        checkAdminAuth();
      } else {
        const route = new URLSearchParams(window.location.search);
        const projectId = route.get('project');
        const moduleId = route.get('module') || undefined;
        if (projectId) {
          setUserIntendsWorkspace(true);
          const canonical = normalizeModuleType(moduleId || 'execution_roadmap');
          setRequestedDestination({
            projectId,
            module: canonical
          });
          setDestinationState('pending');
          void openProjectRef.current(projectId, moduleId, false);
        } else {
          clearWorkspace();
          setRequestedDestination(null);
          setDestinationState('idle');
          if (route.get('workspace') !== 'true') {
            // If navigating back to root without workspace param
            setUserIntendsWorkspace(false);
          }
        }
      }
    };
    window.addEventListener('popstate', handlePopState);

    return () => {
      isCancelled = true;
      window.removeEventListener('auth:expired', handleAuthExpired);
      window.removeEventListener('popstate', handlePopState);
    };
  }, [loadProjects]);

  // 2. Open Project & Restore Navigation Memory (Section 4 & 5)
  const handleOpenProject = async (projectId: string, targetModuleOverride?: string, writeHistory = true) => {
    const isCurrentActive = currentProject?.id === projectId;

    // Previous workspace cleanup must happen BEFORE the new navigation token is captured
    if (!isCurrentActive && currentProject) {
      clearWorkspace();
    }

    const navId = ++navigationRef.current;
    activeProjectIdRef.current = projectId;
    setModuleLoading(true);
    setRestorationError(null);
    setRequestedDestination({
      projectId,
      module: normalizeModuleType(targetModuleOverride || 'execution_roadmap')
    });

    // Optimistically use cached project metadata if available for the same project
    const cachedProj = queryCache.getCached<Project>(`project:${projectId}`, currentUser?.id) ||
      projects.find(p => p.id === projectId);

    if (cachedProj) {
      setCurrentProject(cachedProj);
      if (cachedProj.generated_modules) {
        const genSet = new Set(cachedProj.generated_modules);
        setModuleBadges({
          overview: { version: 'V1', isGenerated: true, status: 'generated' },
          bmc: { version: 'V1', isGenerated: genSet.has('bmc'), status: genSet.has('bmc') ? 'generated' : 'not-generated' },
          tech_stack: { version: 'V1', isGenerated: genSet.has('tech_stack'), status: genSet.has('tech_stack') ? 'generated' : 'not-generated' },
          idea_validator: { version: 'V1', isGenerated: genSet.has('idea_validator'), status: genSet.has('idea_validator') ? 'generated' : 'not-generated' },
          market_research: { version: 'V1', isGenerated: genSet.has('market_research'), status: genSet.has('market_research') ? 'generated' : 'not-generated' },
          execution_roadmap: { version: 'V1', isGenerated: genSet.has('execution_roadmap'), status: genSet.has('execution_roadmap') ? 'generated' : 'not-generated' },
          blueprint_copilot: { version: 'V1', isGenerated: true, status: 'generated' }
        });
      } else if (!isCurrentActive) {
        setModuleBadges(INITIAL_MODULE_BADGES);
      }
    } else if (!isCurrentActive) {
      setModuleBadges(INITIAL_MODULE_BADGES);
    }

    try {
      const proj = await queryCache.fetchWithCache(
        `project:${projectId}`,
        () => api.projects.get(projectId),
        { staleTimeMs: 60000, userScope: currentUser?.id }
      );
      if (activeProjectIdRef.current !== projectId || navigationRef.current !== navId) return;
      setCurrentProject(proj);

      const genModules = new Set(proj.generated_modules || []);
      setModuleBadges({
        overview: { version: 'V1', isGenerated: true, status: 'generated' },
        bmc: { version: 'V1', isGenerated: genModules.has('bmc'), status: genModules.has('bmc') ? 'generated' : 'not-generated' },
        tech_stack: { version: 'V1', isGenerated: genModules.has('tech_stack'), status: genModules.has('tech_stack') ? 'generated' : 'not-generated' },
        idea_validator: { version: 'V1', isGenerated: genModules.has('idea_validator'), status: genModules.has('idea_validator') ? 'generated' : 'not-generated' },
        market_research: { version: 'V1', isGenerated: genModules.has('market_research'), status: genModules.has('market_research') ? 'generated' : 'not-generated' },
        execution_roadmap: { version: 'V1', isGenerated: genModules.has('execution_roadmap'), status: genModules.has('execution_roadmap') ? 'generated' : 'not-generated' },
        blueprint_copilot: { version: 'V1', isGenerated: true, status: 'generated' }
      });

      const targetModule = normalizeModuleType(targetModuleOverride || proj.active_module || 'execution_roadmap');
      activeModuleTypeRef.current = targetModule;
      setActiveModule(targetModule);

      // Save harmless navigation preference to localStorage
      if (currentUser?.id) {
        saveNavDestination(currentUser.id, proj.id, targetModule);
      }

      if (writeHistory) {
        window.history.pushState({}, '', `/?project=${encodeURIComponent(proj.id)}&module=${encodeURIComponent(targetModule)}`);
      }

      loadModuleContent(proj.id, targetModule, currentUser?.id);

      if (targetModuleOverride && targetModule !== proj.active_module) {
        persistNavigationToServer(proj.id, targetModule);
      }
    } catch (err: any) {
      if (activeProjectIdRef.current !== projectId || navigationRef.current !== navId) {
        return;
      }

      if (isCurrentActive) {
        // Failed metadata refresh must not turn generated modules into "Not generated"
        setModuleBadges(prev => {
          const next = { ...prev };
          for (const key of Object.keys(next)) {
            if (next[key].status !== 'generated') {
              next[key] = { ...next[key], status: 'error' };
            }
          }
          return next;
        });
        setModuleLoading(false);
        setModuleError('Failed to refresh project metadata: ' + (err.message || 'Network error'));
      } else {
        setModuleLoading(false);

        const isNotFound = err?.status === 404 || err?.status === 403 ||
          err?.response?.status === 404 || err?.response?.status === 403 ||
          (err?.message && (err.message.includes('404') || err.message.toLowerCase().includes('not found') || err.message.toLowerCase().includes('unauthorized')));

        if (isNotFound) {
          setRequestedDestination(null);
          setDestinationState('invalid');
          clearWorkspace();
          setUserIntendsWorkspace(true);
          window.history.replaceState({}, '', '/?workspace=true');
          setProjectsError('The requested project could not be found or you do not have permission to access it.');
        } else {
          // Transient network/server failure:
          // Keep shell stable, show recoverable inline error with Retry & Back to portfolio
          setCurrentProject(null);
          setRestorationError({
            projectId,
            module: targetModuleOverride || 'execution_roadmap',
            message: err.message || 'Failed to load project details. Please check your connection and retry.'
          });
        }
      }
    }
  };

  const handleBackToPortfolioFromRestoration = () => {
    activeProjectIdRef.current = null;
    navigationRef.current++;
    setRestorationError(null);
    setRequestedDestination(null);
    setDestinationState('idle');
    setUserIntendsWorkspace(true);
    clearWorkspace();
    window.history.pushState({}, '', '/?workspace=true');
  };

  const handleRetryRestoration = async () => {
    const targetProjId = restorationError?.projectId || requestedDestination?.projectId;
    const targetMod = restorationError?.module || requestedDestination?.module || 'execution_roadmap';
    setRestorationError(null);
    setModuleLoading(true);

    if (!targetProjId) return;

    const userScope = currentUser?.id;
    let projsList = projects;
    if (projectsStatus !== 'success-with-data' && projectsStatus !== 'success-empty') {
      const fresh = await loadProjects(userScope, true);
      if (!fresh) {
        setModuleLoading(false);
        setRestorationError({
          projectId: targetProjId,
          module: targetMod,
          message: 'Failed to load projects. Please check your connection and retry.'
        });
        return;
      }
      projsList = fresh;
    }

    const projectExists = projsList.some(p => p.id === targetProjId);
    if (!projectExists) {
      setModuleLoading(false);
      setDestinationState('invalid');
      setRequestedDestination(null);
      clearWorkspace();
      window.history.replaceState({}, '', '/?workspace=true');
      setProjectsError('The requested project could not be found or you do not have permission to access it.');
      return;
    }

    setDestinationState('valid');
    await openProjectRef.current(targetProjId, targetMod, false);
  };

  useEffect(() => {
    openProjectRef.current = handleOpenProject;
  });

  // 3. Switch Module and Persist Navigation Memory Asynchronously (Section 12)
  const handleSelectModule = (moduleId: string) => {
    if (!currentProject) return;
    const canonicalModuleId = normalizeModuleType(moduleId);
    activeModuleTypeRef.current = canonicalModuleId;
    setActiveModule(canonicalModuleId);

    window.history.pushState({}, '', `/?project=${encodeURIComponent(currentProject.id)}&module=${encodeURIComponent(canonicalModuleId)}`);

    // Immediately save harmless preference to localStorage
    if (currentUser?.id) {
      saveNavDestination(currentUser.id, currentProject.id, canonicalModuleId);
    }

    setReadinessError(null);
    setConflictModalOpen(false);
    setConflictData(null);

    loadModuleContent(currentProject.id, canonicalModuleId, currentUser?.id);

    // Asynchronous debounced server persistence
    persistNavigationToServer(currentProject.id, canonicalModuleId);
  };

  // 4. Stable Module Content Loading with Explicit States & Cache (Section 4 & 7)
  async function loadModuleContent(projectId: string, moduleType: string, userScope?: string, forceFresh = false) {
    moduleType = normalizeModuleType(moduleType);
    const navigation = ++navigationRef.current;
    const viewing = () => isViewing(projectId, moduleType, navigation);

    const cacheKey = `module:${projectId}:${moduleType}`;
    const cachedDetail = queryCache.getCached<ModuleDetail>(cacheKey, userScope);


    // If cached content exists in memory, keep/show it immediately without destroying layout
    if (cachedDetail && !forceFresh) {
      setModuleDetail(cachedDetail);
      updateBadgeForModule(moduleType, cachedDetail);
      setModuleStatus(cachedDetail.data ? 'success-with-data' : 'success-empty');
      setModuleLoading(false);
    } else if (cachedDetail) {
      // Revalidating fresh data in background; keep existing cached content visible
      setModuleDetail(cachedDetail);
      setModuleLoading(true);
    } else if (moduleDetail && activeModuleTypeRef.current === moduleType && activeProjectIdRef.current === projectId) {
      // Revalidating fresh data in background; keep active content visible
      setModuleLoading(true);
    } else {
      // No cached data for this module: show module skeleton while loading fresh data
      setModuleStatus('loading');
      setModuleLoading(true);
      setModuleDetail(null);
    }

    setModuleError(null);

    try {
      if (!['overview', 'blueprint_copilot'].includes(moduleType)) {
        const detail = await queryCache.fetchWithCache(
          cacheKey,
          () => api.modules.get(projectId, moduleType),
          { staleTimeMs: 30000, userScope, forceFresh }
        );
        if (!viewing()) return;
        setModuleDetail(detail);
        updateBadgeForModule(moduleType, detail);
        setModuleStatus(detail.data ? 'success-with-data' : 'success-empty');
      } else {
        if (!viewing()) return;
        setModuleStatus('success-with-data');
      }

      if (moduleType === 'execution_roadmap') {
        const [taskList, sum] = await Promise.all([
          queryCache.fetchWithCache(`tasks:list:${projectId}`, () => api.tasks.list(projectId), {
            staleTimeMs: 30000,
            userScope,
            forceFresh
          }),
          queryCache.fetchWithCache(`tasks:summary:${projectId}`, () => api.tasks.getSummary(projectId), {
            staleTimeMs: 30000,
            userScope,
            forceFresh
          })
        ]);
        if (!viewing()) return;
        setTasks(taskList);
        setSummary(sum);
      }

      if (moduleType === 'blueprint_copilot') {
        const page = await queryCache.fetchWithCache(
          `copilot:page:${projectId}`,
          () => api.copilot.getPage(projectId, undefined, 50),
          { staleTimeMs: 30000, userScope, forceFresh }
        );
        if (!viewing()) return;
        setCopilotMessages(page.messages);
        setCopilotOlderCursor(page.before_cursor || null);
        setHasMoreCopilot(page.has_more);
      }
    } catch (error: any) {
      if (viewing()) {
        setModuleError(error.message || 'Could not load this section. Please retry.');
        if (!cachedDetail) {
          setModuleStatus('error');
        }
      }
    } finally {
      if (viewing()) {
        setModuleLoading(false);
      }
    }
  }

  // 5. Generate Module with Readiness Validation
  const handleGenerateModule = async (moduleType: string, planningInputs?: RoadmapPlanningInputs | TechStackPlanningInputs) => {
    if (!currentProject) return;
    const targetProjectId = currentProject.id;
    const targetModuleType = normalizeModuleType(moduleType);
    const genKey = `${targetProjectId}:${targetModuleType}`;
    const epoch = sessionEpochRef.current;

    if (activeGenerationsRef.current.size > 0 || mutationKeysRef.current.size > 0) {
      return;
    }

    setReadinessError(null);

    const pendingTextMap: Record<string, string> = {
      bmc: 'Generating your business model…',
      tech_stack: 'Generating your technical architecture…',
      idea_validator: 'Assessing business viability and experiments…',
      market_research: 'Analyzing market landscape and dynamics…',
      execution_roadmap: 'Generating execution tasks and milestones…'
    };
    const stageText = pendingTextMap[targetModuleType] || 'Generating planning output…';

    setGeneratingProgress(prev => ({
      ...prev,
      [genKey]: { stageText, progressPercent: 0 }
    }));
    activeGenerationsRef.current.add(genKey);

    try {
      const updated = await api.modules.generate(targetProjectId, targetModuleType, planningInputs);
      if (sessionEpochRef.current !== epoch) return;

      // Invalidate module cache
      queryCache.invalidate(`module:${targetProjectId}:${targetModuleType}`);

      if (activeProjectIdRef.current === targetProjectId && activeModuleTypeRef.current === targetModuleType) {
        setModuleDetail(updated);
        setModuleStatus(updated.data ? 'success-with-data' : 'success-empty');
        updateBadgeForModule(targetModuleType, updated);
      } else if (activeProjectIdRef.current === targetProjectId) {
        updateBadgeForModule(targetModuleType, updated);
      }

      setCurrentProject(prev => prev?.id === targetProjectId ? { ...prev, generated_modules: Array.from(new Set([...(prev.generated_modules || []), targetModuleType])) } : prev);

      setProjects(prev => prev.map(p => {
        if (p.id === targetProjectId) {
          const set = new Set(p.generated_modules || []);
          set.add(targetModuleType);
          return { ...p, generated_modules: Array.from(set) };
        }
        return p;
      }));

      if (targetModuleType === 'execution_roadmap') {
        queryCache.invalidate(`tasks:list:${targetProjectId}`);
        queryCache.invalidate(`tasks:summary:${targetProjectId}`);
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
        if (activeProjectIdRef.current === targetProjectId && activeModuleTypeRef.current === targetModuleType) {
          setModuleError('This module already has 5 saved versions. Use Delete to remove the current version, then generate again. Other versions will remain available.');
        } else {
          alert('This module already has 5 saved versions. Use Delete to remove the current version, then generate again. Other versions will remain available.');
        }
      } else {
        if (activeProjectIdRef.current === targetProjectId && activeModuleTypeRef.current === targetModuleType) {
          setModuleError(err.message || 'Blueprint generation failed. Please try again.');
        } else {
          alert(err.message || 'Blueprint generation failed. Please try again.');
        }
      }
    } finally {
      activeGenerationsRef.current.delete(genKey);
      setGeneratingProgress(prev => {
        const next = { ...prev };
        delete next[genKey];
        return next;
      });
    }
  };

  const runModuleMutation = async (work: (projectId: string, moduleType: string) => Promise<void>) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    const moduleType = activeModule;
    const key = `${projectId}:${moduleType}`;
    if (mutationKeysRef.current.has(key) || activeGenerationsRef.current.has(key)) throw new Error('This section is already being updated. Please wait.');
    const navigation = navigationRef.current;
    mutationKeysRef.current.add(key);
    setModuleLoading(true);
    try {
      await work(projectId, moduleType);
    } catch (error: any) {
      if (isViewing(projectId, moduleType, navigation)) {
        setModuleError(error?.message || 'This section could not be updated. Please try again.');
      }
      throw error;
    } finally {
      mutationKeysRef.current.delete(key);
      if (isViewing(projectId, moduleType, navigation)) setModuleLoading(false);
    }
  };

  const handleModifyModule = async (instruction: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      try {
        await api.modules.modify(projectId, moduleType, instruction);
        queryCache.invalidate(`module:${projectId}:${moduleType}`);
        if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType, currentUser?.id, true);
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
      queryCache.invalidate(`module:${projectId}:${moduleType}`);
      setConflictModalOpen(false);
      setConflictData(null);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType, currentUser?.id, true);
    });
  };

  const handleRenameVersion = async (newName: string) => {
    if (!moduleDetail?.active_version_id) return;
    const versionId = moduleDetail.active_version_id;
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.renameVersion(projectId, moduleType, versionId, newName);
      queryCache.invalidate(`module:${projectId}:${moduleType}`);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType, currentUser?.id, true);
    });
  };

  const handleDeleteVersion = async (versionId: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.deleteVersion(projectId, moduleType, versionId);
      queryCache.invalidate(`module:${projectId}:${moduleType}`);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType, currentUser?.id, true);
    });
  };

  const handleDeleteModule = async (moduleType: string) => {
    if (normalizeModuleType(moduleType) !== activeModule) return;
    await runModuleMutation(async (projectId, targetModuleType) => {
      await api.modules.delete(projectId, targetModuleType);
      queryCache.invalidate(`module:${projectId}:${targetModuleType}`);
      const removeGenerated = (project: Project) => ({ ...project, generated_modules: (project.generated_modules || []).filter(type => normalizeModuleType(type) !== targetModuleType) });
      setProjects(prev => prev.map(project => project.id === projectId ? removeGenerated(project) : project));
      setCurrentProject(prev => prev?.id === projectId ? removeGenerated(prev) : prev);
      if (isViewing(projectId)) {
        setModuleBadges(prev => ({ ...prev, [targetModuleType]: { version: 'V1', isGenerated: false, status: 'not-generated' } }));
        if (isViewing(projectId, targetModuleType)) {
          setModuleDetail(null);
          setModuleStatus('success-empty');
        }
        if (targetModuleType === 'execution_roadmap') { setTasks([]); setSummary(EMPTY_SUMMARY); }
      }
    });
  };

  const handleRestoreVersion = async (versionId: string) => {
    await runModuleMutation(async (projectId, moduleType) => {
      await api.modules.restoreVersion(projectId, moduleType, versionId);
      queryCache.invalidate(`module:${projectId}:${moduleType}`);
      if (isViewing(projectId, moduleType)) await loadModuleContent(projectId, moduleType, currentUser?.id, true);
    });
  };

  const refreshTasks = async (projectId: string) => {
    queryCache.invalidate(`tasks:list:${projectId}`);
    queryCache.invalidate(`tasks:summary:${projectId}`);
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

  const handleLoadOlderCopilot = async () => {
    if (!currentProject || loadingOlderCopilot || copilotMessages.length === 0) return;
    const cursor = copilotOlderCursor || copilotMessages[0]?.id;
    if (!cursor) return;
    const projectId = currentProject.id;
    setLoadingOlderCopilot(true);
    try {
      const page = await api.copilot.getPage(projectId, cursor, 50);
      if (isViewing(projectId, 'blueprint_copilot')) {
        setCopilotMessages(prev => {
          const existingIds = new Set(prev.map(m => m.id));
          const freshOlder = page.messages.filter(m => !existingIds.has(m.id));
          return [...freshOlder, ...prev];
        });
        setCopilotOlderCursor(page.before_cursor || null);
        setHasMoreCopilot(page.has_more);
      }
    } catch (e) {
      console.warn('Failed to load older copilot messages:', e);
    } finally {
      if (isViewing(projectId, 'blueprint_copilot')) {
        setLoadingOlderCopilot(false);
      }
    }
  };

  // Project Update / Fork
  const handleUpdateProject = async (data: any, createCopy: boolean) => {
    if (!currentProject) return;
    const projectId = currentProject.id;
    const updated = await api.projects.update(projectId, { ...data, create_copy: createCopy });
    queryCache.invalidate('projects:list');
    queryCache.invalidate(`project:${projectId}`);
    await loadProjects(currentUser?.id, true);
    if (!isViewing(projectId)) return;
    if (createCopy) await handleOpenProject(updated.id, 'overview');
    else setCurrentProject(updated);
  };

  // Project Creation Wizard
  const handleProjectCreated = async (payload: any) => {
    const epoch = sessionEpochRef.current;
    const newProj = await api.projects.create(payload);
    if (sessionEpochRef.current !== epoch) return;
    setIsWizardOpen(false);
    queryCache.invalidate('projects:list');
    await loadProjects(currentUser?.id, true);
    await handleOpenProject(newProj.id);
  };

  // Delete Project
  const handleDeleteProject = async (projectId: string) => {
    await api.projects.delete(projectId);
    queryCache.invalidate('projects:list');
    queryCache.invalidate(`project:${projectId}`);
    if (currentUser?.id) clearNavDestination(currentUser.id);
    await loadProjects(currentUser?.id, true);
    if (currentProject?.id === projectId) {
      clearWorkspace();
    }
  };

  // Bulk Delete Projects
  const handleBulkDeleteProjects = async (projectIds: string[]) => {
    await api.projects.bulkDelete(projectIds);
    queryCache.invalidate('projects:list');
    projectIds.forEach(id => queryCache.invalidate(`project:${id}`));
    if (currentUser?.id) clearNavDestination(currentUser.id);
    await loadProjects(currentUser?.id, true);
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
        <React.Suspense fallback={<div style={{ padding: 24 }} role="status">Loading admin panel…</div>}>
          <AdminLoginPage
            onLoginSuccess={(session) => {
              setAdminUser(session.user);
              window.history.pushState({}, '', '/admin');
              setIsAdminRoute(true);
            }}
          />
        </React.Suspense>
      );
    }

    return (
      <React.Suspense fallback={<div style={{ padding: 24 }} role="status">Loading admin panel…</div>}>
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
      </React.Suspense>
    );
  }

  // Section 3: Instant Landing Page
  // Public landing page renders immediately without waiting for /api/auth/me or any API response.
  // If the user arrived directly with ?project= or ?workspace=, show the workspace frame while validating.
  if (!userIntendsWorkspace) {
    return (
      <LandingPage
        currentUser={currentUser}
        onOpenWorkspace={() => {
          setUserIntendsWorkspace(true);
          if (currentUser?.id) {
            loadProjects(currentUser.id);
            const savedDest = getNavDestination(currentUser.id);
            if (savedDest) {
              const cached = queryCache.getCached<Project[]>('projects:list');
              if (cached && cached.some(p => p.id === savedDest.projectId)) {
                handleOpenProject(savedDest.projectId, savedDest.module, true);
              }
            }
          }
        }}
        onAuthenticated={(sess) => {
          setCurrentUser(sess.user);
          setUserIntendsWorkspace(true);
          loadProjects(sess.user.id);
        }}
      />
    );
  }

  // If user intends workspace but session validation is still pending, or unauthenticated:
  if (!currentUser && !authChecking) {
    // Session check completed and confirmed unauthenticated -> return to LandingPage
    return (
      <LandingPage
        currentUser={null}
        onOpenWorkspace={() => setUserIntendsWorkspace(true)}
        onAuthenticated={(sess) => {
          setCurrentUser(sess.user);
          setUserIntendsWorkspace(true);
          loadProjects(sess.user.id);
        }}
      />
    );
  }

  // Section 4: Immediate Neutral Workspace Shell during restoration
  // If user requested a project/module URL destination, render neutral workspace shell immediately
  // while auth or destination validation is pending, avoiding the portfolio flash!
  if (requestedDestination && destinationState !== 'invalid' && (!currentProject || !currentUser)) {
    const targetModule = requestedDestination.module || activeModule || 'execution_roadmap';
    return (
      <div className="app-layout">
        <Sidebar
          currentProject={NEUTRAL_PROJECT_SHELL}
          activeModule={targetModule}
          onSelectModule={(mod) => {
            const canonical = normalizeModuleType(mod);
            setRequestedDestination(prev => prev ? { ...prev, module: canonical } : null);
            setActiveModule(canonical);
          }}
          onBackToDashboard={handleBackToPortfolioFromRestoration}
          onCreateNewProject={() => {}}
          onExportFullPdf={() => {}}
          moduleVersionBadges={INITIAL_MODULE_BADGES}
        />
        <div className="main-wrapper">
          <Header
            project={NEUTRAL_PROJECT_SHELL}
            user={currentUser || PENDING_USER_SHELL}
            onLogout={logout}
          />
          <main className="content-area">
            {restorationError ? (
              <div className="card" role="alert" style={{ maxWidth: 520, margin: '40px auto', padding: '24px 28px', textAlign: 'center' }}>
                <div style={{ color: 'var(--accent-red, #ef4444)', marginBottom: 12 }}>
                  <AlertCircle size={32} style={{ margin: '0 auto' }} />
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 8px 0' }}>
                  Unable to load workspace
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, margin: '0 0 20px 0' }}>
                  {restorationError.message}
                </p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleRetryRestoration}
                  >
                    Retry
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleBackToPortfolioFromRestoration}
                  >
                    Back to portfolio
                  </button>
                </div>
              </div>
            ) : (
              <ModuleSkeleton moduleType={targetModule} />
            )}
          </main>
        </div>
      </div>
    );
  }

  // Section 4: Immediate Workspace Shell
  // When no project is open or session is unvalidated: render the portfolio dashboard with stable skeletons
  if (!currentProject || !currentUser) {
    return (
      <>
        <DashboardPage
          user={currentUser || PENDING_USER_SHELL}
          projects={currentUser ? projects : []}
          projectsStatus={!currentUser ? 'loading' : projectsStatus}
          projectsError={currentUser ? projectsError : null}
          onRetryProjects={() => void loadProjects(currentUser?.id, true)}
          onOpenProject={currentUser ? handleOpenProject : (() => {})}
          onPrefetchProject={(pId) => currentUser?.id && prefetchProjectData(pId, currentUser.id)}
          onCreateNewProject={() => setIsWizardOpen(true)}
          onDeleteProject={handleDeleteProject}
          onBulkDeleteProjects={handleBulkDeleteProjects}
          onLogout={logout}
          onUserUpdated={(updated) => setCurrentUser(updated)}
        />
        {isWizardOpen && currentUser && (
          <WizardErrorBoundary onCancel={() => setIsWizardOpen(false)}>
            <React.Suspense fallback={<WizardLoadingShell onCancel={() => setIsWizardOpen(false)} />}>
              <NewProjectWizard
                onProjectCreated={handleProjectCreated}
                onCancel={() => setIsWizardOpen(false)}
                userScope={currentUser?.id}
              />
            </React.Suspense>
          </WizardErrorBoundary>
        )}
      </>
    );
  }


  // Active Project Workspace Shell
  return (
    <div className="app-layout">
      {/* Sidebar with Navigation Memory and Speculative Prefetch */}
      <Sidebar
        currentProject={currentProject}
        activeModule={activeModule}
        onSelectModule={handleSelectModule}
        onPrefetchModule={(mod) => prefetchModule(currentProject.id, mod, currentUser?.id)}
        onBackToDashboard={handleBackToPortfolioFromRestoration}
        onCreateNewProject={() => setIsWizardOpen(true)}
        onExportFullPdf={() => api.exports.downloadFullProjectPdf(currentProject.id, currentProject.name)}
        moduleVersionBadges={moduleBadges}
      />

      <div className="main-wrapper" key={currentProject.id}>
        {/* Top Header */}
        <Header
          project={currentProject}
          user={currentUser || PENDING_USER_SHELL}
          onLogout={logout}
          onEditProject={() => handleSelectModule('overview')}
          onSelectModule={handleSelectModule}
          onUserUpdated={(updated) => setCurrentUser(updated)}
        />

        {/* Scrollable Workspace Body */}
        <div className="workspace-scroll-area">
          {moduleError && !moduleDetail && (
            <div className="card" role="alert" style={{ marginBottom: 20 }}>
              <p>{moduleError}</p>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => loadModuleContent(currentProject.id, activeModule, currentUser?.id, true)}
              >
                Retry loading
              </button>
            </div>
          )}

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

          <React.Suspense fallback={<ModuleSkeleton moduleType={activeModule} />}>
            {/* Stable loading design: Show skeleton when module is loading without cached data (Section 10) */}
            {moduleStatus === 'loading' && !moduleDetail ? (
              <ModuleSkeleton moduleType={activeModule} />
            ) : (
              <>
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
                    userScope={currentUser?.id}
                    hasMoreOlder={hasMoreCopilot}
                    isLoadingOlder={loadingOlderCopilot}
                    onLoadOlderMessages={handleLoadOlderCopilot}
                    onSendMessage={async (msg, tempId) => {
                      const projectId = currentProject.id;
                      const optimisticUserMsg: CopilotMessage = {
                        id: tempId,
                        role: 'user',
                        content: msg,
                        created_at: new Date().toISOString(),
                        status: 'sending'
                      };
                      setCopilotMessages(prev => [...prev, optimisticUserMsg]);

                      try {
                        const assistantMsg = await api.copilot.sendMessage(projectId, msg, tempId);
                        queryCache.invalidate(`copilot:page:${projectId}`);
                        if (isViewing(projectId, 'blueprint_copilot')) {
                          setCopilotMessages(prev => {
                            const updated = prev.map(m => m.id === tempId ? { ...m, status: 'saved' as const } : m);
                            return [...updated, assistantMsg];
                          });
                        }
                      } catch (err: any) {
                        if (isViewing(projectId, 'blueprint_copilot')) {
                          setCopilotMessages(prev =>
                            prev.map(m => m.id === tempId ? { ...m, status: 'failed' as const, error: err.message || 'Failed to send' } : m)
                          );
                        }
                        throw err;
                      }
                    }}
                    isLoading={moduleLoading}
                  />
                )}
              </>
            )}
          </React.Suspense>
        </div>
      </div>

      {/* New Project Wizard Modal - Lazy Loaded */}
      {isWizardOpen && (
        <WizardErrorBoundary onCancel={() => setIsWizardOpen(false)}>
          <React.Suspense fallback={<WizardLoadingShell onCancel={() => setIsWizardOpen(false)} />}>
            <NewProjectWizard
              onProjectCreated={handleProjectCreated}
              onCancel={() => setIsWizardOpen(false)}
              userScope={currentUser?.id}
            />
          </React.Suspense>
        </WizardErrorBoundary>
      )}

      {/* 5-Version Conflict Resolution Modal - Lazy Loaded */}
      {conflictModalOpen && conflictData && (
        <React.Suspense fallback={null}>
          <VersionConflictModal
            moduleTitle={conflictData.moduleTitle}
            existingVersions={conflictData.existingVersions}
            pendingInstruction={conflictData.pendingInstruction}
            onResolveReplace={handleResolveReplace}
            onCancel={() => setConflictModalOpen(false)}
            isLoading={moduleLoading}
          />
        </React.Suspense>
      )}
    </div>
  );
};

export default App;
