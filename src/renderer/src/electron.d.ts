export interface ElectronAPI {
  // Settings management
  getSettings: () => Promise<any>;
  updateSettings: (settings: any) => Promise<boolean>;

  // File operations
  openFile: () => Promise<any>;
  saveFile: () => Promise<any>;

  // System information
  getSystemInfo: () => Promise<any>;

  // Backend management
  restartBackend: () => Promise<boolean>;

  // Communication channels
  on: (channel: string, func: Function) => void;
  removeAllListeners: (channel: string) => void;

  // Path utilities
  getAppPath: () => string;

  // Version information
  getVersion: () => string;
  getAppVersion: () => string;
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