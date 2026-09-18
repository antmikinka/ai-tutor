/**
 * Backend location + typed REST helper.
 *
 * Resolution order for the HTTP base URL:
 *   1. `backendUrl` from Electron settings (main process knows the port it spawned)
 *   2. REACT_APP_BACKEND_URL at build time
 *   3. http://127.0.0.1:8000
 */

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';

let cachedBaseUrl: string | null = null;

export const resolveBackendUrl = async (): Promise<string> => {
  if (cachedBaseUrl) return cachedBaseUrl;

  let url = process.env.REACT_APP_BACKEND_URL || DEFAULT_BACKEND_URL;
  if (window.electronAPI?.getSettings) {
    try {
      const settings = await window.electronAPI.getSettings();
      if (settings?.backendUrl) url = settings.backendUrl;
    } catch (error) {
      console.warn('Could not read backend URL from Electron settings:', error);
    }
  }
  cachedBaseUrl = url.replace(/\/+$/, '');
  return cachedBaseUrl;
};

export const resetBackendUrlCache = () => {
  cachedBaseUrl = null;
};

export const toWebSocketUrl = (httpBase: string, clientId: string): string => {
  const ws = httpBase.replace(/^http/, 'ws');
  return `${ws}/ws/${encodeURIComponent(clientId)}`;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const describeDetail = (detail: unknown): unknown => {
  // FastAPI validation errors arrive as a list of {loc, msg}; flatten to a sentence.
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? `${(d as { loc?: unknown[] }).loc?.slice(-1)[0] ?? ''}: ${(d as { msg: string }).msg}` : String(d)))
      .join('; ');
  }
  return detail;
};

export const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const base = await resolveBackendUrl();
  // Let the browser set the multipart boundary for FormData bodies.
  const headers: Record<string, string> =
    init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { ...headers, ...((init?.headers as Record<string, string>) || {}) },
  });
  const text = await response.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) {
    throw new ApiError(response.status, describeDetail(body?.detail ?? body) ?? `HTTP ${response.status}`);
  }
  return body as T;
};

export const apiJson = <T>(path: string, method: 'POST' | 'PUT' | 'DELETE', payload?: unknown): Promise<T> =>
  apiFetch<T>(path, { method, body: payload === undefined ? undefined : JSON.stringify(payload) });

export const apiUpload = <T>(path: string, form: FormData): Promise<T> => apiFetch<T>(path, { method: 'POST', body: form });

export const newClientId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `ui-${crypto.randomUUID()}`;
  }
  return `ui-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
};
