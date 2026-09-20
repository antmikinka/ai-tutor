/**
 * Renderer-side view of the API exposed by src/main/preload.js via
 * contextBridge. Keep in sync with that file.
 */

export interface ElectronSettings {
  backendUrl?: string;
  windowBounds?: { width: number; height: number; x?: number; y?: number };
  [key: string]: unknown;
}

export interface ElectronSystemInfo {
  platform: string;
  arch: string;
  version: string;
  electronVersion: string;
  nodeVersion: string;
  chromeVersion: string;
  isPackaged: boolean;
  memory: { total: number; free: number };
  cpu: { model: string; cores: number };
}

export type BackendEvent = 'backend-status' | 'backend-log';

export interface ElectronAPI {
  getSettings: () => Promise<ElectronSettings>;
  updateSettings: (settings: Record<string, unknown>) => Promise<boolean>;

  openFile: () => Promise<{ canceled: boolean; filePaths: string[] }>;
  saveFile: (options: { defaultPath?: string; data: string; encoding?: 'utf8' | 'base64' }) => Promise<{ canceled: boolean; filePath?: string }>;

  getSystemInfo: () => Promise<ElectronSystemInfo>;
  getAppVersion: () => Promise<string>;
  getBackendUrl: () => Promise<string>;
  restartBackend: () => Promise<boolean>;

  on: (channel: BackendEvent, listener: (payload: unknown) => void) => () => void;
}

export interface WindowControls {
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
    windowControls?: WindowControls;
  }
}
