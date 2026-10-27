/**
 * Lightweight, zero-dependency in-memory query cache & deduplication service.
 * Supports:
 * - Request identity on in-flight entries (prevents older requests from deleting newer entries)
 * - Multi-subscriber cancellation safety (cancellation by one subscriber does not abort shared request)
 * - Union regex invalidation over both cache and in-flight request keys
 * - Stale-while-revalidate subscriber notifications
 * - User-scoped cache isolation and invalidation
 * - Generation epoch tracking to prevent late responses from repopulating post-logout cache
 * - Bounded LRU cache size (max 150 entries)
 */

export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  staleAt: number;
  userScope?: string;
}

interface InFlightRequest<T> {
  id: string;
  promise: Promise<T>;
  controller: AbortController;
  timestamp: number;
  requestEpoch: number;
  userScope?: string;
  subscribers: number;
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
  private subscribers = new Map<string, Set<(data: any) => void>>();
  private epoch = 0;
  private readonly MAX_CACHE_ENTRIES = 150;

  /**
   * Fetch with request deduplication and stale-while-revalidate caching.
   * If a request for the same key is already in flight, reuses the existing promise and tracks subscribers.
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

    if (signal?.aborted) {
      throw new DOMException('The operation was aborted.', 'AbortError');
    }

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
      existing.subscribers++;
      if (signal) {
        signal.addEventListener(
          'abort',
          () => {
            existing.subscribers--;
            // Only abort the underlying controller if all subscribers have aborted
            if (existing.subscribers <= 0) {
              existing.controller.abort(signal.reason);
            }
          },
          { once: true }
        );
      }
      return existing.promise as Promise<T>;
    }

    // 3. Launch new fetch with epoch tracking and unique entry identity
    const requestEpoch = this.epoch;
    const requestUserScope = userScope;
    const controller = new AbortController();
    const entryId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const entry: InFlightRequest<T> = {
      id: entryId,
      promise: null as any,
      controller,
      timestamp: now,
      requestEpoch,
      userScope: requestUserScope,
      subscribers: 1
    };

    if (signal) {
      signal.addEventListener(
        'abort',
        () => {
          entry.subscribers--;
          if (entry.subscribers <= 0) {
            controller.abort(signal.reason);
          }
        },
        { once: true }
      );
    }

    const promise = (async () => {
      try {
        const data = await fetcher(controller.signal);
        // Epoch & Abort guard: If cache was cleared, user logged out, or request aborted, do NOT write to cache
        if (this.epoch !== requestEpoch || controller.signal.aborted) {
          return data;
        }
        this.setCached(key, data, staleTimeMs, requestUserScope);
        this.notifySubscribers(key, data);
        return data;
      } finally {
        // Precise identity cleanup: only remove from inFlight if THIS entry is still the active one
        if (this.inFlight.get(key) === entry) {
          this.inFlight.delete(key);
        }
      }
    })();

    entry.promise = promise;
    this.inFlight.set(key, entry);

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
    const entryId = `reval_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const entry: InFlightRequest<any> = {
      id: entryId,
      promise: null as any,
      controller,
      timestamp: Date.now(),
      requestEpoch,
      userScope,
      subscribers: 1
    };

    const promise = (async () => {
      try {
        const data = await fetcher(controller.signal);
        // Guard against writing to cache if epoch changed or aborted
        if (this.epoch !== requestEpoch || controller.signal.aborted) {
          return;
        }
        this.setCached(key, data, staleTimeMs, userScope);
        this.notifySubscribers(key, data);
      } catch {
        // Background revalidation failure silently keeps existing stale data
      } finally {
        if (this.inFlight.get(key) === entry) {
          this.inFlight.delete(key);
        }
      }
    })();

    entry.promise = promise as any;
    this.inFlight.set(key, entry);
  }

  /**
   * Subscribe to cache updates (e.g. from background revalidation).
   */
  subscribe(key: string, callback: (data: any) => void): () => void {
    if (!this.subscribers.has(key)) {
      this.subscribers.set(key, new Set());
    }
    const set = this.subscribers.get(key)!;
    set.add(callback);
    return () => {
      set.delete(callback);
      if (set.size === 0) this.subscribers.delete(key);
    };
  }

  private notifySubscribers(key: string, data: any): void {
    const set = this.subscribers.get(key);
    if (set) {
      for (const cb of Array.from(set)) {
        try {
          cb(data);
        } catch (e) {
          console.warn('QueryCache subscriber error:', e);
        }
      }
    }
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
    // Evict oldest entry when capacity is reached
    if (this.cache.size >= this.MAX_CACHE_ENTRIES && !this.cache.has(key)) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) this.cache.delete(oldestKey);
    }
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
      // Invalidate matching keys from the union of cache and in-flight maps
      const allKeys = new Set([...this.cache.keys(), ...this.inFlight.keys()]);
      for (const key of allKeys) {
        if (rx.test(key)) {
          this.cache.delete(key);
          this.abortKey(key);
        }
      }
    }
  }

  invalidatePrefix(prefix: string): void {
    const escaped = prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    this.invalidate(new RegExp(`^${escaped}`));
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
