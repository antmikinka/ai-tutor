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

export const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const base = await resolveBackendUrl();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? body);
  }
  return body as T;
};

export const newClientId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `ui-${crypto.randomUUID()}`;
  }
  return `ui-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
};
