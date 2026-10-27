import {
  SessionData, Project, ModuleDetail, RoadmapTask, RoadmapSummary,
  CopilotMessage, CopilotSendResult, CopilotOperationStatus,
  RoadmapPlanningInputs, TechStackPlanningInputs,
  ProjectKnowledgeItem, KnowledgeLink, FinancialWorksheet, CopilotProposalResponse
} from '../types';

let csrfTokenCache = '';

export function getCsrfToken(): string {
  if (typeof document !== 'undefined' && document.cookie) {
    const match = document.cookie.match(/(?:^|;\s*)aba_csrf=([^;]+)/);
    if (match) {
      try { csrfTokenCache = decodeURIComponent(match[1]); } catch { csrfTokenCache = match[1]; }
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

export class ApiError extends Error {
  status: number;
  data: any;
  code?: string;
  constructor(message: string, status: number, data: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
    this.code = typeof data === 'object' && data ? data.error : undefined;
  }
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
  let timedOut = false;
  const abortFromCaller = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) abortFromCaller();
  else options.signal?.addEventListener('abort', abortFromCaller, { once: true });
  const timeoutId = setTimeout(() => { timedOut = true; controller.abort(); }, 300000); // Bounded timeout for the two-stage generation pipeline

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Send HTTP-only session cookie
      signal: controller.signal
    });
  } catch (fetchErr: any) {
    if (timedOut) {
      throw new Error('The request took longer than five minutes. Reload the module to check whether it was saved before retrying.');
    }
    if (options.signal?.aborted) throw new Error('The request was cancelled.');
    throw fetchErr;
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener('abort', abortFromCaller);
  }

  if (response.status === 401) {
    // Session expired or unauthenticated
    clearCsrfToken();
    if (!endpoint.includes('/auth/me') && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
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
    const raw = await response.text();
    let detail: any = raw || `Request failed (${response.status}).`;
    try { const parsed = JSON.parse(raw); detail = parsed.detail ?? parsed.message ?? parsed; } catch { /* Plain-text server error. */ }
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map(item => `${(item.loc || []).slice(1).join('.')}: ${item.msg || 'Invalid value'}`).join('; ')
      : detail.message || detail.error || 'The request could not be completed.';
    const err = new ApiError(message, response.status, detail);
    (err as any).isCsrfError = message.toLowerCase().includes('csrf');
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

async function downloadFile(url: string, filename: string) {
  try {
    const response = await fetch(url, { credentials: 'include' });
    if (!response.ok) {
      const text = await response.text();
      let message = `Export failed (${response.status}).`;
      try { const data = JSON.parse(text); message = data.detail?.message || data.detail || data.message || message; } catch { /* Use status on non-JSON failure. */ }
      throw new Error(typeof message === 'string' ? message : 'Export could not be completed.');
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (error: any) {
    window.alert(error.message || 'Export could not be downloaded. Please try again.');
  }
}

export const api = {
  health: (): Promise<{ status: string; database_connected: boolean; generation_configured: boolean; generation_model?: string; configured_generation_keys?: number; available_generation_keys?: number; generation_provider_status?: string }> =>
    request('/api/health'),

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
    getMe: async (options?: { signal?: AbortSignal }): Promise<SessionData> => {
      const res = await request<SessionData>('/api/auth/me', { signal: options?.signal });
      if (res.csrf_token) setCsrfToken(res.csrf_token);
      return res;
    },
    updateProfile: (data: { username?: string; email?: string; display_name?: string; preferences?: { font: 'system' | 'mono' } }): Promise<any> =>
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
    list: (options?: { signal?: AbortSignal }): Promise<Project[]> => request<Project[]>('/api/projects', { signal: options?.signal }),
    create: (data: any): Promise<Project> => request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    get: (id: string, options?: { signal?: AbortSignal }): Promise<Project> => request<Project>(`/api/projects/${id}`, { signal: options?.signal }),
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
    get: (projectId: string, moduleType: string, options?: { signal?: AbortSignal }): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}`, { signal: options?.signal }),

    delete: (projectId: string, moduleType: string): Promise<{ message: string; module_type: string; deleted_records: number; deleted_tasks: number }> =>
      request(`/api/projects/${projectId}/modules/${moduleType}`, { method: 'DELETE' }),

    generate: (projectId: string, moduleType: string, planningInputs?: RoadmapPlanningInputs | TechStackPlanningInputs | Record<string, any>): Promise<ModuleDetail> =>
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
    list: (projectId: string, params?: { timeline?: string; status?: string; search?: string }, options?: { signal?: AbortSignal }): Promise<RoadmapTask[]> => {
      const searchParams = new URLSearchParams();
      if (params?.timeline) searchParams.set('timeline', params.timeline);
      if (params?.status) searchParams.set('status', params.status);
      if (params?.search) searchParams.set('search', params.search);
      const q = searchParams.toString();
      return request<RoadmapTask[]>(`/api/projects/${projectId}/tasks${q ? `?${q}` : ''}`, { signal: options?.signal });
    },

    getSummary: (projectId: string, options?: { signal?: AbortSignal }): Promise<RoadmapSummary> =>
      request<RoadmapSummary>(`/api/projects/${projectId}/tasks/summary`, { signal: options?.signal }),

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
    getPage: (projectId: string, beforeCursor?: string, limit = 50, options?: { signal?: AbortSignal }): Promise<{
      messages: CopilotMessage[];
      has_more: boolean;
      before_cursor?: string | null;
      total_count: number;
    }> => {
      const searchParams = new URLSearchParams();
      if (limit) searchParams.set('limit', limit.toString());
      if (beforeCursor) searchParams.set('before_cursor', beforeCursor);
      const q = searchParams.toString();
      return request<{
        messages: CopilotMessage[];
        has_more: boolean;
        before_cursor?: string | null;
        total_count: number;
      }>(`/api/projects/${projectId}/copilot/page${q ? `?${q}` : ''}`, { signal: options?.signal });
    },

    getHistory: (projectId: string, params?: { limit?: number; offset?: number; order?: 'asc' | 'desc'; before_id?: string; before_cursor?: string }, options?: { signal?: AbortSignal }): Promise<CopilotMessage[]> => {
      const searchParams = new URLSearchParams();
      if (params?.limit) searchParams.set('limit', params.limit.toString());
      if (params?.offset !== undefined) searchParams.set('offset', params.offset.toString());
      if (params?.order) searchParams.set('order', params.order);
      if (params?.before_id) searchParams.set('before_id', params.before_id);
      if (params?.before_cursor) searchParams.set('before_cursor', params.before_cursor);
      const q = searchParams.toString();
      return request<CopilotMessage[]>(`/api/projects/${projectId}/copilot${q ? `?${q}` : ''}`, { signal: options?.signal });
    },

    getLatestHistory: async (projectId: string, limit = 50): Promise<CopilotMessage[]> => {
      const page = await api.copilot.getPage(projectId, undefined, limit);
      return page.messages;
    },

    getOlderHistory: async (projectId: string, beforeCursor: string, limit = 50): Promise<CopilotMessage[]> => {
      const page = await api.copilot.getPage(projectId, beforeCursor, limit);
      return page.messages;
    },

    sendMessage: (projectId: string, message: string, clientMsgId?: string): Promise<CopilotSendResult> =>
      request<CopilotSendResult>(`/api/projects/${projectId}/copilot`, {
        method: 'POST',
        body: JSON.stringify({ message, client_msg_id: clientMsgId })
      }),

    getOperationStatus: (projectId: string, clientMsgId: string): Promise<CopilotOperationStatus> =>
      request<CopilotOperationStatus>(`/api/projects/${projectId}/copilot/operations/${encodeURIComponent(clientMsgId)}`),

    proposeChange: (projectId: string, target_module: string, instruction: string): Promise<CopilotProposalResponse> =>
      request<CopilotProposalResponse>(`/api/projects/${projectId}/copilot/propose`, {
        method: 'POST',
        body: JSON.stringify({ target_module, instruction })
      })
  },

  knowledge: {
    list: (projectId: string, itemType?: string): Promise<ProjectKnowledgeItem[]> => {
      const qs = itemType ? `?item_type=${encodeURIComponent(itemType)}` : '';
      return request<ProjectKnowledgeItem[]>(`/api/projects/${projectId}/knowledge${qs}`);
    },
    create: (projectId: string, data: Partial<ProjectKnowledgeItem>): Promise<ProjectKnowledgeItem> =>
      request<ProjectKnowledgeItem>(`/api/projects/${projectId}/knowledge`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    update: (projectId: string, itemId: string, data: Partial<ProjectKnowledgeItem>): Promise<ProjectKnowledgeItem> =>
      request<ProjectKnowledgeItem>(`/api/projects/${projectId}/knowledge/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      }),
    delete: (projectId: string, itemId: string): Promise<void> =>
      request<void>(`/api/projects/${projectId}/knowledge/${itemId}`, {
        method: 'DELETE'
      }),
    createLink: (projectId: string, data: { source_id: string; target_id: string; relationship: string }): Promise<KnowledgeLink> =>
      request<KnowledgeLink>(`/api/projects/${projectId}/knowledge/links`, {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    deleteLink: (projectId: string, linkId: string): Promise<void> =>
      request<void>(`/api/projects/${projectId}/knowledge/links/${linkId}`, {
        method: 'DELETE'
      }),
  },

  financials: {
    get: (projectId: string): Promise<FinancialWorksheet> =>
      request<FinancialWorksheet>(`/api/projects/${projectId}/financials`),
    update: (projectId: string, data: Partial<FinancialWorksheet>): Promise<FinancialWorksheet> =>
      request<FinancialWorksheet>(`/api/projects/${projectId}/financials`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),
  },

  exports: {
    downloadFullProjectPdf: (projectId: string, projectName: string) =>
      downloadFile(`/api/projects/${projectId}/export/pdf`, `${projectName.replace(/[^a-z0-9_-]/gi, '_')}_blueprint.pdf`),
    downloadModulePdf: (projectId: string, moduleType: string, projectName: string) =>
      downloadFile(`/api/projects/${projectId}/export/modules/${moduleType}/pdf`, `${projectName.replace(/[^a-z0-9_-]/gi, '_')}_${moduleType}.pdf`)
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
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/dashboard/stats${qs ? `?${qs}` : ''}`);
      },
      getTrends: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
        const qs = new URLSearchParams(clean).toString();
        return request<any>(`/api/admin/dashboard/trends${qs ? `?${qs}` : ''}`);
      }
    },
    users: {
      list: (params: Record<string, any> = {}) => {
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
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
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
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
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
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
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
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
        const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
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
        void downloadFile(`/api/admin/reports/export-csv?report_type=${encodeURIComponent(reportType)}`, `${reportType}_report.csv`);
      },
      downloadPdf: () => {
        void downloadFile('/api/admin/reports/summary-pdf', 'project_summary.pdf');
      }
    }
  }
};
