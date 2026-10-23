/**
 * Safe, scoped draft persistence using sessionStorage.
 * Preserves temporary unsaved form state across accidental navigation.
 * Never stores authentication credentials, bearer tokens, or sensitive cookies.
 */

export interface StoredDraft<T = any> {
  schemaVersion: 1;
  userScope: string;
  projectScope?: string;
  draftType: string;
  data: T;
  updatedAt: number;
  expiresAt: number;
}

const STORAGE_PREFIX = 'va_draft_';
const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

function buildStorageKey(userScope: string, draftType: string, projectScope?: string): string {
  const safeUser = encodeURIComponent(userScope.trim());
  const safeType = encodeURIComponent(draftType.trim());
  const safeProj = projectScope ? encodeURIComponent(projectScope.trim()) : 'global';
  return `${STORAGE_PREFIX}${safeUser}_${safeType}_${safeProj}`;
}

export function saveDraft<T>(
  userScope: string,
  draftType: string,
  data: T,
  projectScope?: string,
  ttlMs = DEFAULT_TTL_MS
): void {
  if (!userScope || !draftType || data === undefined || data === null) return;
  try {
    const key = buildStorageKey(userScope, draftType, projectScope);
    const draft: StoredDraft<T> = {
      schemaVersion: 1,
      userScope: userScope.trim(),
      projectScope: projectScope ? projectScope.trim() : undefined,
      draftType: draftType.trim(),
      data,
      updatedAt: Date.now(),
      expiresAt: Date.now() + ttlMs
    };
    sessionStorage.setItem(key, JSON.stringify(draft));
  } catch {
    // Graceful handling of private browsing or quota limitations
  }
}

export function getDraft<T>(
  userScope: string,
  draftType: string,
  projectScope?: string
): T | null {
  if (!userScope || !draftType) return null;
  try {
    const key = buildStorageKey(userScope, draftType, projectScope);
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;

    const parsed: StoredDraft<T> = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;

    if (parsed.schemaVersion !== 1) {
      clearDraft(userScope, draftType, projectScope);
      return null;
    }

    if (parsed.userScope !== userScope.trim()) {
      return null;
    }

    if (projectScope && parsed.projectScope !== projectScope.trim()) {
      return null;
    }

    if (Date.now() > parsed.expiresAt) {
      clearDraft(userScope, draftType, projectScope);
      return null;
    }

    return parsed.data;
  } catch {
    clearDraft(userScope, draftType, projectScope);
    return null;
  }
}

export function clearDraft(
  userScope: string,
  draftType: string,
  projectScope?: string
): void {
  if (!userScope || !draftType) return;
  try {
    const key = buildStorageKey(userScope, draftType, projectScope);
    sessionStorage.removeItem(key);
  } catch {
    // Ignore
  }
}

export function clearUserDrafts(userScope: string): void {
  if (!userScope) return;
  try {
    const prefix = `${STORAGE_PREFIX}${encodeURIComponent(userScope.trim())}_`;
    const toRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith(prefix)) {
        toRemove.push(k);
      }
    }
    toRemove.forEach(k => sessionStorage.removeItem(k));
  } catch {
    // Ignore
  }
}

export function clearAllDrafts(): void {
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith(STORAGE_PREFIX)) {
        toRemove.push(k);
      }
    }
    toRemove.forEach(k => sessionStorage.removeItem(k));
  } catch {
    // Ignore
  }
}
