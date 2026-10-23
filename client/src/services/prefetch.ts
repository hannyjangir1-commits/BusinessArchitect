/**
 * Intent-based speculative prefetching for lazy JavaScript chunks and compact API data.
 * Activates on pointer hover or keyboard focus with debounce and low concurrency.
 * Respects Save-Data network mode.
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

// Low concurrency limiter (max 2 background prefetch operations)
let activePrefetches = 0;
const MAX_CONCURRENT_PREFETCH = 2;
const prefetchQueue: Array<() => Promise<void>> = [];

function pumpQueue() {
  while (activePrefetches < MAX_CONCURRENT_PREFETCH && prefetchQueue.length > 0) {
    const task = prefetchQueue.shift()!;
    activePrefetches++;
    task().finally(() => {
      activePrefetches--;
      pumpQueue();
    });
  }
}

function schedulePrefetch(task: () => Promise<void>) {
  if (isSaveDataEnabled()) return;
  prefetchQueue.push(task);
  pumpQueue();
}

// Prefetched cache keys tracker to avoid redundant attempts
const prefetchedChunks = new Set<string>();

export function cancelPrefetchQueue(): void {
  prefetchQueue.length = 0;
  prefetchedChunks.clear();
}


/**
 * Prefetches the code chunk for a module.
 */
export function prefetchModuleChunk(moduleType: string): void {
  if (isSaveDataEnabled() || prefetchedChunks.has(moduleType)) return;
  const loader = MODULE_CHUNK_LOADERS[moduleType];
  if (!loader) return;

  prefetchedChunks.add(moduleType);
  schedulePrefetch(async () => {
    try {
      await loader();
    } catch {
      prefetchedChunks.delete(moduleType);
    }
  });
}

/**
 * Prefetches compact API data for a module under a specific project.
 */
export function prefetchModuleData(projectId: string, moduleType: string, userScope?: string): void {
  if (isSaveDataEnabled() || !projectId || !moduleType) return;
  if (moduleType === 'overview') return;

  const cacheKey = `module:${projectId}:${moduleType}`;
  if (queryCache.isFresh(cacheKey)) return;

  schedulePrefetch(async () => {
    try {
      if (moduleType === 'execution_roadmap') {
        await Promise.allSettled([
          queryCache.fetchWithCache(`tasks:list:${projectId}`, () => api.tasks.list(projectId), {
            staleTimeMs: 30000,
            userScope
          }),
          queryCache.fetchWithCache(`tasks:summary:${projectId}`, () => api.tasks.getSummary(projectId), {
            staleTimeMs: 30000,
            userScope
          })
        ]);
      } else if (moduleType === 'blueprint_copilot') {
        await queryCache.fetchWithCache(`copilot:history:${projectId}`, () => api.copilot.getHistory(projectId), {
          staleTimeMs: 30000,
          userScope
        });
      } else {
        await queryCache.fetchWithCache(cacheKey, () => api.modules.get(projectId, moduleType), {
          staleTimeMs: 30000,
          userScope
        });
      }
    } catch {
      // Ignore background speculative errors
    }
  });
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

  schedulePrefetch(async () => {
    try {
      await queryCache.fetchWithCache(cacheKey, () => api.projects.get(projectId), {
        staleTimeMs: 60000,
        userScope
      });
    } catch {
      // Ignore background errors
    }
  });
}
