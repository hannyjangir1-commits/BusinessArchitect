import { SessionData, Project, ModuleDetail, RoadmapTask, RoadmapSummary, CopilotMessage, RoadmapPlanningInputs } from '../types';

let csrfTokenCache = '';

export function getCsrfToken(): string {
  if (typeof document !== 'undefined' && document.cookie) {
    const match = document.cookie.match(/(?:^|;\s*)aba_csrf=([^;]+)/);
    if (match) {
      csrfTokenCache = decodeURIComponent(match[1]);
      return csrfTokenCache;
    }
  }
  return csrfTokenCache;
}

export function setCsrfToken(token: string) {
  csrfTokenCache = token;
}

export function clearCsrfToken() {
  csrfTokenCache = '';
}

interface RequestOptions extends RequestInit {
  _isCsrfRetry?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Inject CSRF token on mutating requests
  const method = (options.method || 'GET').toUpperCase();
  const isMutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);

  if (isMutating) {
    let token = getCsrfToken();
    if (!token && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register') && !endpoint.includes('/auth/me')) {
      try {
        const authMeUrl = endpoint.startsWith('/api/admin') ? '/api/admin/auth/me' : '/api/auth/me';
        const meRes = await fetch(authMeUrl, { credentials: 'include' });
        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.csrf_token) {
            setCsrfToken(meData.csrf_token);
            token = meData.csrf_token;
          }
        }
      } catch {
        // Fallback to whatever token is available
      }
    }
    if (token) {
      headers.set('X-CSRF-Token', token);
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90000); // 90s timeout for long-running AI requests

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Send HTTP-only session cookie
      signal: options.signal || controller.signal
    });
  } catch (fetchErr: any) {
    if (fetchErr.name === 'AbortError') {
      throw new Error('Request timed out after 90 seconds. Please check your connection and retry.');
    }
    throw fetchErr;
  } finally {
    clearTimeout(timeoutId);
  }

  if (response.status === 401) {
    // Session expired or unauthenticated
    clearCsrfToken();
    if (!endpoint.includes('/auth/me')) {
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
  }

  // Bounded safe retry on CSRF token mismatch
  if (response.status === 403 && !options._isCsrfRetry) {
    let errorDetail = '';
    try {
      const errClone = response.clone();
      const errJson = await errClone.json();
      errorDetail = (errJson.detail || errJson.message || '').toString();
    } catch {
      try {
        const errClone = response.clone();
        errorDetail = await errClone.text();
      } catch {
        // ignore
      }
    }

    if (errorDetail.toLowerCase().includes('csrf')) {
      clearCsrfToken();
      const authMeUrl = endpoint.startsWith('/api/admin') ? '/api/admin/auth/me' : '/api/auth/me';
      try {
        const meRes = await fetch(authMeUrl, { credentials: 'include' });
        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.csrf_token) {
            setCsrfToken(meData.csrf_token);
            const retryHeaders = new Headers(options.headers || {});
            retryHeaders.set('X-CSRF-Token', meData.csrf_token);
            return await request<T>(endpoint, {
              ...options,
              headers: retryHeaders,
              _isCsrfRetry: true
            });
          }
        }
      } catch {
        // Fall through to standard error throw
      }
    }
  }

  if (!response.ok) {
    let errorDetail: any = 'An unexpected error occurred';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    const err = new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
    (err as any).status = response.status;
    (err as any).data = errorDetail;
    if (typeof errorDetail === 'string' && errorDetail.toLowerCase().includes('csrf')) {
      (err as any).isCsrfError = true;
    }
    throw err;
  }

  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response.text() as unknown as T;
}

export const api = {
  auth: {
    register: async (payload: any): Promise<SessionData> => {
      const res = await request<SessionData>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      if (res.csrf_token) setCsrfToken(res.csrf_token);
      return res;
    },
    login: async (email_or_username: string, password: string): Promise<SessionData> => {
      const res = await request<SessionData>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email_or_username, password })
      });
      if (res.csrf_token) setCsrfToken(res.csrf_token);
      return res;
    },
    logout: async (): Promise<void> => {
      await request('/api/auth/logout', { method: 'POST' });
      csrfTokenCache = '';
    },
    getMe: async (): Promise<SessionData> => {
      const res = await request<SessionData>('/api/auth/me');
      if (res.csrf_token) setCsrfToken(res.csrf_token);
      return res;
    },
    updateProfile: (data: { username?: string; email?: string }): Promise<any> =>
      request('/api/auth/profile', {
        method: 'PUT',
        body: JSON.stringify(data)
      }),
    changePassword: (data: { current_password: string; new_password: string; confirm_new_password: string }): Promise<any> =>
      request('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify(data)
      })
  },

  projects: {
    list: (): Promise<Project[]> => request<Project[]>('/api/projects'),
    create: (data: any): Promise<Project> => request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    get: (id: string): Promise<Project> => request<Project>(`/api/projects/${id}`),
    update: (id: string, data: any): Promise<Project> => request<Project>(`/api/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
    updateActiveModule: (id: string, activeModule: string): Promise<any> => request(`/api/projects/${id}/active-module`, {
      method: 'PATCH',
      body: JSON.stringify({ active_module: activeModule })
    }),
    delete: (id: string): Promise<any> => request(`/api/projects/${id}`, { method: 'DELETE' }),
    bulkDelete: (projectIds: string[]): Promise<{ deleted_count: number; deleted_ids: string[]; message: string }> =>
      request('/api/projects/bulk-delete', {
        method: 'POST',
        body: JSON.stringify({ project_ids: projectIds })
      })
  },

  modules: {
    get: (projectId: string, moduleType: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}`),

    generate: (projectId: string, moduleType: string, planningInputs?: RoadmapPlanningInputs): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/generate`, {
        method: 'POST',
        body: planningInputs ? JSON.stringify(planningInputs) : undefined
      }),

    modify: (projectId: string, moduleType: string, instruction: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/modify`, {
        method: 'POST',
        body: JSON.stringify({ instruction })
      }),

    resolveConflict: (
      projectId: string,
      moduleType: string,
      replaceVersionId: string,
      instruction?: string,
      newData?: any,
      newVersionName?: string,
      changeSummary?: string
    ): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/resolve-conflict`, {
        method: 'POST',
        body: JSON.stringify({
          replace_version_id: replaceVersionId,
          instruction: instruction,
          new_data: newData,
          new_version_name: newVersionName,
          change_summary: changeSummary
        })
      }),

    renameVersion: (projectId: string, moduleType: string, versionId: string, versionName: string) =>
      request(`/api/projects/${projectId}/modules/${moduleType}/versions/${versionId}/rename`, {
        method: 'PATCH',
        body: JSON.stringify({ version_name: versionName })
      }),

    deleteVersion: (projectId: string, moduleType: string, versionId: string) =>
      request(`/api/projects/${projectId}/modules/${moduleType}/versions/${versionId}`, {
        method: 'DELETE'
      }),

    restoreVersion: (projectId: string, moduleType: string, versionId: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/versions/${versionId}/restore`, {
        method: 'POST'
      })
  },

  tasks: {
    list: (projectId: string, params?: { timeline?: string; status?: string; search?: string }): Promise<RoadmapTask[]> => {
      const searchParams = new URLSearchParams();
      if (params?.timeline) searchParams.set('timeline', params.timeline);
      if (params?.status) searchParams.set('status', params.status);
      if (params?.search) searchParams.set('search', params.search);
      const q = searchParams.toString();
      return request<RoadmapTask[]>(`/api/projects/${projectId}/tasks${q ? `?${q}` : ''}`);
    },

    getSummary: (projectId: string): Promise<RoadmapSummary> =>
      request<RoadmapSummary>(`/api/projects/${projectId}/tasks/summary`),

    create: (projectId: string, data: any): Promise<RoadmapTask> =>
      request<RoadmapTask>(`/api/projects/${projectId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    update: (projectId: string, taskId: string, data: any): Promise<RoadmapTask> =>
      request<RoadmapTask>(`/api/projects/${projectId}/tasks/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),

    delete: (projectId: string, taskId: string) =>
      request(`/api/projects/${projectId}/tasks/${taskId}`, { method: 'DELETE' })
  },

  copilot: {
    getHistory: (projectId: string): Promise<CopilotMessage[]> =>
      request<CopilotMessage[]>(`/api/projects/${projectId}/copilot`),

    sendMessage: (projectId: string, message: string): Promise<CopilotMessage> =>
      request<CopilotMessage>(`/api/projects/${projectId}/copilot`, {
        method: 'POST',
        body: JSON.stringify({ message })
      })
  },

  exports: {
    downloadFullProjectPdf: (projectId: string, projectName: string) => {
      const url = `/api/projects/${projectId}/export/pdf`;
      const link = document.createElement('a');
      link.href = url;
      link.download = `${projectName.toLowerCase().replace(/\s+/g, '_')}_blueprint.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },

    downloadModulePdf: (projectId: string, moduleType: string, projectName: string) => {
      const url = `/api/projects/${projectId}/export/modules/${moduleType}/pdf`;
      const link = document.createElement('a');
      link.href = url;
      link.download = `${projectName.toLowerCase().replace(/\s+/g, '_')}_${moduleType}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  },

  admin: {
    auth: {
      login: async (username: string, password: string) => {
        const res = await request<{ user: any; csrf_token: string; permissions: string[] }>('/api/admin/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password })
        });
        if (res.csrf_token) setCsrfToken(res.csrf_token);
        return res;
      },
      logout: async () => {
        await request('/api/admin/auth/logout', { method: 'POST' });
        clearCsrfToken();
      },
      getMe: async () => {
        const res = await request<{ user: any; csrf_token: string; permissions: string[] }>('/api/admin/auth/me');
        if (res.csrf_token) setCsrfToken(res.csrf_token);
        return res;
      },
      changePassword: (data: { current_password: string; new_password: string; confirm_new_password: string }) =>
        request('/api/admin/auth/change-password', {
          method: 'POST',
          body: JSON.stringify(data)
        }),
      getSessions: () =>
        request<any[]>('/api/admin/auth/sessions'),
      revokeSession: (sessionId: string) =>
        request<any>(`/api/admin/auth/sessions/${sessionId}/revoke`, { method: 'POST' }),
      revokeOtherSessions: () =>
        request<any>('/api/admin/auth/sessions/revoke-others', { method: 'POST' })
    },
    dashboard: {
      getStats: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/dashboard/stats${qs ? `?${qs}` : ''}`);
      },
      getTrends: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/dashboard/trends${qs ? `?${qs}` : ''}`);
      }
    },
    users: {
      list: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/users${qs ? `?${qs}` : ''}`);
      },
      get: (userId: string) =>
        request<any>(`/api/admin/users/${userId}`),
      create: (data: { username: string; email: string; password?: string; role?: string }) =>
        request<any>('/api/admin/users', {
          method: 'POST',
          body: JSON.stringify(data)
        }),
      update: (userId: string, data: { email?: string; role?: string; is_suspended?: boolean; suspension_reason?: string }) =>
        request<any>(`/api/admin/users/${userId}`, {
          method: 'PUT',
          body: JSON.stringify(data)
        }),
      suspend: (userId: string, reason: string) =>
        request<any>(`/api/admin/users/${userId}/suspend`, {
          method: 'POST',
          body: JSON.stringify({ reason })
        }),
      reactivate: (userId: string) =>
        request<any>(`/api/admin/users/${userId}/reactivate`, { method: 'POST' }),
      revokeSessions: (userId: string) =>
        request<any>(`/api/admin/users/${userId}/revoke-sessions`, { method: 'POST' }),
      delete: (userId: string, confirmUsername: string) =>
        request<any>(`/api/admin/users/${userId}?confirm_username=${encodeURIComponent(confirmUsername)}`, {
          method: 'DELETE'
        })
    },
    projects: {
      list: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/projects${qs ? `?${qs}` : ''}`);
      },
      get: (projectId: string) =>
        request<any>(`/api/admin/projects/${projectId}`),
      transfer: (projectId: string, newOwnerUsername: string) =>
        request<any>(`/api/admin/projects/${projectId}/transfer`, {
          method: 'POST',
          body: JSON.stringify({ new_owner_username: newOwnerUsername })
        }),
      delete: (projectId: string, confirmProjectName: string) =>
        request<any>(`/api/admin/projects/${projectId}?confirm_project_name=${encodeURIComponent(confirmProjectName)}`, {
          method: 'DELETE'
        })
    },
    aiOps: {
      list: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/ai-operations${qs ? `?${qs}` : ''}`);
      },
      getStats: () =>
        request<any>('/api/admin/ai-operations/stats'),
      getQuality: () =>
        request<any>('/api/admin/ai-operations/quality'),
      retry: (operationId: string) =>
        request<any>(`/api/admin/ai-operations/${operationId}/retry`, { method: 'POST' })
    },
    analytics: {
      getOverview: () =>
        request<any>('/api/admin/analytics/overview'),
      listEvents: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/analytics/events${qs ? `?${qs}` : ''}`);
      }
    },
    system: {
      getHealth: () =>
        request<any>('/api/admin/system/health'),
      getDatabase: () =>
        request<any>('/api/admin/system/database'),
      getLogs: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/system/logs${qs ? `?${qs}` : ''}`);
      }
    },
    integrity: {
      scan: () =>
        request<any>('/api/admin/integrity/scan'),
      repair: (action: string, confirmation = true) =>
        request<any>('/api/admin/integrity/repair', {
          method: 'POST',
          body: JSON.stringify({ action, confirmation })
        })
    },
    security: {
      listEvents: (params: Record<string, any> = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request<any>(`/api/admin/security/events${qs ? `?${qs}` : ''}`);
      },
      listSessions: () =>
        request<any>('/api/admin/security/sessions'),
      revokeSession: (sessionId: string) =>
        request<any>(`/api/admin/security/sessions/${sessionId}/revoke`, { method: 'POST' }),
      revokeAllSessions: () =>
        request<any>('/api/admin/security/sessions/revoke-all', { method: 'POST' })
    },
    audit: {
      list: (params: Record<string, any> = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request<any>(`/api/admin/audit-logs${qs ? `?${qs}` : ''}`);
      }
    },
    config: {
      get: () =>
        request<any>('/api/admin/configuration'),
      update: (settings: Record<string, string>) =>
        request<any>('/api/admin/configuration', {
          method: 'POST',
          body: JSON.stringify({ settings })
        })
    },
    maintenance: {
      getStatus: () =>
        request<any>('/api/admin/maintenance/status'),
      toggle: (enabled: boolean, reason?: string) =>
        request<any>('/api/admin/maintenance/toggle', {
          method: 'POST',
          body: JSON.stringify({ enabled, reason })
        }),
      pruneSessions: () =>
        request<any>('/api/admin/maintenance/prune-sessions', { method: 'POST' })
    },
    reports: {
      downloadCsv: (reportType: string) => {
        window.open(`/api/admin/reports/export-csv?report_type=${reportType}`, '_blank');
      },
      downloadPdf: () => {
        window.open('/api/admin/reports/summary-pdf', '_blank');
      }
    }
  }
};
