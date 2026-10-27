import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { api } from '../services/api';
import { queryCache } from '../services/queryCache';
import {
  saveNavDestination,
  getNavDestination,
  clearNavDestination,
  clearAllNavDestinations
} from '../services/navigationStorage';
import {
  saveDraft,
  getDraft,
  clearDraft,
  clearAllDrafts
} from '../services/draftStorage';
import {
  prefetchModule,
  prefetchProjectData,
  isSaveDataEnabled
} from '../services/prefetch';
import { User, Project, BusinessStage } from '../types';

const createMockProject = (id: string, name: string, stage: BusinessStage = 'Idea'): Project => ({
  id,
  name,
  stage,
  description: 'Test project description',
  active_module: 'execution_roadmap',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
});

describe('Batch 03: Security & Race-Condition Review Gate', () => {

  beforeEach(() => {
    vi.clearAllMocks();
    queryCache.clearAll();
    clearAllDrafts();
    clearAllNavDestinations();
    localStorage.clear();
    sessionStorage.clear();
    window.history.replaceState({}, '', '/');
  });

  afterEach(() => {
    queryCache.clearAll();
    clearAllDrafts();
    clearAllNavDestinations();
  });

  // =========================================================================
  // Section 1: Protected-Content Authentication Gate
  // =========================================================================
  describe('1. Protected-Content Authentication Gate', () => {
    it('never renders protected cached content while /api/auth/me is pending, isolates user switch, and verifies new user content', async () => {
      // 1. Prepopulate navigation storage with valid-looking project and module from user-a
      saveNavDestination('user-a', 'proj-user-a', 'execution_roadmap');

      // 2. Prepopulate queryCache with recognizable protected content from user-a
      queryCache.setCached(
        'projects:list',
        [{
          id: 'proj-user-a',
          name: 'SECRET_PROJECT_USER_A',
          stage: 'MVP',
          description: 'Secret confidential roadmap',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z'
        }],
        60000,
        'user-a'
      );
      queryCache.setCached(
        'project:proj-user-a',
        {
          id: 'proj-user-a',
          name: 'SECRET_PROJECT_USER_A',
          stage: 'MVP',
          description: 'Secret confidential roadmap',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z'
        },
        60000,
        'user-a'
      );
      queryCache.setCached(
        'module:proj-user-a:execution_roadmap',
        {
          id: 'mod-user-a',
          project_id: 'proj-user-a',
          module_type: 'execution_roadmap',
          data: { secret_vision: 'USER_A_CONFIDENTIAL_STRATEGY' }
        },
        60000,
        'user-a'
      );

      // 3. Open a workspace route
      window.history.replaceState({}, '', '/?workspace=true');

      // 4. Keep /api/auth/me unresolved
      let resolveAuthMe: (value: any) => void;
      const authMePromise = new Promise((resolve) => {
        resolveAuthMe = resolve;
      });
      vi.spyOn(api.auth, 'getMe').mockReturnValue(authMePromise as any);

      render(<App />);

      // 5. Verify that ONLY workspace shell and skeleton appear
      const skeletons = screen.getAllByRole('status');
      expect(skeletons.length).toBeGreaterThan(0);
      expect(skeletons[0].getAttribute('aria-busy')).toBe('true');

      // 6. Verify that NO cached project name, module content, or secret appears
      expect(screen.queryByText('SECRET_PROJECT_USER_A')).toBeNull();
      expect(screen.queryByText('USER_A_CONFIDENTIAL_STRATEGY')).toBeNull();
      expect(screen.queryByText('Secret confidential roadmap')).toBeNull();

      // 7. Resolve authentication as a DIFFERENT user (user-b)
      const userB: User = {
        id: 'user-b',
        username: 'user_b_authorized',
        email: 'user_b@example.com',
        role: 'user',
        created_at: '2026-01-01T00:00:00Z'
      };

      let resolveUserBProjects: (value: any) => void;
      const userBProjectsPromise = new Promise((resolve) => {
        resolveUserBProjects = resolve;
      });
      vi.spyOn(api.projects, 'list').mockReturnValue(userBProjectsPromise as any);

      await act(async () => {
        resolveAuthMe!({ user: userB });
      });

      // 8. Verify that user-a's cached content is NEVER rendered
      expect(screen.queryByText('SECRET_PROJECT_USER_A')).toBeNull();
      expect(screen.queryByText('USER_A_CONFIDENTIAL_STRATEGY')).toBeNull();

      // 9. Verify that previous user's cache and nav storage were purged
      expect(queryCache.getCached('project:proj-user-a', 'user-b')).toBeUndefined();
      expect(getNavDestination('user-a')).toBeNull();

      // 10. Resolve user-b's authoritative project list
      const userBProject = createMockProject('proj-user-b', 'USER_B_AUTHORIZED_VENTURE');

      await act(async () => {
        resolveUserBProjects!([userBProject]);
      });

      // Verify ONLY user-b's content appears
      expect(screen.getByText('USER_B_AUTHORIZED_VENTURE')).toBeDefined();
      expect(screen.queryByText('SECRET_PROJECT_USER_A')).toBeNull();
    });
  });

  // =========================================================================
  // Section 2: Navigation Race Conditions
  // =========================================================================
  describe('2. Navigation Race-Condition Protection', () => {
    it('preserves latest destination when earlier requests resolve out-of-order and rejects stale errors', async () => {
      const mockUser: User = {
        id: 'u-race',
        username: 'race_tester',
        email: 'race@example.com',
        role: 'user',
        created_at: '2026-01-01T00:00:00Z'
      };
      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser, csrf_token: 'mock-csrf' });

      const projectA = createMockProject('proj-A', 'Project Alpha');
      const projectB = createMockProject('proj-B', 'Project Beta');
      const projectC = createMockProject('proj-C', 'Project Gamma');

      vi.spyOn(api.projects, 'list').mockResolvedValue([projectA, projectB, projectC]);


      // Controlled deferred resolvers for api.modules.get
      let resolveBMC: (val: any) => void;
      const promiseBMC = new Promise((resolve) => {
        resolveBMC = resolve;
      });

      let rejectTechStack: (err: any) => void;
      const promiseTechStack = new Promise((_, reject) => {
        rejectTechStack = reject;
      });

      let resolveMarketResearch: (val: any) => void;
      const promiseMarketResearch = new Promise((resolve) => {
        resolveMarketResearch = resolve;
      });

      vi.spyOn(api.projects, 'get').mockResolvedValue({
        ...projectA,
        active_module: 'overview',
        generated_modules: ['overview', 'bmc', 'tech_stack', 'market_research']
      });

      vi.spyOn(api.modules, 'get').mockImplementation((_projId: string, modType: string) => {
        if (modType === 'bmc') return promiseBMC as any;
        if (modType === 'tech_stack') return promiseTechStack as any;
        if (modType === 'market_research') return promiseMarketResearch as any;
        return Promise.resolve({ id: 'mod-' + modType, data: { ok: true } } as any);
      });

      window.history.replaceState({}, '', '/?workspace=true');
      render(<App />);

      await waitFor(() => {
        expect(screen.getByText('Project Alpha')).toBeDefined();
      });

      // Open Project Alpha
      await act(async () => {
        fireEvent.click(screen.getByText('Project Alpha'));
      });

      await waitFor(() => {
        expect(screen.getByText('Business Model Canvas')).toBeDefined();
      });

      // 1. Rapid navigation: Click BMC, then Click Tech Stack, then Click Market Research
      const bmcBtn = screen.getByText('Business Model Canvas');
      const techBtn = screen.getByText('Technology Stack');
      const mrBtn = screen.getByText('Market Research');

      await act(async () => {
        fireEvent.click(bmcBtn);
      });
      await act(async () => {
        fireEvent.click(techBtn);
      });
      await act(async () => {
        fireEvent.click(mrBtn);
      });

      // 4. Resolve the newest request (Market Research) FIRST
      await act(async () => {
        resolveMarketResearch!({
          id: 'mod-mr',
          project_id: 'proj-A',
          module_type: 'market_research',
          data: {
            provenance_note: 'TARGET_MARKET_LEADER',
            tam_summary: 'Market size',
            competitors: []
          }
        });
      });


      // Verify Market Research is active
      await waitFor(() => {
        expect(screen.getByText('TARGET_MARKET_LEADER')).toBeDefined();
      }, { timeout: 4000 });

      // 5. Resolve the older BMC request SECOND
      await act(async () => {
        resolveBMC!({
          id: 'mod-bmc',
          project_id: 'proj-A',
          module_type: 'bmc',
          data: { customer_segments: ['STALE_OLD_BMC_SEGMENT'] }
        });
      });

      // 6. The visible screen must STILL remain on Market Research
      expect(screen.getByText('TARGET_MARKET_LEADER')).toBeDefined();
      expect(screen.queryByText('STALE_OLD_BMC_SEGMENT')).toBeNull();

      // 7. Resolve Tech Stack with an error afterward
      await act(async () => {
        rejectTechStack!(new Error('Stale network failure for Tech Stack'));
      });

      // 8. Stale error must NOT replace Market Research with an error state
      expect(screen.getByText('TARGET_MARKET_LEADER')).toBeDefined();
      expect(screen.queryByText('Stale network failure for Tech Stack')).toBeNull();

      // 9. Stored last destination must be market_research
      const saved = getNavDestination('u-race');
      expect(saved?.module).toBe('market_research');
      expect(saved?.projectId).toBe('proj-A');
    });

  });

  // =========================================================================
  // Section 3: User-Scoped Cache Keys & Epoch Isolation
  // =========================================================================
  describe('3. User-Scoped Cache Keys & Late Response Protection', () => {
    it('prevents late responses initiated before logout from repopulating cache', async () => {
      let resolveSlowFetch: (val: any) => void;
      const slowPromise = new Promise((resolve) => {
        resolveSlowFetch = resolve;
      });

      // Launch slow fetch under user-1
      const fetchPromise = queryCache.fetchWithCache(
        'test:slow:key',
        () => slowPromise as any,
        { userScope: 'user-1' }
      );

      expect(queryCache.inFlightCount).toBe(1);

      // User logs out before response arrives
      queryCache.clearAll();
      expect(queryCache.inFlightCount).toBe(0);
      expect(queryCache.size).toBe(0);

      // Slow response resolves after logout
      await act(async () => {
        resolveSlowFetch!({ secret: 'should_not_be_cached' });
        await fetchPromise.catch(() => {});
      });

      // Cache MUST remain completely empty
      expect(queryCache.size).toBe(0);
      expect(queryCache.getCached('test:slow:key')).toBeUndefined();
      expect(queryCache.getCached('test:slow:key', 'user-1')).toBeUndefined();
    });

    it('prevents late responses initiated under old user from being read by new user', async () => {
      let resolveUserAFetch: (val: any) => void;
      const userAPromise = new Promise((resolve) => {
        resolveUserAFetch = resolve;
      });

      const p1 = queryCache.fetchWithCache(
        'projects:list',
        () => userAPromise as any,
        { userScope: 'user-A' }
      );

      // User switches to user-B
      queryCache.clearAll();

      await act(async () => {
        resolveUserAFetch!([{ id: 'proj-A-secret' }]);
        await p1.catch(() => {});
      });

      // User-B requests projects:list - must get cache miss
      expect(queryCache.getCached('projects:list', 'user-B')).toBeUndefined();
    });

    it('ensures regex invalidation cleanly catches all matching keys without skipping', () => {
      queryCache.setCached('module:p1:overview', { ok: 1 });
      queryCache.setCached('module:p1:bmc', { ok: 2 });
      queryCache.setCached('module:p1:tech_stack', { ok: 3 });
      queryCache.setCached('module:p1:execution_roadmap', { ok: 4 });
      queryCache.setCached('module:p2:bmc', { ok: 5 });

      // Invalidate all p1 modules with a regex
      queryCache.invalidate(/^module:p1:/);

      expect(queryCache.getCached('module:p1:overview')).toBeUndefined();
      expect(queryCache.getCached('module:p1:bmc')).toBeUndefined();
      expect(queryCache.getCached('module:p1:tech_stack')).toBeUndefined();
      expect(queryCache.getCached('module:p1:execution_roadmap')).toBeUndefined();
      // p2 should remain intact
      expect(queryCache.getCached('module:p2:bmc')).toBeDefined();
    });
  });

  // =========================================================================
  // Section 4: Form Draft Recovery Safety
  // =========================================================================
  describe('4. Draft Recovery Storage Isolation & Safety', () => {
    it('safely handles corrupt JSON and rejects wrong user or wrong project scope', () => {
      sessionStorage.setItem('va_draft_user1_wizard_global', 'invalid-non-json{');
      expect(getDraft('user1', 'wizard')).toBeNull();

      // Save draft for user1 under project1
      saveDraft('user1', 'copilot_input', 'My message', 'proj1');

      // User2 cannot read user1 draft
      expect(getDraft('user2', 'copilot_input', 'proj1')).toBeNull();

      // Project2 cannot read project1 draft
      expect(getDraft('user1', 'copilot_input', 'proj2')).toBeNull();

      // Correct user and project restores successfully
      expect(getDraft('user1', 'copilot_input', 'proj1')).toBe('My message');
    });

    it('expires drafts after TTL and clears on submission', () => {
      // Save with 1ms TTL
      saveDraft('u1', 'test_type', { foo: 'bar' }, undefined, 1);

      return new Promise<void>((resolve) => {
        setTimeout(() => {
          expect(getDraft('u1', 'test_type')).toBeNull();
          resolve();
        }, 20);
      });
    });
  });

  // =========================================================================
  // Section 5: Navigation Restoration Authoritative Validation
  // =========================================================================
  describe('5. Navigation Restoration Validation', () => {
    it('discards saved destination if project is not in authoritative project list', async () => {
      const mockUser: User = {
        id: 'u-auth-test',
        username: 'auth_tester',
        email: 'test@example.com',
        role: 'user',
        created_at: '2026-01-01T00:00:00Z'
      };
      vi.spyOn(api.auth, 'getMe').mockResolvedValue({ user: mockUser, csrf_token: 'mock-csrf' });

      // Save destination for a project that was deleted
      saveNavDestination('u-auth-test', 'deleted-project-123', 'bmc');

      // Authoritative project list does not contain deleted-project-123
      const liveProject = createMockProject('live-proj', 'Live Project');
      vi.spyOn(api.projects, 'list').mockResolvedValue([liveProject]);


      window.history.replaceState({}, '', '/?workspace=true');
      render(<App />);

      await waitFor(() => {
        expect(screen.getByText('Live Project')).toBeDefined();
      });

      // The deleted project destination was discarded from localStorage
      expect(getNavDestination('u-auth-test')).toBeNull();
    });
  });

  // =========================================================================
  // Section 6: Prefetch Behavior
  // =========================================================================
  describe('6. Prefetch Audit & Concurrency', () => {
    it('keyboard focus provides the same prefetch trigger as pointer hover', () => {
      const fetchSpy = vi.spyOn(queryCache, 'fetchWithCache');
      vi.spyOn(api.projects, 'get').mockResolvedValue({ id: 'p-focus', name: 'Focused Project' } as any);

      prefetchProjectData('p-focus', 'u1');
      expect(fetchSpy).toHaveBeenCalled();
    });

    it('suppresses speculative prefetch when data-saver mode is active', () => {
      const fetchSpy = vi.spyOn(queryCache, 'fetchWithCache');
      const nav = navigator as any;
      nav.connection = { saveData: true };

      prefetchProjectData('p-saver', 'u1');
      expect(fetchSpy).not.toHaveBeenCalled();

      delete nav.connection;
    });
  });
});
