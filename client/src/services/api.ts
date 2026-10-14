import { SessionData, Project, ModuleDetail, RoadmapTask, RoadmapSummary, CopilotMessage } from '../types';

let csrfTokenCache = '';

export function getCsrfToken(): string {
  if (csrfTokenCache) return csrfTokenCache;
  const match = document.cookie.match(new RegExp('(^|;\\s*)aba_csrf=([^;]+)'));
  if (match) {
    csrfTokenCache = decodeURIComponent(match[2]);
  }
  return csrfTokenCache;
}

export function setCsrfToken(token: string) {
  csrfTokenCache = token;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Inject CSRF token on mutating requests
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const token = getCsrfToken();
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
    if (!endpoint.includes('/auth/me')) {
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
  }

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    const err = new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
    (err as any).status = response.status;
    (err as any).data = errorDetail;
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
    }
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
    delete: (id: string): Promise<any> => request(`/api/projects/${id}`, { method: 'DELETE' })
  },

  modules: {
    get: (projectId: string, moduleType: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}`),

    generate: (projectId: string, moduleType: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/generate`, {
        method: 'POST'
      }),

    modify: (projectId: string, moduleType: string, instruction: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/modify`, {
        method: 'POST',
        body: JSON.stringify({ instruction })
      }),

    resolveConflict: (projectId: string, moduleType: string, replaceVersionId: string, newData: any, newVersionName?: string, changeSummary?: string): Promise<ModuleDetail> =>
      request<ModuleDetail>(`/api/projects/${projectId}/modules/${moduleType}/resolve-conflict`, {
        method: 'POST',
        body: JSON.stringify({
          replace_version_id: replaceVersionId,
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
  }
};
