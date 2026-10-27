/**
 * Intent-based speculative prefetching for lazy JavaScript chunks and compact API data.
 * Activates on pointer hover or keyboard focus with debounce and low concurrency.
 * Respects Save-Data network mode.
 * Bounded speculative network concurrency (max 2 actual requests).
 * Scoped to session epochs with immediate cancellation on logout or session change.
 */

import { queryCache } from './queryCache';
import { api } from './api';

// Registry of dynamic chunk loaders
const MODULE_CHUNK_LOADERS: Record<string, () => Promise<any>> = {
  bmc: () => import('../components/BMCModule'),
  tech_stack: () => import('../components/TechStackModule'),
  idea_validator: () => import('../components/IdeaValidatorModule'),
  market_research: () => import('../components/MarketResearchModule'),
  execution_roadmap: () => import('../components/ExecutionRoadmapModule'),
  blueprint_copilot: () => import('../components/BlueprintCopilotModule'),
  wizard: () => import('../components/NewProjectWizard'),
  conflict: () => import('../components/VersionConflictModal')
};

// Check if user has enabled data-saver mode
export function isSaveDataEnabled(): boolean {
  if (typeof navigator === 'undefined') return false;
  const conn = (navigator as any).connection;
  return Boolean(conn?.saveData);
}

// Low concurrency limiter (max 2 actual concurrent network requests)
const MAX_CONCURRENT_PREFETCH = 2;
let activePrefetches = 0;
let currentSessionEpoch = 1;

interface PrefetchJob {
  key: string;
  epoch: number;
  task: (signal: AbortSignal) => Promise<void>;
  controller: AbortController;
}

const prefetchQueue: PrefetchJob[] = [];
const queuedKeys = new Set<string>();
const activeControllers = new Set<AbortController>();
const prefetchedChunks = new Set<string>();

/**
 * Pump queue respecting max concurrency of 2 actual HTTP / chunk requests
 */
function pumpQueue() {
  while (activePrefetches < MAX_CONCURRENT_PREFETCH && prefetchQueue.length > 0) {
    const job = prefetchQueue.shift()!;
    if (job.epoch !== currentSessionEpoch) {
      queuedKeys.delete(job.key);
      continue;
    }

    activePrefetches++;
    activeControllers.add(job.controller);

    job.task(job.controller.signal)
      .catch(() => {
        // Speculative errors are silently ignored
      })
      .finally(() => {
        activePrefetches--;
        activeControllers.delete(job.controller);
        queuedKeys.delete(job.key);
        pumpQueue();
      });
  }
}

/**
 * Schedule a bounded prefetch job with intention deduplication and session epoch check
 */
function schedulePrefetch(key: string, task: (signal: AbortSignal) => Promise<void>) {
  if (isSaveDataEnabled()) return;
  if (queuedKeys.has(key)) return;

  const controller = new AbortController();
  queuedKeys.add(key);
  prefetchQueue.push({
    key,
    epoch: currentSessionEpoch,
    task,
    controller
  });

  pumpQueue();
}

/**
 * Cancel all queued and in-flight prefetch jobs, increment session epoch.
 * Must be called on logout or session switch.
 */
export function cancelPrefetchQueue(): void {
  currentSessionEpoch++;
  prefetchQueue.length = 0;
  queuedKeys.clear();
  for (const controller of activeControllers) {
    try {
      controller.abort();
    } catch {
      // ignore
    }
  }
  activeControllers.clear();
  prefetchedChunks.clear();
}

/**
 * Reset prefetch session epoch for fresh authenticated session
 */
export function resetPrefetchSession(): void {
  cancelPrefetchQueue();
}

/**
 * Prefetches the code chunk for a module.
 */
export function prefetchModuleChunk(moduleType: string): void {
  if (isSaveDataEnabled() || prefetchedChunks.has(moduleType)) return;
  const loader = MODULE_CHUNK_LOADERS[moduleType];
  if (!loader) return;

  const chunkKey = `chunk:${moduleType}`;
  if (queuedKeys.has(chunkKey)) return;

  prefetchedChunks.add(moduleType);
  schedulePrefetch(chunkKey, async () => {
    try {
      await loader();
    } catch {
      prefetchedChunks.delete(moduleType);
    }
  });
}

/**
 * Prefetches compact API data for a module under a specific project.
 * GET requests only. Never prefetch mutations or generations.
 */
export function prefetchModuleData(projectId: string, moduleType: string, userScope?: string): void {
  if (isSaveDataEnabled() || !projectId || !moduleType) return;
  if (moduleType === 'overview') return;

  if (moduleType === 'execution_roadmap') {
    // Schedule as two individual bounded requests to prevent hidden concurrency spike
    const listKey = `tasks:list:${projectId}`;
    if (!queryCache.isFresh(listKey)) {
      schedulePrefetch(listKey, async (signal) => {
        await queryCache.fetchWithCache(listKey, (s) => api.tasks.list(projectId, undefined, { signal: s }), {
          staleTimeMs: 30000,
          userScope,
          signal
        });
      });
    }

    const summaryKey = `tasks:summary:${projectId}`;
    if (!queryCache.isFresh(summaryKey)) {
      schedulePrefetch(summaryKey, async (signal) => {
        await queryCache.fetchWithCache(summaryKey, (s) => api.tasks.getSummary(projectId, { signal: s }), {
          staleTimeMs: 30000,
          userScope,
          signal
        });
      });
    }
  } else if (moduleType === 'blueprint_copilot') {
    const copilotKey = `copilot:page:${projectId}`;
    if (!queryCache.isFresh(copilotKey)) {
      schedulePrefetch(copilotKey, async (signal) => {
        await queryCache.fetchWithCache(copilotKey, (s) => api.copilot.getPage(projectId, undefined, 50, { signal: s }), {
          staleTimeMs: 30000,
          userScope,
          signal
        });
      });
    }
  } else {
    const cacheKey = `module:${projectId}:${moduleType}`;
    if (!queryCache.isFresh(cacheKey)) {
      schedulePrefetch(cacheKey, async (signal) => {
        await queryCache.fetchWithCache(cacheKey, (s) => api.modules.get(projectId, moduleType, { signal: s }), {
          staleTimeMs: 30000,
          userScope,
          signal
        });
      });
    }
  }
}

/**
 * Combined intent handler for hover / keyboard focus on navigation targets.
 */
export function prefetchModule(projectId: string, moduleType: string, userScope?: string): void {
  prefetchModuleChunk(moduleType);
  prefetchModuleData(projectId, moduleType, userScope);
}

/**
 * Prefetch single project metadata on hover / focus.
 */
export function prefetchProjectData(projectId: string, userScope?: string): void {
  if (isSaveDataEnabled() || !projectId) return;
  const cacheKey = `project:${projectId}`;
  if (queryCache.isFresh(cacheKey)) return;

  schedulePrefetch(cacheKey, async (signal) => {
    await queryCache.fetchWithCache(cacheKey, (s) => api.projects.get(projectId, { signal: s }), {
      staleTimeMs: 60000,
      userScope,
      signal
    });
  });
}

