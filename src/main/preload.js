const { contextBridge, ipcRenderer } = require('electron');

// Channels the main process may push to the renderer.
const PUSH_CHANNELS = new Set(['backend-status', 'backend-log']);

/**
 * Minimal, explicit bridge. Every function maps to exactly one ipcMain.handle
 * in main.js; the renderer never receives the raw ipcRenderer or event object.
 * Keep src/renderer/src/electron.d.ts in sync with this surface.
 */
contextBridge.exposeInMainWorld('electronAPI', {
  getSettings: () => ipcRenderer.invoke('get-settings'),
  updateSettings: (settings) => ipcRenderer.invoke('update-settings', settings),

  openFile: () => ipcRenderer.invoke('open-file-dialog'),
  saveFile: (options) => ipcRenderer.invoke('save-file-dialog', options),

  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),

  /** Subscribe to a push channel; returns an unsubscribe function. */
  on: (channel, listener) => {
    if (!PUSH_CHANNELS.has(channel)) throw new Error(`Unknown channel: ${channel}`);
    const wrapped = (_event, payload) => listener(payload);
    ipcRenderer.on(channel, wrapped);
    return () => ipcRenderer.removeListener(channel, wrapped);
  },
});

contextBridge.exposeInMainWorld('windowControls', {
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close'),
});
