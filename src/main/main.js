const { app, BrowserWindow, ipcMain, dialog, globalShortcut, screen } = require('electron');
const path = require('path');
const isDev = true; // Force development mode for debugging
const { spawn, exec } = require('child_process');
const log = require('electron-log');
const Store = require('electron-store');
const WebSocket = require('ws');

// Configure logging
log.transports.file.level = 'info';
log.info('AI Math Tutor starting...');

// Initialize electron store for settings
const store = new Store({
  defaults: {
    windowBounds: { width: 1200, height: 800 },
    backendUrl: 'http://localhost:8000',
    websocketUrl: 'ws://localhost:8000',
    audioSettings: {
      inputDevice: 'default',
      outputDevice: 'default',
      volume: 0.8
    },
    modelSettings: {
      temperature: 0.7,
      maxTokens: 2048,
      useGPU: true
    }
  }
});

let mainWindow;
let backendProcess = null;

/**
 * Create the main application window
 */
function createWindow() {
  const { width, height } = store.get('windowBounds');
  const primaryDisplay = screen.getPrimaryDisplay();
  const { workArea } = primaryDisplay;

  mainWindow = new BrowserWindow({
    width: Math.min(width, workArea.width - 100),
    height: Math.min(height, workArea.height - 100),
    minWidth: 800,
    minHeight: 600,
    x: workArea.x + (workArea.width - width) / 2,
    y: workArea.y + (workArea.height - height) / 2,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      allowRunningInsecureContent: false,
      experimentalFeatures: false,
      // Content Security Policy
      contentSecurityPolicy: {
        defaultSrc: "'self'",
        scriptSrc: "'self' 'unsafe-inline' 'unsafe-eval' http://localhost:3000",
        styleSrc: "'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
        fontSrc: "'self' https://fonts.gstatic.com https://fonts.googleapis.com",
        imgSrc: "'self' data: https:",
        connectSrc: "'self' ws://localhost:8000 wss://localhost:8000 http://localhost:8000 https://localhost:8000"
      }
    },
    icon: path.join(__dirname, '../../assets/icon.ico'),
    show: false,
    frame: true,
    titleBarStyle: 'default',
    backgroundColor: '#ffffff'
  });

  // Load the app - always use development server for debugging
  console.log('Loading app from development server: http://localhost:3000');
  mainWindow.loadURL('http://localhost:3000');
  mainWindow.webContents.openDevTools();

  // Add console error logging
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    const levels = ['verbose', 'info', 'warning', 'error'];
    console.log(`Renderer ${levels[level]}: ${message}`);

    if (level === 2 || level === 3) { // warning or error
      log.error(`Renderer ${levels[level]}: ${message}`);
    }
  });

  // Add uncaught exception handler for renderer
  mainWindow.webContents.on('crashed', () => {
    console.error('Renderer process crashed');
    log.error('Renderer process crashed');
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    log.info('Main window shown');
  });

  // Window state management
  mainWindow.on('resize', () => {
    const { width, height } = mainWindow.getBounds();
    store.set('windowBounds', { width, height });
  });

  mainWindow.on('close', (e) => {
    if (backendProcess) {
      log.info('Shutting down backend server...');
      backendProcess.kill('SIGTERM');
      backendProcess = null;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Start the Python FastAPI backend server
 */
function startBackendServer() {
  const backendPath = path.join(__dirname, '../backend');
  const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';

  backendProcess = spawn(pythonExecutable, ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'], {
    cwd: backendPath,
    env: { ...process.env, PYTHONPATH: backendPath }
  });

  backendProcess.stdout.on('data', (data) => {
    log.info(`Backend: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    log.error(`Backend Error: ${data}`);
  });

  backendProcess.on('close', (code) => {
    log.info(`Backend process exited with code ${code}`);
    backendProcess = null;
  });
}



/**
 * Set up global keyboard shortcuts
 */
function setupGlobalShortcuts() {
  // F1 for help
  globalShortcut.register('F1', () => {
    if (mainWindow) {
      mainWindow.webContents.send('show-help');
    }
  });

  // Ctrl+Shift+R for reload in development
  if (isDev) {
    globalShortcut.register('CommandOrControl+Shift+R', () => {
      if (mainWindow) {
        mainWindow.webContents.reload();
      }
    });
  }

  // Ctrl+Shift+I for dev tools in development
  if (isDev) {
    globalShortcut.register('CommandOrControl+Shift+I', () => {
      if (mainWindow) {
        mainWindow.webContents.toggleDevTools();
      }
    });
  }
}

/**
 * IPC handlers for renderer process communication
 */
function setupIPCHandlers() {
  // Get app settings
  ipcMain.handle('get-settings', () => {
    return store.store;
  });

  // Update app settings
  ipcMain.handle('update-settings', (event, settings) => {
    store.set(settings);
    return true;
  });

  // Open file dialog for loading images/diagrams
  ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: [
        { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp'] },
        { name: 'PDF Files', extensions: ['pdf'] }
      ]
    });
    return result;
  });

  // Save file dialog for exporting solutions
  ipcMain.handle('save-file-dialog', async () => {
    const result = await dialog.showSaveDialog(mainWindow, {
      filters: [
        { name: 'PDF', extensions: ['pdf'] },
        { name: 'PNG Image', extensions: ['png'] },
        { name: 'Text', extensions: ['txt'] }
      ]
    });
    return result;
  });

  // Get system information
  ipcMain.handle('get-system-info', () => {
    return {
      platform: process.platform,
      arch: process.arch,
      version: app.getVersion(),
      electronVersion: process.versions.electron,
      screens: screen.getAllDisplays()
    };
  });

  // Restart backend server
  ipcMain.handle('restart-backend', () => {
    if (backendProcess) {
      backendProcess.kill('SIGTERM');
    }
    startBackendServer();
    return true;
  });
}

// App lifecycle events
app.whenReady().then(() => {
  log.info('App ready, creating window...');
  createWindow();
  setupGlobalShortcuts();
  setupIPCHandlers();

  // Start backend services
  if (!isDev) {
    startBackendServer();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();

  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  // Clean up resources
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
  }
});

// Error handling
process.on('uncaughtException', (error) => {
  log.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled Rejection at:', promise, 'reason:', reason);
});