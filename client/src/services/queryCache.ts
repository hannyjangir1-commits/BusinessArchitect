/**
 * Lightweight, zero-dependency in-memory query cache & deduplication service.
 * Supports:
 * - In-flight promise reuse (request deduplication)
 * - Stale-while-revalidate freshness semantics
 * - AbortController integration
 * - User-scoped cache isolation and invalidation
 * - Generation epoch tracking to prevent late responses from repopulating post-logout cache
 * - Safe TTL expiration
 */

export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  staleAt: number;
  userScope?: string;
}

interface InFlightRequest<T> {
  promise: Promise<T>;
  controller: AbortController;
  timestamp: number;
  requestEpoch: number;
  userScope?: string;
}

export interface FetchWithCacheOptions {
  staleTimeMs?: number;
  userScope?: string;
  forceFresh?: boolean;
  signal?: AbortSignal;
}

class QueryCache {
  private cache = new Map<string, CacheEntry<any>>();
  private inFlight = new Map<string, InFlightRequest<any>>();
  private epoch = 0;

  /**
   * Fetch with request deduplication and stale-while-revalidate caching.
   * If a request for the same key is already in flight, reuses the existing promise.
   * If fresh data is in cache for this userScope, returns it immediately.
   * If stale data is in cache, returns cached data immediately and revalidates in the background.
   */
  async fetchWithCache<T>(
    key: string,
    fetcher: (signal: AbortSignal) => Promise<T>,
    options: FetchWithCacheOptions = {}
  ): Promise<T> {
    const {
      staleTimeMs = 60000,
      userScope,
      forceFresh = false,
      signal
    } = options;

    const now = Date.now();
    const cached = this.cache.get(key);

    // Verify userScope compatibility: a user cannot read another user's cached entry
    const scopeMatches = (!cached?.userScope && !userScope) || (cached?.userScope === userScope);

    // 1. Fresh cache hit
    if (cached && scopeMatches && !forceFresh) {
      if (now < cached.staleAt) {
        return cached.data as T;
      }
      // Stale cache hit: return cached data immediately and revalidate in background
      this.revalidateInBackground(key, fetcher, staleTimeMs, userScope);
      return cached.data as T;
    }

    // 2. Reuse in-flight request if present and userScope matches
    const existing = this.inFlight.get(key);
    if (existing && existing.userScope === userScope) {
      return existing.promise as Promise<T>;
    }

    // 3. Launch new fetch with epoch tracking
    const requestEpoch = this.epoch;
    const requestUserScope = userScope;
    const controller = new AbortController();

    if (signal) {
      if (signal.aborted) {
        controller.abort(signal.reason);
      } else {
        signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
      }
    }

    const promise = (async () => {
      try {
        const data = await fetcher(controller.signal);
        // Epoch & Abort guard: If cache was cleared, user logged out, or request aborted, do NOT write to cache
        if (this.epoch !== requestEpoch || controller.signal.aborted) {
          return data;
        }
        this.cache.set(key, {
          data,
          timestamp: Date.now(),
          staleAt: Date.now() + staleTimeMs,
          userScope: requestUserScope
        });
        return data;
      } finally {
        this.inFlight.delete(key);
      }
    })();

    this.inFlight.set(key, {
      promise,
      controller,
      timestamp: now,
      requestEpoch,
      userScope
    });

    return promise;
  }

  private revalidateInBackground<T>(
    key: string,
    fetcher: (signal: AbortSignal) => Promise<T>,
    staleTimeMs: number,
    userScope?: string
  ): void {
    if (this.inFlight.has(key)) return;

    const requestEpoch = this.epoch;
    const controller = new AbortController();
    const promise = (async () => {
      try {
        const data = await fetcher(controller.signal);
        // Guard against writing to cache if epoch changed or aborted
        if (this.epoch !== requestEpoch || controller.signal.aborted) {
          return;
        }
        this.cache.set(key, {
          data,
          timestamp: Date.now(),
          staleAt: Date.now() + staleTimeMs,
          userScope
        });
      } catch {
        // Background revalidation failure silently keeps existing stale data
      } finally {
        this.inFlight.delete(key);
      }
    })();

    this.inFlight.set(key, {
      promise,
      controller,
      timestamp: Date.now(),
      requestEpoch,
      userScope
    });
  }

  /**
   * Retrieves an entry from cache if present.
   * If userScope is provided and entry is tagged with a different userScope, returns undefined.
   */
  getCached<T>(key: string, userScope?: string): T | undefined {
    const entry = this.cache.get(key);
    if (!entry) return undefined;
    if (userScope && entry.userScope && entry.userScope !== userScope) {
      return undefined;
    }
    return entry.data as T;
  }


  isFresh(key: string, userScope?: string): boolean {
    const entry = this.cache.get(key);
    if (!entry) return false;
    if (entry.userScope && entry.userScope !== userScope) return false;
    return Date.now() < entry.staleAt;
  }

  setCached<T>(key: string, data: T, staleTimeMs = 60000, userScope?: string): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      staleAt: Date.now() + staleTimeMs,
      userScope
    });
  }

  invalidate(patternOrKey: string | RegExp): void {
    if (typeof patternOrKey === 'string') {
      this.cache.delete(patternOrKey);
      this.abortKey(patternOrKey);
    } else {
      // Strip 'g' flag to prevent stateful lastIndex skipping across sequential .test() calls
      const rx = new RegExp(patternOrKey.source, patternOrKey.flags.replace('g', ''));
      for (const key of Array.from(this.cache.keys())) {
        if (rx.test(key)) {
          this.cache.delete(key);
          this.abortKey(key);
        }
      }
    }
  }

  abortKey(key: string): void {
    const inflight = this.inFlight.get(key);
    if (inflight) {
      inflight.controller.abort();
      this.inFlight.delete(key);
    }
  }

  abortAll(): void {
    for (const [key, inflight] of Array.from(this.inFlight.entries())) {
      inflight.controller.abort();
      this.inFlight.delete(key);
    }
  }

  /**
   * Removes any cached entries belonging to other users.
   */
  enforceUserScope(currentUserScope: string): void {
    for (const [key, entry] of Array.from(this.cache.entries())) {
      if (entry.userScope && entry.userScope !== currentUserScope) {
        this.cache.delete(key);
        this.abortKey(key);
      }
    }
  }

  clearUserScope(userScope?: string): void {
    this.epoch++;
    this.abortAll();
    if (!userScope) {
      this.cache.clear();
      return;
    }
    for (const [key, entry] of Array.from(this.cache.entries())) {
      if (entry.userScope === userScope || !entry.userScope) {
        this.cache.delete(key);
      }
    }
  }

  clearAll(): void {
    this.epoch++;
    this.abortAll();
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }

  get inFlightCount(): number {
    return this.inFlight.size;
  }

  get currentEpoch(): number {
    return this.epoch;
  }
}

export const queryCache = new QueryCache();
