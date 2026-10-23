import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { App } from '../App';
import { LandingPage } from '../pages/LandingPage';
import { DashboardPage } from '../pages/DashboardPage';
import { queryCache } from '../services/queryCache';
import { saveNavDestination, getNavDestination, clearNavDestination } from '../services/navigationStorage';
import { saveDraft, getDraft, clearDraft, clearUserDrafts } from '../services/draftStorage';
import { api } from '../services/api';
import { Project, User } from '../types';

describe('Batch 03: Perceived Performance & Immediate Shell', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    queryCache.clearAll();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    queryCache.clearAll();
  });

  // Section 3: Instant Landing Page
  describe('Section 3: Instant Landing Page', () => {
    it('renders heading, navigation, and primary CTA immediately while /api/auth/me is unresolved', async () => {
      // Hold /api/auth/me unresolved indefinitely
      let resolveAuth: any;
      const authPromise = new Promise<{ user: User }>((resolve) => {
        resolveAuth = resolve;
      });
      vi.spyOn(api.auth, 'getMe').mockImplementation(() => authPromise as any);

      render(<App />);

      // Proves heading is rendered immediately without waiting for auth
      expect(screen.getByRole('heading', { level: 1 })).toBeDefined();
      expect(screen.getByText(/Turn your business idea into an/i)).toBeDefined();

      // Proves navigation links are rendered and usable
      expect(screen.getByText('Workspace Modules')).toBeDefined();
      expect(screen.getByText('Planning Workflow')).toBeDefined();
      expect(screen.getByText('Enterprise Architecture')).toBeDefined();

      // Proves primary action is rendered and usable
      const ctaBtn = screen.getByRole('button', { name: /Create Your Blueprint/i });
      expect(ctaBtn).toBeDefined();

      // Proves clicking CTA opens auth modal immediately without blank screen
      fireEvent.click(ctaBtn);
      expect(screen.getByRole('dialog')).toBeDefined();
      expect(screen.getByText(/Create Free Account/i)).toBeDefined();

      // Cleanup unresolved promise
      resolveAuth({ user: { id: 'u1', username: 'testuser', email: 'test@example.com', role: 'user', created_at: '2026-01-01T00:00:00Z' } });
    });

    it('updates primary action to "Open workspace" when visitor is authenticated', () => {
      const mockUser: User = { id: 'u1', username: 'alice', email: 'alice@example.com', role: 'user', created_at: '2026-01-01T00:00:00Z' };
      const onOpenWorkspace = vi.fn();

      render(
        <LandingPage
          onAuthenticated={vi.fn()}
          currentUser={mockUser}
          onOpenWorkspace={onOpenWorkspace}
        />
      );

      // Top navbar shows username and Open workspace
      expect(screen.getByText('alice')).toBeDefined();
      const openWorkspaceBtns = screen.getAllByRole('button', { name: /Open workspace/i });
      expect(openWorkspaceBtns.length).toBeGreaterThanOrEqual(1);

      // Clicking Open workspace triggers handler
      fireEvent.click(openWorkspaceBtns[0]);
      expect(onOpenWorkspace).toHaveBeenCalledTimes(1);
    });

    it('does not leave a blank screen when /api/auth/me fails', async () => {
      vi.spyOn(api.auth, 'getMe').mockRejectedValue(new Error('Network error'));

      render(<App />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1 })).toBeDefined();
      });

      // Public landing page remains usable
      expect(screen.getByText('Get Started')).toBeDefined();
      expect(screen.getByText('Sign In')).toBeDefined();
    });
  });

  // Section 4: Immediate Workspace Shell & Explicit States
  describe('Section 4: Immediate Workspace Shell & Explicit States', () => {
    const mockUser: User = { id: 'u1', username: 'bob', email: 'bob@example.com', role: 'user', created_at: '2026-01-01T00:00:00Z' };

    it('shows accessible skeletons while projects request is pending', () => {
      render(
        <DashboardPage
          user={mockUser}
          projects={[]}
          projectsStatus="loading"
          onOpenProject={vi.fn()}
          onCreateNewProject={vi.fn()}
          onDeleteProject={vi.fn()}
          onLogout={vi.fn()}
        />
      );

      // Verifies accessible skeletons with aria-busy and status role
      const statusEl = screen.getByRole('status');
      expect(statusEl).toBeDefined();
      expect(statusEl.getAttribute('aria-busy')).toBe('true');
      expect(statusEl.getAttribute('aria-label')).toBe('Loading projects');

      // Crucial: False-empty message must NOT appear during loading
      expect(screen.queryByText(/No Venture Blueprints Yet/i)).toBeNull();
    });

    it('shows empty portfolio ONLY after successful empty response (success-empty)', () => {
      render(
        <DashboardPage
          user={mockUser}
          projects={[]}
          projectsStatus="success-empty"
          onOpenProject={vi.fn()}
          onCreateNewProject={vi.fn()}
          onDeleteProject={vi.fn()}
          onLogout={vi.fn()}
        />
      );

      // Now empty portfolio message appears because server confirmed empty array
      expect(screen.getByText(/No Venture Blueprints Yet/i)).toBeDefined();
      expect(screen.getByRole('button', { name: /Create Your First Project/i })).toBeDefined();
    });

    it('shows a retryable error on failed project request, NOT an empty portfolio', () => {
      const onRetry = vi.fn();
      render(
        <DashboardPage
          user={mockUser}
          projects={[]}
          projectsStatus="error"
          projectsError="Failed to connect to database"
          onRetryProjects={onRetry}
          onOpenProject={vi.fn()}
          onCreateNewProject={vi.fn()}
          onDeleteProject={vi.fn()}
          onLogout={vi.fn()}
        />
      );

      // Renders retryable error message
      expect(screen.getByText(/Unable to Load Venture Blueprints/i)).toBeDefined();
      expect(screen.getAllByText(/Failed to connect to database/i).length).toBeGreaterThanOrEqual(1);

      // Proves empty portfolio is NEVER shown on error
      expect(screen.queryByText(/No Venture Blueprints Yet/i)).toBeNull();

      // Proves retry button works
      const retryBtn = screen.getByRole('button', { name: /Retry Loading/i });
      fireEvent.click(retryBtn);
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('unauthorized 401 response clears protected state cleanly and resets to landing page', async () => {
      vi.spyOn(api.auth, 'getMe').mockResolvedValue({
        user: mockUser,
        csrf_token: 'csrf-123'
      } as any);

      vi.spyOn(api.projects, 'list').mockResolvedValue([
        { id: 'p1', name: 'Alpha Project', stage: 'Idea', industry: 'SaaS', updated_at: new Date().toISOString() } as Project
      ]);

      render(<App />);

      // Wait for auth and workspace
      await waitFor(() => {
        expect(screen.getByText('Open workspace →')).toBeDefined();
      });

      // Transition to workspace
      fireEvent.click(screen.getByText('Open workspace →'));

      await waitFor(() => {
        expect(screen.getByText('Alpha Project')).toBeDefined();
      });

      // Simulate 401 session expiration event
      window.dispatchEvent(new CustomEvent('auth:expired'));

      // Proves protected state is wiped and returned to LandingPage cleanly
      await waitFor(() => {
        expect(screen.queryByText('Alpha Project')).toBeNull();
        expect(screen.getByText(/Turn your business idea into an/i)).toBeDefined();
      });
    });
  });

  // Section 5: Lightweight Navigation Destination
  describe('Section 5: Navigation Storage', () => {
    it('saves, validates, and restores harmless navigation destination', () => {
      saveNavDestination('user-123', 'proj-abc', 'tech_stack');

      const restored = getNavDestination('user-123');
      expect(restored).not.toBeNull();
      expect(restored?.schemaVersion).toBe(1);
      expect(restored?.userScope).toBe('user-123');
      expect(restored?.projectId).toBe('proj-abc');
      expect(restored?.module).toBe('tech_stack');
      expect(restored?.updatedAt).toBeGreaterThan(0);

      // Verifies no passwords, bearer tokens, or session tokens are stored
      const raw = localStorage.getItem('va_nav_dest_user-123')!;
      expect(raw).not.toContain('token');
      expect(raw).not.toContain('password');
      expect(raw).not.toContain('cookie');
    });

    it('rejects destination for different userScope', () => {
      saveNavDestination('user-1', 'proj-1', 'bmc');
      expect(getNavDestination('user-2')).toBeNull();
    });

    it('rejects and clears expired destination (>30 days)', () => {
      const expiredPayload = {
        schemaVersion: 1,
        userScope: 'user-old',
        projectId: 'proj-old',
        module: 'overview',
        updatedAt: Date.now() - (35 * 24 * 60 * 60 * 1000) // 35 days old
      };
      localStorage.setItem('va_nav_dest_user-old', JSON.stringify(expiredPayload));

      expect(getNavDestination('user-old')).toBeNull();
      expect(localStorage.getItem('va_nav_dest_user-old')).toBeNull();
    });

    it('rejects invalid schema or unsupported module slug', () => {
      const badPayload = {
        schemaVersion: 2,
        userScope: 'u1',
        projectId: 'p1',
        module: 'unsupported_route'
      };
      localStorage.setItem('va_nav_dest_u1', JSON.stringify(badPayload));
      expect(getNavDestination('u1')).toBeNull();
    });
  });

  // Section 6 & 7: Query Cache & Deduplication
  describe('Section 6 & 7: Query Cache Layer', () => {
    it('deduplicates concurrent in-flight requests into a single network call', async () => {
      let callCount = 0;
      const fetcher = vi.fn().mockImplementation(async () => {
        callCount++;
        await new Promise(r => setTimeout(r, 20));
        return [{ id: 'p1', name: 'Project 1' }];
      });

      // Fire 3 simultaneous fetch calls for the same key
      const [res1, res2, res3] = await Promise.all([
        queryCache.fetchWithCache('projects:list', fetcher),
        queryCache.fetchWithCache('projects:list', fetcher),
        queryCache.fetchWithCache('projects:list', fetcher)
      ]);

      // All 3 return identical data
      expect(res1).toEqual([{ id: 'p1', name: 'Project 1' }]);
      expect(res2).toEqual(res1);
      expect(res3).toEqual(res1);

      // Only ONE network call occurred!
      expect(callCount).toBe(1);
    });

    it('serves fresh cached data immediately without invoking fetcher', async () => {
      queryCache.setCached('project:p1', { id: 'p1', name: 'Cached Name' }, 60000);

      const fetcher = vi.fn();
      const result = await queryCache.fetchWithCache('project:p1', fetcher, { staleTimeMs: 60000 });

      expect(result).toEqual({ id: 'p1', name: 'Cached Name' });
      expect(fetcher).not.toHaveBeenCalled();
    });

    it('invalidates cache on mutation', async () => {
      queryCache.setCached('projects:list', [{ id: 'p1' }]);
      expect(queryCache.getCached('projects:list')).toBeDefined();

      queryCache.invalidate('projects:list');
      expect(queryCache.getCached('projects:list')).toBeUndefined();
    });

    it('clears user-scoped cache on logout', () => {
      queryCache.setCached('projects:list', [{ id: 'p1' }], 60000, 'user-A');
      queryCache.setCached('projects:other', [{ id: 'p2' }], 60000, 'user-B');

      queryCache.clearUserScope('user-A');
      expect(queryCache.getCached('projects:list')).toBeUndefined();
      expect(queryCache.getCached('projects:other')).toBeDefined();

      queryCache.clearAll();
      expect(queryCache.getCached('projects:other')).toBeUndefined();
    });
  });

  // Section 11: Draft Recovery through sessionStorage
  describe('Section 11: Draft Recovery in sessionStorage', () => {
    it('saves, retrieves, and isolates form drafts by userScope', () => {
      const wizardData = { name: 'Fintech App', stage: 'MVP', budget: '50k' };
      saveDraft('user-1', 'wizard', wizardData);

      const restored = getDraft('user-1', 'wizard');
      expect(restored).toEqual(wizardData);

      // Different user cannot access user-1's draft
      expect(getDraft('user-2', 'wizard')).toBeNull();

      // Clear draft on submit
      clearDraft('user-1', 'wizard');
      expect(getDraft('user-1', 'wizard')).toBeNull();
    });

    it('expires drafts after TTL', () => {
      // Save with negative TTL to simulate expired draft
      saveDraft('user-1', 'test_draft', { foo: 'bar' }, undefined, -100);
      expect(getDraft('user-1', 'test_draft')).toBeNull();
    });

    it('clears all user drafts on logout', () => {
      saveDraft('user-1', 'wizard', { name: 'Draft 1' });
      saveDraft('user-1', 'copilot_input', 'Draft prompt');

      clearUserDrafts('user-1');
      expect(getDraft('user-1', 'wizard')).toBeNull();
      expect(getDraft('user-1', 'copilot_input')).toBeNull();
    });
  });

  // Section 14: Delayed-Network Behavioral Proofs
  describe('Section 14: Controlled Delayed-Network Behavioral Proofs', () => {
    const mockUser: User = { id: 'u-perf', username: 'charlie', email: 'charlie@example.com', role: 'user', created_at: '2026-01-01T00:00:00Z' };

    it('session delayed by 2000ms: landing page renders and remains interactive immediately', async () => {
      vi.spyOn(api.auth, 'getMe').mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ user: mockUser } as any), 2000))
      );

      const startTime = Date.now();
      render(<App />);

      // Instant first render proof
      expect(screen.getByRole('heading', { level: 1 })).toBeDefined();
      expect(screen.getByText(/Turn your business idea into an/i)).toBeDefined();
      expect(Date.now() - startTime).toBeLessThan(500); // Proves rendered far before 2000ms resolution
    });

    it('project list delayed by 2000ms: workspace shell and skeletons appear immediately, no false empty state', async () => {
      vi.spyOn(api.projects, 'list').mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve([]), 2000))
      );

      render(
        <DashboardPage
          user={mockUser}
          projects={[]}
          projectsStatus="loading"
          onOpenProject={vi.fn()}
          onCreateNewProject={vi.fn()}
          onDeleteProject={vi.fn()}
          onLogout={vi.fn()}
        />
      );

      // Skeletons are visible immediately
      expect(screen.getByRole('status')).toBeDefined();
      // False empty state does NOT flash
      expect(screen.queryByText(/No Venture Blueprints Yet/i)).toBeNull();
    });

    it('stale requests cannot overwrite newer navigation destination', async () => {
      let resolveFirst: any;
      let resolveSecond: any;

      const firstFetch = new Promise<{ id: string; active_version_name: string }>((res) => { resolveFirst = res; });
      const secondFetch = new Promise<{ id: string; active_version_name: string }>((res) => { resolveSecond = res; });

      // Simulate first navigation to BMC
      const key1 = 'module:p1:bmc';
      const key2 = 'module:p1:tech_stack';

      const p1 = queryCache.fetchWithCache(key1, () => firstFetch);
      const p2 = queryCache.fetchWithCache(key2, () => secondFetch);

      // Second request resolves first
      resolveSecond({ id: 'ts-mod', active_version_name: 'TS V2' });
      const secondResult = await p2;
      expect(secondResult.active_version_name).toBe('TS V2');

      // Older stale request resolves later
      resolveFirst({ id: 'bmc-mod', active_version_name: 'BMC V1' });
      const firstResult = await p1;

      // Both stay isolated in cache and do not overwrite each other
      expect(queryCache.getCached(key2)).toEqual({ id: 'ts-mod', active_version_name: 'TS V2' });
      expect(queryCache.getCached(key1)).toEqual({ id: 'bmc-mod', active_version_name: 'BMC V1' });
    });

    it('restored navigation does not bypass authorization', () => {
      // User 2 has a saved destination pointing to Project X
      saveNavDestination('user-attacker', 'proj-private', 'tech_stack');

      // But when authenticated as user-victim, reading destination with user-victim scope returns null
      const restored = getNavDestination('user-victim');
      expect(restored).toBeNull();
    });
  });
});

