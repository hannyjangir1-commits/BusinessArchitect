/**
 * Lightweight, zero-dependency in-memory query cache & deduplication service.
 * Supports:
 * - In-flight promise reuse (request deduplication)
 * - Stale-while-revalidate freshness semantics
 * - AbortController integration
 * - User-scoped cache isolation and invalidation
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

  /**
   * Fetch with request deduplication and stale-while-revalidate caching.
   * If a request for the same key is already in flight, reuses the existing promise.
   * If fresh data is in cache, returns it immediately.
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

    // 1. Fresh cache hit
    if (cached && !forceFresh) {
      if (now < cached.staleAt) {
        return cached.data as T;
      }
      // Stale cache hit: return cached data immediately and revalidate in background
      this.revalidateInBackground(key, fetcher, staleTimeMs, userScope);
      return cached.data as T;
    }

    // 2. Reuse in-flight request if present (request deduplication)
    const existing = this.inFlight.get(key);
    if (existing) {
      return existing.promise as Promise<T>;
    }

    // 3. Launch new fetch
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
        this.cache.set(key, {
          data,
          timestamp: Date.now(),
          staleAt: Date.now() + staleTimeMs,
          userScope
        });
        return data;
      } finally {
        this.inFlight.delete(key);
      }
    })();

    this.inFlight.set(key, {
      promise,
      controller,
      timestamp: now
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

    const controller = new AbortController();
    const promise = (async () => {
      try {
        const data = await fetcher(controller.signal);
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
      timestamp: Date.now()
    });
  }

  getCached<T>(key: string): T | undefined {
    const entry = this.cache.get(key);
    return entry ? (entry.data as T) : undefined;
  }

  isFresh(key: string): boolean {
    const entry = this.cache.get(key);
    return !!entry && Date.now() < entry.staleAt;
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
      for (const key of Array.from(this.cache.keys())) {
        if (patternOrKey.test(key)) {
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

  clearUserScope(userScope?: string): void {
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
    this.abortAll();
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }

  get inFlightCount(): number {
    return this.inFlight.size;
  }
}

export const queryCache = new QueryCache();
