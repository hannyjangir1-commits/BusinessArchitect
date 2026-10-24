import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { api } from '../services/api';
import { queryCache } from '../services/queryCache';
import {
  saveNavDestination,
  getNavDestination,
  clearAllNavDestinations
} from '../services/navigationStorage';
import { LandingPage } from '../pages/LandingPage';
import { Sidebar, ModuleBadgeStatus } from '../components/Sidebar';
import { BlueprintCopilotModule } from '../components/BlueprintCopilotModule';
import { MarketResearchModule } from '../components/MarketResearchModule';
import { isMeaninglessPlaceholder } from '../utils/researchPlaceholders';
import { DashboardPage } from '../pages/DashboardPage';
import { User, Project, BusinessStage } from '../types';

const createMockProject = (id: string, name: string, stage: BusinessStage = 'Idea', generated_modules: string[] = []): Project => ({
  id,
  name,
  stage,
  description: 'Test project description',
  industry: 'Technology',
  active_module: 'execution_roadmap',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
});

describe('Batch 03.1 — Live Validation Fixes Regression Suite', () => {

  beforeEach(() => {
    vi.clearAllMocks();
    queryCache.clearAll();
    clearAllNavDestinations();
    localStorage.clear();
    sessionStorage.clear();
    window.history.replaceState({}, '', '/');
  });

  afterEach(() => {
    queryCache.clearAll();
    clearAllNavDestinations();
  });

  // =========================================================================
  // 1. Module Restoration & Portfolio Flash Prevention
  // =========================================================================
  describe('1. Module Restoration & Portfolio Flash Prevention', () => {
    it('renders neutral workspace shell with skeleton immediately on project URL while authentication is pending', async () => {
      window.history.replaceState({}, '', '/?project=proj-live&module=market_research');

      // Keep getMe unresolved to test pending state
      let resolveAuth: any;
      const authPromise = new Promise<{ user: User }>((resolve) => {
        resolveAuth = resolve;
      });
      vi.spyOn(api.auth, 'getMe').mockImplementation(() => authPromise as any);

      render(<App />);

      // Workspace shell must appear immediately
      expect(screen.getByText('Venture Atlas')).toBeDefined();
      // Skeleton for market_research must be displayed
      expect(screen.getByRole('status', { name: /loading market_research/i })).toBeDefined();

      // Portfolio flash must NOT occur:
      expect(screen.queryByText(/your venture portfolio/i)).toBeNull();
      expect(screen.queryByText(/welcome back, loading/i)).toBeNull();
      expect(screen.queryByText(/0 active ventures/i)).toBeNull();
      expect(screen.queryByText(/no tasks assigned yet/i)).toBeNull();

      // Resolve auth to clean up
      await act(async () => {
        resolveAuth({ user: { id: 'u1', username: 'alice', email: 'alice@example.com', created_at: '' } });
      });
    });

    it('does not reveal protected cached content before current-session validation', async () => {
      window.history.replaceState({}, '', '/?project=proj-secret&module=bmc');

      // Prepopulate cache with secret project data
      queryCache.setCached('project:proj-secret', {
        id: 'proj-secret',
        name: 'CLASSIFIED_PROJECT_NAME',
        description: 'Super secret confidential blueprint',
        stage: 'Growth'
      }, 60000);

      // Keep auth pending
      vi.spyOn(api.auth, 'getMe').mockImplementation(() => new Promise(() => {}));

      render(<App />);

      // Neutral shell is shown, but classified name is NOT revealed before session validation
      expect(screen.queryByText('CLASSIFIED_PROJECT_NAME')).toBeNull();
      expect(screen.queryByText('Super secret confidential blueprint')).toBeNull();
      expect(screen.getByRole('status', { name: /loading bmc/i })).toBeDefined();
    });

    it('restores valid URL destination after validation and populates content', async () => {
      window.history.replaceState({}, '', '/?project=proj-1&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const mockProject = createMockProject('proj-1', 'Valid Venture', 'MVP', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([mockProject] as any);
      vi.spyOn(api.projects, 'get').mockResolvedValue(mockProject as any);
      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-bmc-1',
        project_id: 'proj-1',
        module_type: 'bmc',
        data: { value_propositions: ['Real Value Proposition'] }
      } as any);

      render(<App />);

      await waitFor(() => {
        expect(screen.getAllByText('Valid Venture').length).toBeGreaterThan(0);
      });

      expect(api.modules.get).toHaveBeenCalledWith('proj-1', 'bmc');
    });

    it('explicit URL destination takes precedence over saved preference', async () => {
      window.history.replaceState({}, '', '/?project=proj-explicit&module=idea_validator');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      // User has a different saved destination in storage
      saveNavDestination('user-1', 'proj-saved', 'execution_roadmap');

      const projExplicit = createMockProject('proj-explicit', 'Explicit Project', 'Idea', ['idea_validator']);
      const projSaved = createMockProject('proj-saved', 'Saved Project', 'Growth', ['execution_roadmap']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projExplicit, projSaved] as any);
      vi.spyOn(api.projects, 'get').mockImplementation(async (id) => (id === 'proj-explicit' ? projExplicit : projSaved) as any);
      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-1',
        project_id: 'proj-explicit',
        module_type: 'idea_validator',
        data: { score: 85 }
      } as any);

      render(<App />);

      await waitFor(() => {
        expect(screen.getAllByText('Explicit Project').length).toBeGreaterThan(0);
      });

      // Explicit URL module was loaded, not the saved execution_roadmap
      expect(api.modules.get).toHaveBeenCalledWith('proj-explicit', 'idea_validator');
      expect(screen.queryByText('Saved Project')).toBeNull();
    });

    it('falls back safely to dashboard when project is invalid or deleted', async () => {
      window.history.replaceState({}, '', '/?project=deleted-project&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const realProject = createMockProject('proj-real', 'Real Venture');

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      // projects.list does NOT include deleted-project
      vi.spyOn(api.projects, 'list').mockResolvedValue([realProject] as any);

      render(<App />);

      await waitFor(() => {
        expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
        expect(screen.getAllByText('Real Venture').length).toBeGreaterThan(0);
      });

      expect(window.location.search).toBe('?workspace=true');
    });

    it('returns to public landing page if session check is rejected', async () => {
      window.history.replaceState({}, '', '/?project=proj-1&module=bmc');

      vi.spyOn(api.auth, 'getMe').mockRejectedValue(new Error('Unauthorized'));

      render(<App />);

      await waitFor(() => {
        expect(screen.getAllByText(/sign in/i).length).toBeGreaterThan(0);
      });

      expect(screen.queryByText(/your venture portfolio/i)).toBeNull();
    });

    it('does not allow slow old requests to overwrite restored destination in true navigation race', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const projA = createMockProject('proj-A', 'Venture Alpha', 'Idea', ['bmc']);
      const projB = createMockProject('proj-B', 'Venture Beta', 'Growth', ['tech_stack']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projA, projB] as any);

      let resolveProjA: (value: any) => void;
      const projAPromise = new Promise((resolve) => { resolveProjA = resolve; });

      const getSpy = vi.spyOn(api.projects, 'get').mockImplementation(async (id) => {
        if (id === 'proj-A') {
          return projAPromise as any;
        }
        if (id === 'proj-B') {
          return projB as any;
        }
        throw new Error('Not found');
      });

      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-tech',
        project_id: 'proj-B',
        module_type: 'tech_stack',
        data: { frontend: ['React'] }
      } as any);

      // 1. Initial destination is proj-A. Request A actually starts!
      window.history.replaceState({}, '', '/?project=proj-A&module=bmc');
      render(<App />);

      // Verify request A has actually started
      await waitFor(() => {
        expect(getSpy).toHaveBeenCalledWith('proj-A');
      });

      // 2. User navigates to proj-B (via popstate)
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-B&module=tech_stack');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // 3. Request B starts and resolves
      await waitFor(() => {
        expect(getSpy).toHaveBeenCalledWith('proj-B');
      });

      await waitFor(() => {
        expect(screen.getAllByText('Venture Beta').length).toBeGreaterThan(0);
      });

      // 4. Request A resolves afterward!
      await act(async () => {
        resolveProjA(projA);
      });

      // 5. Venture Beta remains visible and stored as destination
      expect(screen.getAllByText('Venture Beta').length).toBeGreaterThan(0);
      expect(screen.queryByText('Venture Alpha')).toBeNull();
      const savedDest = getNavDestination('user-1');
      expect(savedDest?.projectId).toBe('proj-B');

      // Assert that both requests were actually called
      expect(getSpy).toHaveBeenCalledWith('proj-A');
      expect(getSpy).toHaveBeenCalledWith('proj-B');
    });

    it('switches between fully loaded projects: Project A content loads, navigates to B, B module executes and renders distinctive content while A content is cleared', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const projA = createMockProject('proj-A', 'Venture Alpha', 'MVP', ['bmc']);
      const projB = createMockProject('proj-B', 'Venture Beta', 'Growth', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projA, projB] as any);
      vi.spyOn(api.projects, 'get').mockImplementation(async (id) => {
        if (id === 'proj-A') return projA as any;
        if (id === 'proj-B') return projB as any;
        throw new Error('Not found');
      });

      const moduleSpy = vi.spyOn(api.modules, 'get').mockImplementation(async (pId, mod) => {
        if (pId === 'proj-A' && mod === 'bmc') {
          return {
            id: 'mod-bmc-A',
            project_id: 'proj-A',
            module_type: 'bmc',
            data: { value_propositions: ['Alpha Core Value'] }
          } as any;
        }
        if (pId === 'proj-B' && mod === 'bmc') {
          return {
            id: 'mod-bmc-B',
            project_id: 'proj-B',
            module_type: 'bmc',
            data: { value_propositions: ['Beta Core Value'] }
          } as any;
        }
        return { id: 'mod', project_id: pId, module_type: mod, data: {} } as any;
      });

      // 1. Initial load: Project A
      window.history.replaceState({}, '', '/?project=proj-A&module=bmc');
      render(<App />);

      // A content loads completely
      await waitFor(() => {
        expect(screen.getAllByText('Venture Alpha').length).toBeGreaterThan(0);
        expect(screen.getByText('Alpha Core Value')).toBeDefined();
      });
      expect(moduleSpy).toHaveBeenCalledWith('proj-A', 'bmc');

      // 2. Navigation to B starts via URL and popstate
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-B&module=bmc');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // 3. B metadata resolves, 4. B module request actually executes, 5. Distinctive B content renders
      await waitFor(() => {
        expect(screen.getAllByText('Venture Beta').length).toBeGreaterThan(0);
        expect(screen.getByText('Beta Core Value')).toBeDefined();
      });

      // Verify B module request actually ran
      expect(moduleSpy).toHaveBeenCalledWith('proj-B', 'bmc');

      // 6. A content is absent
      expect(screen.queryByText('Alpha Core Value')).toBeNull();

      // 7. Navigation storage identifies B
      const savedDest = getNavDestination('user-1');
      expect(savedDest?.projectId).toBe('proj-B');
      expect(savedDest?.module).toBe('bmc');
    });

    it('switching from Project A to Project B when B metadata fails: shows inline error and working Retry restores B', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const projA = createMockProject('proj-A', 'Venture Alpha', 'MVP', ['bmc']);
      const projB = createMockProject('proj-B', 'Venture Beta', 'Growth', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projA, projB] as any);

      let bFailOnce = true;
      vi.spyOn(api.projects, 'get').mockImplementation(async (id) => {
        if (id === 'proj-A') return projA as any;
        if (id === 'proj-B') {
          if (bFailOnce) {
            bFailOnce = false;
            throw new Error('503 Service Unavailable for Beta');
          }
          return projB as any;
        }
        throw new Error('Not found');
      });

      vi.spyOn(api.modules, 'get').mockImplementation(async (pId, mod) => {
        if (pId === 'proj-A') {
          return { id: 'mod-A', project_id: 'proj-A', module_type: mod, data: { value_propositions: ['ALPHA_VALUE'] } } as any;
        }
        if (pId === 'proj-B') {
          return { id: 'mod-B', project_id: 'proj-B', module_type: mod, data: { value_propositions: ['BETA_RECOVERED_VALUE'] } } as any;
        }
        return { id: 'm', project_id: pId, module_type: mod, data: {} } as any;
      });

      // 1. Fully load Project A
      window.history.replaceState({}, '', '/?project=proj-A&module=bmc');
      render(<App />);

      await waitFor(() => {
        expect(screen.getByText('ALPHA_VALUE')).toBeDefined();
      });

      // 2. Navigate to Project B
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-B&module=bmc');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // 3. Inline error appears, old A content is cleared
      await waitFor(() => {
        expect(screen.getByText('Unable to load workspace')).toBeDefined();
        expect(screen.getByText('503 Service Unavailable for Beta')).toBeDefined();
      });
      expect(screen.queryByText('ALPHA_VALUE')).toBeNull();

      // 4. Click Retry
      const retryBtn = screen.getByRole('button', { name: /^retry$/i });
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      // 5. Successful retry populates Project B and its module content
      await waitFor(() => {
        expect(screen.getAllByText('Venture Beta').length).toBeGreaterThan(0);
        expect(screen.getByText('BETA_RECOVERED_VALUE')).toBeDefined();
      });
    });

    it('navigating A -> B -> C with out-of-order responses preserves latest destination C', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const projA = createMockProject('proj-A', 'Project A', 'Idea', ['bmc']);
      const projB = createMockProject('proj-B', 'Project B', 'MVP', ['bmc']);
      const projC = createMockProject('proj-C', 'Project C', 'Growth', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projA, projB, projC] as any);

      let resolveProjB: (val: any) => void;
      const bPromise = new Promise((resolve) => { resolveProjB = resolve; });

      vi.spyOn(api.projects, 'get').mockImplementation(async (id) => {
        if (id === 'proj-A') return projA as any;
        if (id === 'proj-B') return bPromise as any;
        if (id === 'proj-C') return projC as any;
        throw new Error('Not found');
      });

      vi.spyOn(api.modules, 'get').mockImplementation(async (pId, mod) => {
        if (pId === 'proj-A') return { id: 'mA', project_id: 'proj-A', module_type: mod, data: { value_propositions: ['CONTENT_A'] } } as any;
        if (pId === 'proj-B') return { id: 'mB', project_id: 'proj-B', module_type: mod, data: { value_propositions: ['CONTENT_B'] } } as any;
        if (pId === 'proj-C') return { id: 'mC', project_id: 'proj-C', module_type: mod, data: { value_propositions: ['CONTENT_C'] } } as any;
        return { id: 'm', project_id: pId, module_type: mod, data: {} } as any;
      });

      // 1. Fully load Project A
      window.history.replaceState({}, '', '/?project=proj-A&module=bmc');
      render(<App />);

      await waitFor(() => {
        expect(screen.getByText('CONTENT_A')).toBeDefined();
      });

      // 2. Navigate to B (starts request B, which stays pending)
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-B&module=bmc');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // 3. Before B finishes, user navigates to C
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-C&module=bmc');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // C resolves and renders
      await waitFor(() => {
        expect(screen.getAllByText('Project C').length).toBeGreaterThan(0);
        expect(screen.getByText('CONTENT_C')).toBeDefined();
      });

      // 4. B finishes late
      await act(async () => {
        resolveProjB(projB);
      });

      // 5. C remains visible, B does NOT overwrite C
      expect(screen.getByText('CONTENT_C')).toBeDefined();
      expect(screen.queryByText('CONTENT_B')).toBeNull();
      expect(screen.queryByText('CONTENT_A')).toBeNull();
      expect(getNavDestination('user-1')?.projectId).toBe('proj-C');
    });

    it('leaving for portfolio while B is pending prevents late completion from reopening B', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const projA = createMockProject('proj-A', 'Project A', 'Idea', ['bmc']);
      const projB = createMockProject('proj-B', 'Project B', 'MVP', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([projA, projB] as any);

      let resolveProjB: (val: any) => void;
      const bPromise = new Promise((resolve) => { resolveProjB = resolve; });

      vi.spyOn(api.projects, 'get').mockImplementation(async (id) => {
        if (id === 'proj-A') return projA as any;
        if (id === 'proj-B') return bPromise as any;
        throw new Error('Not found');
      });

      vi.spyOn(api.modules, 'get').mockImplementation(async (pId, mod) => {
        if (pId === 'proj-A') return { id: 'mA', project_id: 'proj-A', module_type: mod, data: { value_propositions: ['CONTENT_A'] } } as any;
        if (pId === 'proj-B') return { id: 'mB', project_id: 'proj-B', module_type: mod, data: { value_propositions: ['CONTENT_B'] } } as any;
        return { id: 'm', project_id: pId, module_type: mod, data: {} } as any;
      });

      // 1. Fully load Project A
      window.history.replaceState({}, '', '/?project=proj-A&module=bmc');
      const { container } = render(<App />);

      await waitFor(() => {
        expect(screen.getByText('CONTENT_A')).toBeDefined();
      });

      // 2. Navigate to B (B is pending)
      await act(async () => {
        window.history.pushState({}, '', '/?project=proj-B&module=bmc');
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // 3. User leaves for portfolio by clicking Back to Dashboard
      const backBtn = (container.querySelector('.back-to-dashboard-btn') as HTMLElement) || screen.getByRole('button', { name: /back to/i });
      await act(async () => {
        fireEvent.click(backBtn);
      });

      await waitFor(() => {
        expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
      });

      // 4. B metadata finishes late
      await act(async () => {
        resolveProjB(projB);
      });

      // 5. Portfolio remains visible, Project B workspace is NOT reopened
      expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
      expect(container.querySelector('.workspace-scroll-area')).toBeNull();
      expect(screen.queryByText('CONTENT_B')).toBeNull();
      expect(window.location.search).toBe('?workspace=true');
    });

    it('auth succeeds, list includes p1, detail rejects: shows inline recoverable error and retry works', async () => {
      window.history.replaceState({}, '', '/?project=p1&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const proj1 = createMockProject('p1', 'Alpha Venture', 'Idea', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([proj1] as any);

      const getSpy = vi.spyOn(api.projects, 'get')
        .mockRejectedValueOnce(new Error('Network gateway timeout'))
        .mockResolvedValue(proj1 as any);

      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-bmc',
        project_id: 'p1',
        module_type: 'bmc',
        data: { value: 'Loaded BMC' }
      } as any);

      render(<App />);

      // 1. Loading skeleton disappears, inline error appears
      await waitFor(() => {
        expect(screen.getByText('Unable to load workspace')).toBeDefined();
        expect(screen.getByText('Network gateway timeout')).toBeDefined();
      });

      // No permanent loading skeleton
      expect(screen.queryByRole('status', { name: /loading bmc/i })).toBeNull();

      // Retry and Back to portfolio buttons appear
      const retryBtn = screen.getByRole('button', { name: /^retry$/i });
      const backBtn = screen.getByRole('button', { name: /back to portfolio/i });
      expect(retryBtn).toBeDefined();
      expect(backBtn).toBeDefined();

      // 2. Click Retry: successful retry populates requested module
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      await waitFor(() => {
        expect(screen.getAllByText('Alpha Venture').length).toBeGreaterThan(0);
      });

      expect(getSpy).toHaveBeenCalledTimes(2);
      expect(api.modules.get).toHaveBeenCalledWith('p1', 'bmc');
    });

    it('auth succeeds, list includes p1, detail rejects: back to portfolio clears restoration intent', async () => {
      window.history.replaceState({}, '', '/?project=p1&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const proj1 = createMockProject('p1', 'Alpha Venture');

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([proj1] as any);
      vi.spyOn(api.projects, 'get').mockRejectedValueOnce(new Error('Network failure'));

      render(<App />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load workspace')).toBeDefined();
      });

      const backBtn = screen.getByRole('button', { name: /back to portfolio/i });
      await act(async () => {
        fireEvent.click(backBtn);
      });

      // User returns to portfolio dashboard
      await waitFor(() => {
        expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
        expect(screen.getAllByText('Alpha Venture').length).toBeGreaterThan(0);
      });

      expect(window.location.search).toBe('?workspace=true');
    });

    it('project-list request fails temporarily: deep-link intent is retained, user sees recoverable error, retry restores destination', async () => {
      window.history.replaceState({}, '', '/?project=p1&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const proj1 = createMockProject('p1', 'Alpha Venture', 'Idea', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);

      const listSpy = vi.spyOn(api.projects, 'list')
        .mockRejectedValueOnce(new Error('Failed to reach server'))
        .mockResolvedValue([proj1] as any);

      vi.spyOn(api.projects, 'get').mockResolvedValue(proj1 as any);
      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-bmc',
        project_id: 'p1',
        module_type: 'bmc',
        data: { value: 'BMC Data' }
      } as any);

      render(<App />);

      // Deep link intent is retained, user sees recoverable error in neutral shell
      await waitFor(() => {
        expect(screen.getByText('Unable to load workspace')).toBeDefined();
        expect(screen.getByText(/failed to load projects/i)).toBeDefined();
      });

      expect(window.location.search).toBe('?project=p1&module=bmc');

      // Click Retry
      const retryBtn = screen.getByRole('button', { name: /^retry$/i });
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      // Restores destination
      await waitFor(() => {
        expect(screen.getAllByText('Alpha Venture').length).toBeGreaterThan(0);
      });

      expect(listSpy).toHaveBeenCalledTimes(2);
      expect(api.modules.get).toHaveBeenCalledWith('p1', 'bmc');
    });

    it('navigation away during retry: late completion cannot overwrite the new destination', async () => {
      window.history.replaceState({}, '', '/?project=p1&module=bmc');

      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const proj1 = createMockProject('p1', 'Alpha Venture', 'Idea', ['bmc']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([proj1] as any);

      let resolveRetry: (value: any) => void;
      const retryPromise = new Promise((resolve) => { resolveRetry = resolve; });

      vi.spyOn(api.projects, 'get')
        .mockRejectedValueOnce(new Error('Initial failure'))
        .mockImplementationOnce(() => retryPromise as any);

      const { container } = render(<App />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load workspace')).toBeDefined();
      });

      // 1. Click Retry
      const retryBtn = screen.getByRole('button', { name: /^retry$/i });
      await act(async () => {
        fireEvent.click(retryBtn);
      });

      // 2. While retry is pending, user navigates away by clicking Back to Dashboard
      const backBtn = (container.querySelector('.back-to-dashboard-btn') as HTMLElement) || screen.getByRole('button', { name: /back to/i });
      await act(async () => {
        fireEvent.click(backBtn);
      });

      await waitFor(() => {
        expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
      });

      // 3. Late retry completion finishes afterward
      await act(async () => {
        resolveRetry(proj1);
      });

      // 4. Portfolio remains visible, late completion does NOT reopen project workspace
      expect(screen.getByText(/your venture portfolio/i)).toBeDefined();
      expect(container.querySelector('.workspace-scroll-area')).toBeNull();
      expect(window.location.search).toBe('?workspace=true');
    });
  });

  // =========================================================================
  // 2. Dashboard Stats & Placeholders
  // =========================================================================
  describe('2. Dashboard Stats & Placeholders', () => {
    it('renders dashes (—) instead of 0s while dashboard projects are loading', () => {
      const pendingUser: User = { id: 'pending', username: 'Loading...', email: '', role: 'user', created_at: '' };

      render(
        <DashboardPage
          user={pendingUser}
          projects={[]}
          projectsStatus="loading"
          projectsError={null}
          onRetryProjects={() => {}}
          onOpenProject={() => {}}
          onCreateNewProject={() => {}}
          onDeleteProject={async () => {}}
          onBulkDeleteProjects={async () => {}}
          onLogout={async () => {}}
        />
      );

      // Must not say "Welcome back, Loading..."
      expect(screen.queryByText(/welcome back, loading/i)).toBeNull();
      expect(screen.getByText(/welcome to your enterprise business blueprints/i)).toBeDefined();

      // Stats should show dashes, NOT "0 Active Ventures" or "0 Generated Modules"
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBeGreaterThanOrEqual(2);
      expect(screen.queryByText('0 Active Ventures')).toBeNull();
      expect(screen.queryByText('0 Generated Modules')).toBeNull();
      expect(screen.queryByText('No tasks assigned yet')).toBeNull();
    });

    it('renders real 0 counts only when projectsStatus is confirmed success-empty', () => {
      const realUser: User = { id: 'u1', username: 'sarah', email: 'sarah@test.com', created_at: '' };

      render(
        <DashboardPage
          user={realUser}
          projects={[]}
          projectsStatus="success-empty"
          projectsError={null}
          onRetryProjects={() => {}}
          onOpenProject={() => {}}
          onCreateNewProject={() => {}}
          onDeleteProject={async () => {}}
          onBulkDeleteProjects={async () => {}}
          onLogout={async () => {}}
        />
      );

      // Now real 0 values are legitimately confirmed
      expect(screen.getByText(/Welcome back,/)).toBeDefined();
      expect(screen.getAllByText('sarah').length).toBeGreaterThan(0);
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // 3. Sidebar Generation Badges
  // =========================================================================
  describe('3. Sidebar Generation Badges', () => {
    it('omits badge and does not display "Not generated" while metadata status is unknown or loading', () => {
      const project = createMockProject('p1', 'Alpha Venture');
      const badges: Record<string, { version?: string; isGenerated?: boolean; status?: ModuleBadgeStatus }> = {
        overview: { version: 'V1', status: 'generated' },
        bmc: { version: 'V1', status: 'unknown' },
        tech_stack: { version: 'V1', status: 'loading' },
        idea_validator: { version: 'V1', status: 'not-generated' }
      };

      const { container } = render(
        <Sidebar
          currentProject={project}
          activeModule="overview"
          onSelectModule={() => {}}
          onBackToDashboard={() => {}}
          onCreateNewProject={() => {}}
          onExportFullPdf={() => {}}
          moduleVersionBadges={badges}
        />
      );

      const bmcBtn = container.querySelector('[data-module-id="bmc"]');
      const techBtn = container.querySelector('[data-module-id="tech_stack"]');
      const ideaBtn = container.querySelector('[data-module-id="idea_validator"]');

      // bmc and tech_stack should have NO status dot (omitted while unknown/loading)
      expect(bmcBtn?.querySelector('.status-dot-gray')).toBeNull();
      expect(bmcBtn?.querySelector('.status-dot-green')).toBeNull();
      expect(techBtn?.querySelector('.status-dot-gray')).toBeNull();

      // Confirmed not-generated module DOES have gray dot
      expect(ideaBtn?.querySelector('.status-dot-gray')).not.toBeNull();
    });

    it('describes Blueprint Copilot as interactive assistant, never "Not generated"', () => {
      const project = createMockProject('p1', 'Alpha Venture');

      const { container } = render(
        <Sidebar
          currentProject={project}
          activeModule="overview"
          onSelectModule={() => {}}
          onBackToDashboard={() => {}}
          onCreateNewProject={() => {}}
          onExportFullPdf={() => {}}
          moduleVersionBadges={{}}
        />
      );

      const copilotBtn = container.querySelector('[data-module-id="blueprint_copilot"]');
      expect(copilotBtn?.getAttribute('aria-label')).toContain('Interactive assistant');
      expect(copilotBtn?.getAttribute('aria-label')).not.toContain('Not generated');
      expect(copilotBtn?.querySelector('.status-dot-gray')).toBeNull();
    });

    it('preserves confirmed generated status even if metadata refresh fails', () => {
      const project = createMockProject('p1', 'Alpha Venture');
      // When status is 'error', it should not display as 'not-generated'
      const badges: Record<string, { version?: string; status?: ModuleBadgeStatus }> = {
        bmc: { version: 'V1', status: 'generated' },
        tech_stack: { version: 'V1', status: 'error' }
      };

      const { container } = render(
        <Sidebar
          currentProject={project}
          activeModule="overview"
          onSelectModule={() => {}}
          onBackToDashboard={() => {}}
          onCreateNewProject={() => {}}
          onExportFullPdf={() => {}}
          moduleVersionBadges={badges}
        />
      );

      const bmcBtn = container.querySelector('[data-module-id="bmc"]');
      const techBtn = container.querySelector('[data-module-id="tech_stack"]');

      expect(bmcBtn?.querySelector('.status-dot-green')).not.toBeNull();
      // Error status must NOT show a gray dot (not-generated)
      expect(techBtn?.querySelector('.status-dot-gray')).toBeNull();
    });

    it('metadata refresh failure preserves confirmed generated badges in workspace without resetting', async () => {
      const mockUser: User = { id: 'user-1', username: 'founder', email: 'founder@test.com', created_at: '' };
      const proj = createMockProject('p1', 'Active Venture', 'MVP', ['bmc', 'tech_stack']);

      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser } as any);
      vi.spyOn(api.projects, 'list').mockResolvedValue([proj] as any);
      vi.spyOn(api.projects, 'get').mockResolvedValue(proj as any);
      vi.spyOn(api.modules, 'get').mockResolvedValue({
        id: 'mod-1',
        project_id: 'p1',
        module_type: 'bmc',
        data: { value: 'BMC Data' }
      } as any);

      window.history.replaceState({}, '', '/?project=p1&module=bmc');
      const { container } = render(<App />);

      await waitFor(() => {
        expect(screen.getAllByText('Active Venture').length).toBeGreaterThan(0);
      });

      // Confirm generated badge is present on non-active generated module tech_stack
      const techBtn = container.querySelector('[data-module-id="tech_stack"]');
      expect(techBtn?.querySelector('.status-dot-green')).not.toBeNull();

      // Now simulate a background metadata refresh failure
      vi.spyOn(api.projects, 'get').mockRejectedValueOnce(new Error('500 Server Error'));

      // Trigger popstate on same project
      await act(async () => {
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // Project remains active (not cleared)
      expect(screen.getAllByText('Active Venture').length).toBeGreaterThan(0);

      // Previously confirmed generated badge remains generated (not reset to INITIAL_MODULE_BADGES or not-generated)
      const techBtnAfter = container.querySelector('[data-module-id="tech_stack"]');
      expect(techBtnAfter?.querySelector('.status-dot-green')).not.toBeNull();
    });
  });

  // =========================================================================
  // 4. Authentication Dialog Escape & Focus Trap
  // =========================================================================
  describe('4. Authentication Dialog Escape & Focus Trap', () => {
    it('closes on Escape key press in sign-in mode and restores focus to opener', () => {
      render(<LandingPage onAuthenticated={() => {}} />);

      const signInBtn = screen.getByRole('button', { name: /^sign in$/i });
      signInBtn.focus();
      expect(document.activeElement).toBe(signInBtn);

      fireEvent.click(signInBtn);
      expect(screen.getByRole('dialog')).toBeDefined();

      // Press Escape
      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

      // Dialog is dismissed
      expect(screen.queryByRole('dialog')).toBeNull();
      // Focus restored to opener
      expect(document.activeElement).toBe(signInBtn);
    });

    it('closes on Escape key press in registration mode and restores focus to opener', () => {
      render(<LandingPage onAuthenticated={() => {}} />);

      const getStartedBtn = screen.getByRole('button', { name: /^get started$/i });
      getStartedBtn.focus();

      fireEvent.click(getStartedBtn);
      expect(screen.getByRole('dialog')).toBeDefined();
      expect(screen.getByRole('heading', { name: /create free account/i })).toBeDefined();

      // Press Escape
      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(getStartedBtn);
    });

    it('clicking inside modal card does not dismiss dialog, clicking overlay dismisses', () => {
      const { container } = render(<LandingPage onAuthenticated={() => {}} />);

      const signInBtn = screen.getByRole('button', { name: /^sign in$/i });
      fireEvent.click(signInBtn);

      const modalCard = screen.getByRole('dialog');
      fireEvent.click(modalCard);

      expect(screen.getByRole('dialog')).toBeDefined();

      // Clicking backdrop/overlay dismisses dialog
      const overlay = container.querySelector('.modal-overlay')!;
      fireEvent.click(overlay);
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  });

  // =========================================================================
  // 5. Copilot Markdown Rendering
  // =========================================================================
  describe('5. Copilot Markdown Rendering', () => {
    const fixtureText = `## Actions for tomorrow
1. Set up the booking profile.
   - Add the service menu.
   - Add opening hours.
2. Print local flyers.
3. Visit two customer locations.
---
## Missing evidence
- Customer willingness to pay
- Actual travel time`;

    it('renders horizontal rule, contiguous ordered list, sub-bullets, and headings semantically', () => {
      const messages = [
        {
          id: 'msg-1',
          project_id: 'p1',
          role: 'assistant' as const,
          content: fixtureText,
          created_at: '2026-01-01T00:00:00Z'
        }
      ];

      const { container } = render(
        <BlueprintCopilotModule
          project={createMockProject('p1', 'Alpha')}
          messages={messages}
          onSendMessage={async () => {}}
          isLoading={false}
        />
      );

      // Verify horizontal rule <hr>
      expect(container.querySelector('hr')).not.toBeNull();
      expect(container.innerHTML).not.toContain('<p>---</p>');

      // Verify contiguous ordered list <ol>
      const olElements = container.querySelectorAll('ol');
      expect(olElements.length).toBe(1); // exactly one contiguous <ol>, not split into multiple lists!

      // Three list items in the ordered list
      const olListItems = olElements[0].querySelectorAll(':scope > li');
      expect(olListItems.length).toBe(3);
      expect(olListItems[0].textContent).toContain('Set up the booking profile.');
      expect(olListItems[1].textContent).toContain('Print local flyers.');
      expect(olListItems[2].textContent).toContain('Visit two customer locations.');

      // Sub-bullets inside the first <li>
      const subUl = olListItems[0].querySelector('ul');
      expect(subUl).not.toBeNull();
      const subItems = subUl!.querySelectorAll('li');
      expect(subItems.length).toBe(2);
      expect(subItems[0].textContent).toContain('Add the service menu.');
      expect(subItems[1].textContent).toContain('Add opening hours.');

      // Headings
      expect(screen.getByRole('heading', { name: 'Actions for tomorrow' })).toBeDefined();
      expect(screen.getByRole('heading', { name: 'Missing evidence' })).toBeDefined();
    });

    it('rejects unsafe javascript: links and prevents raw HTML execution', () => {
      const maliciousText = `Check [Unsafe Link](javascript:alert('pwned')) and [Safe Link](https://example.com) and <script>alert('xss')</script>`;

      const messages = [
        {
          id: 'msg-sec',
          project_id: 'p1',
          role: 'assistant' as const,
          content: maliciousText,
          created_at: '2026-01-01T00:00:00Z'
        }
      ];

      const { container } = render(
        <BlueprintCopilotModule
          project={createMockProject('p1', 'Alpha')}
          messages={messages}
          onSendMessage={async () => {}}
          isLoading={false}
        />
      );

      // javascript: link should NOT be an <a> with href javascript:
      const unsafeLinks = container.querySelectorAll('a[href^="javascript:"]');
      expect(unsafeLinks.length).toBe(0);

      // Safe link is preserved
      const safeLink = container.querySelector('a[href="https://example.com"]');
      expect(safeLink).not.toBeNull();
      expect(safeLink?.getAttribute('rel')).toBe('noopener noreferrer');

      // Script tag is escaped and not executed
      expect(container.querySelector('script')).toBeNull();
    });
  });

  // =========================================================================
  // 6. Market Research Meaningless Placeholder Detection
  // =========================================================================
  describe('6. Market Research Meaningless Placeholder Detection', () => {
    it('correctly classifies exact known placeholders and preserves real entries', () => {
      expect(isMeaninglessPlaceholder('Opportunity 1')).toBe(true);
      expect(isMeaninglessPlaceholder('opportunity 2')).toBe(true);
      expect(isMeaninglessPlaceholder('Threat 1')).toBe(true);
      expect(isMeaninglessPlaceholder('gap 1')).toBe(true);
      expect(isMeaninglessPlaceholder('Core Differentiator 1')).toBe(true);

      // Real entries with numbers must NOT be suppressed
      expect(isMeaninglessPlaceholder('Tier 1 enterprise cloud migration opportunity')).toBe(false);
      expect(isMeaninglessPlaceholder('High threat of competitor reaction in Q3')).toBe(false);
      expect(isMeaninglessPlaceholder('50% cost advantage in manufacturing')).toBe(false);
      expect(isMeaninglessPlaceholder('1 opportunity in European expansion')).toBe(false);
    });

    it('replaces placeholder-only lists with honest empty states while preserving real entries and warnings', () => {
      const placeholderData = {
        opportunities: ['Opportunity 1', 'Opportunity 2'],
        threats: ['Threat 1'],
        research_gaps: ['Gap 1'],
        competitor_profiles: [
          { name: 'Acme Corp', market_share_estimate: '10%', strengths: ['Core Differentiator 1'], weaknesses: [], pricing_model: 'Fixed' }
        ]
      };

      const detail = {
        id: 'mr-1',
        project_id: 'p1',
        module_type: 'market_research',
        data: {
          ...placeholderData,
          provenance_note: 'Limited data available in secondary tier research'
        }
      };

      render(
        <MarketResearchModule
          project={createMockProject('p1', 'Alpha')}
          moduleDetail={detail as any}
          onGenerate={async () => {}}
          onExportPdf={() => {}}
          isLoading={false}
        />
      );

      // Honest empty states must be displayed
      expect(screen.getByText('No supported opportunities were identified in this result.')).toBeDefined();
      expect(screen.getByText('No supported threats were identified in this result.')).toBeDefined();
      expect(screen.getByText('No specific research gaps were provided.')).toBeDefined();

      // Literal placeholders must NOT be presented as substantive research
      expect(screen.queryByText('Opportunity 1')).toBeNull();
      expect(screen.queryByText('Threat 1')).toBeNull();
      expect(screen.queryByText('Gap 1')).toBeNull();

      // Evidence warnings remain visible
      expect(screen.getByText(/Limited data available in secondary tier research/i)).toBeDefined();
    });

    it('renders real, substantive entries alongside evidence notes', () => {
      const realData = {
        opportunities: ['High demand for AI-driven logistics optimization in Southeast Asia'],
        threats: ['Incumbent vendors possess established enterprise sales distribution'],
        research_gaps: ['Willingness to pay in tier-2 regional hubs remains unverified'],
        competitor_profiles: [
          {
            name: 'LogiGlobal',
            market_share_estimate: '15%',
            strengths: ['Proprietary route engine with sub-second recalculation'],
            weaknesses: ['High enterprise pricing'],
            pricing_model: 'Subscription'
          }
        ]
      };

      const detail = {
        id: 'mr-2',
        project_id: 'p1',
        module_type: 'market_research',
        data: realData
      };

      render(
        <MarketResearchModule
          project={createMockProject('p1', 'Alpha')}
          moduleDetail={detail as any}
          onGenerate={async () => {}}
          onExportPdf={() => {}}
          isLoading={false}
        />
      );

      expect(screen.getByText('High demand for AI-driven logistics optimization in Southeast Asia')).toBeDefined();
      expect(screen.getByText('Incumbent vendors possess established enterprise sales distribution')).toBeDefined();
      expect(screen.getByText('Willingness to pay in tier-2 regional hubs remains unverified')).toBeDefined();
      expect(screen.getByText(/Proprietary route engine with sub-second recalculation/)).toBeDefined();
    });
  });
});
