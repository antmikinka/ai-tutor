const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Settings management
  getSettings: () => ipcRenderer.invoke('get-settings'),
  updateSettings: (settings) => ipcRenderer.invoke('update-settings', settings),

  // File operations
  openFile: () => ipcRenderer.invoke('open-file-dialog'),
  saveFile: () => ipcRenderer.invoke('save-file-dialog'),

  // System information
  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),

  // Backend management
  restartBackend: () => ipcRenderer.invoke('restart-backend'),

  // Communication channels
  on: (channel, func) => {
    const validChannels = ['show-help', 'backend-status', 'audio-data', 'math-response'];
    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, func);
    }
  },
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  },

  // Path utilities
  getAppPath: () => {
    return process.resourcesPath || '';
  },

  // Version information
  getVersion: () => process.versions.electron,
  getAppVersion: () => process.env.APP_VERSION || '1.0.0'
});

// Window controls
contextBridge.exposeInMainWorld('windowControls', {
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close')
});

// Security - prevent access to Node.js globals
delete window.require;
delete window.exports;
delete window.module;