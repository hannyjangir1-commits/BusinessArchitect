/**
 * Lightweight, safe client-side navigation memory.
 * Stores only harmless route preferences in localStorage.
 * Strictly avoids storing tokens, credentials, module content, or full project models.
 */

export interface SavedNavDestination {
  schemaVersion: 1;
  userScope: string;
  projectId: string;
  module: string;
  updatedAt: number;
}

const STORAGE_PREFIX = 'va_nav_dest_';
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

const VALID_MODULES = new Set([
  'overview',
  'bmc',
  'tech_stack',
  'idea_validator',
  'market_research',
  'execution_roadmap',
  'detailed_roadmap',
  'blueprint_copilot'
]);

function getStorageKey(userScope: string): string {
  // Safe sanitized key
  const safeScope = encodeURIComponent(userScope.trim());
  return `${STORAGE_PREFIX}${safeScope}`;
}

export function saveNavDestination(userScope: string, projectId: string, moduleSlug: string): void {
  if (!userScope || !projectId || !moduleSlug) return;
  try {
    const payload: SavedNavDestination = {
      schemaVersion: 1,
      userScope: userScope.trim(),
      projectId: projectId.trim(),
      module: moduleSlug === 'detailed_roadmap' ? 'execution_roadmap' : moduleSlug.trim(),
      updatedAt: Date.now()
    };
    localStorage.setItem(getStorageKey(userScope), JSON.stringify(payload));
  } catch {
    // Gracefully handle storage quota or privacy mode restrictions
  }
}

export function getNavDestination(userScope: string): SavedNavDestination | null {
  if (!userScope) return null;
  try {
    const raw = localStorage.getItem(getStorageKey(userScope));
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;

    // Validate schemaVersion
    if (parsed.schemaVersion !== 1) {
      clearNavDestination(userScope);
      return null;
    }

    // Validate user scope matches
    if (parsed.userScope !== userScope.trim()) {
      return null;
    }

    // Validate expiration
    const age = Date.now() - (parsed.updatedAt || 0);
    if (age < 0 || age > MAX_AGE_MS) {
      clearNavDestination(userScope);
      return null;
    }

    // Validate field formats
    if (typeof parsed.projectId !== 'string' || !parsed.projectId.trim()) {
      clearNavDestination(userScope);
      return null;
    }

    if (typeof parsed.module !== 'string' || !VALID_MODULES.has(parsed.module)) {
      clearNavDestination(userScope);
      return null;
    }

    return {
      schemaVersion: 1,
      userScope: parsed.userScope,
      projectId: parsed.projectId,
      module: parsed.module === 'detailed_roadmap' ? 'execution_roadmap' : parsed.module,
      updatedAt: parsed.updatedAt
    };
  } catch {
    clearNavDestination(userScope);
    return null;
  }
}

export function clearNavDestination(userScope: string): void {
  if (!userScope) return;
  try {
    localStorage.removeItem(getStorageKey(userScope));
  } catch {
    // Ignore
  }
}

export function clearAllNavDestinations(): void {
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(STORAGE_PREFIX)) {
        keysToRemove.push(k);
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
  } catch {
    // Ignore
  }
}
