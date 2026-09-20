const { app, BrowserWindow, ipcMain, dialog, screen, session, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const { spawn } = require('child_process');
const log = require('electron-log');
const Store = require('electron-store');

log.transports.file.level = 'info';
log.info(`AI Math Tutor ${app.getVersion()} starting (packaged=${app.isPackaged})`);

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const isDev = !app.isPackaged;
const DEV_SERVER_URL = process.env.ELECTRON_START_URL || 'http://localhost:3000';
const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT = Number(process.env.MATH_TUTOR_BACKEND_PORT) || 8000;
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const BACKEND_START_TIMEOUT_MS = 60_000;

const store = new Store({
  defaults: {
    windowBounds: { width: 1280, height: 840 },
    userSettings: {},
  },
});

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {import('child_process').ChildProcess | null} */
let backendProcess = null;
let backendOwnedByUs = false;
let quitting = false;

// ---------------------------------------------------------------------------
// Backend process management
// ---------------------------------------------------------------------------

function backendDir() {
  return app.isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(__dirname, '..', 'backend');
}

/** Pick the Python interpreter: explicit override > bundled runtime > repo venv > PATH. */
function pythonExecutable() {
  if (process.env.MATH_TUTOR_PYTHON) return process.env.MATH_TUTOR_PYTHON;

  const isWin = process.platform === 'win32';
  const candidates = [
    path.join(process.resourcesPath || '', 'python', isWin ? 'python.exe' : 'bin/python3'),
    path.join(__dirname, '..', '..', 'venv', isWin ? 'Scripts/python.exe' : 'bin/python'),
    path.join(__dirname, '..', '..', '.venv', isWin ? 'Scripts/python.exe' : 'bin/python'),
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  return found || (isWin ? 'python' : 'python3');
}

function probeBackend(timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/health`, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function sendToRenderer(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, payload);
}

function startBackendProcess() {
  const cwd = backendDir();
  const python = pythonExecutable();
  const userData = app.getPath('userData');

  // Runtime state must never be written inside the (read-only) install dir.
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    HOST: BACKEND_HOST,
    PORT: String(BACKEND_PORT),
    DEBUG: 'false',
    ENVIRONMENT: app.isPackaged ? 'production' : 'development',
    DATA_DIR: path.join(userData, 'data'),
    LOG_DIR: path.join(userData, 'logs'),
    UPLOAD_DIR: path.join(userData, 'uploads'),
    TEMP_DIR: path.join(os.tmpdir(), 'ai-math-tutor'),
    MODEL_DIR: process.env.MODEL_DIR || path.join(userData, 'models'),
    MODEL_CACHE_DIR: process.env.MODEL_CACHE_DIR || path.join(userData, 'models', 'cache'),
  };

  log.info(`Starting backend: ${python} main.py (cwd=${cwd}, port=${BACKEND_PORT})`);
  sendToRenderer('backend-status', { state: 'starting', url: BACKEND_URL });

  const child = spawn(python, ['main.py'], { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  backendProcess = child;
  backendOwnedByUs = true;

  const forward = (level) => (chunk) => {
    const text = chunk.toString().trimEnd();
    if (!text) return;
    log[level](`[backend] ${text}`);
    sendToRenderer('backend-log', { level, text });
  };
  child.stdout.on('data', forward('info'));
  child.stderr.on('data', forward('warn'));

  child.on('error', (error) => {
    log.error(`Backend failed to start: ${error.message}`);
    sendToRenderer('backend-status', { state: 'error', message: `Could not start Python (${python}): ${error.message}` });
  });
  child.on('exit', (code, signal) => {
    log.info(`Backend exited (code=${code}, signal=${signal})`);
    if (backendProcess === child) backendProcess = null;
    if (!quitting) sendToRenderer('backend-status', { state: 'stopped', code, signal });
  });
}

async function waitForBackend(timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await probeBackend()) return true;
    if (backendOwnedByUs && !backendProcess) return false; // crashed on startup
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function ensureBackend() {
  if (process.env.MATH_TUTOR_SKIP_BACKEND === '1') {
    log.info('MATH_TUTOR_SKIP_BACKEND=1: not managing the backend');
    return;
  }
  if (await probeBackend()) {
    log.info(`Backend already running at ${BACKEND_URL}; reusing it`);
    backendOwnedByUs = false;
    sendToRenderer('backend-status', { state: 'ready', url: BACKEND_URL, managed: false });
    return;
  }
  startBackendProcess();
  const ready = await waitForBackend(BACKEND_START_TIMEOUT_MS);
  if (ready) {
    log.info('Backend is ready');
    sendToRenderer('backend-status', { state: 'ready', url: BACKEND_URL, managed: true });
  } else {
    log.error('Backend did not become healthy in time');
    sendToRenderer('backend-status', { state: 'error', message: 'The Python backend did not start. Check the logs.' });
  }
}

function stopBackend() {
  const child = backendProcess;
  if (!child || !backendOwnedByUs) return Promise.resolve();
  backendProcess = null;
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      try {
        child.kill('SIGKILL');
      } catch (_) {
        /* already gone */
      }
      resolve();
    }, 5000);
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
    try {
      if (process.platform === 'win32') {
        // SIGTERM is not delivered to Python on Windows; taskkill the tree instead.
        spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true });
      } else {
        child.kill('SIGTERM');
      }
    } catch (error) {
      log.warn(`Failed to signal backend: ${error.message}`);
      resolve();
    }
  });
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

function installContentSecurityPolicy() {
  const devServer = isDev ? ` ${DEV_SERVER_URL} ${DEV_SERVER_URL.replace(/^http/, 'ws')}` : '';
  const wsBackend = BACKEND_URL.replace(/^http/, 'ws');
  const csp = [
    "default-src 'self'",
    // CRA dev server injects inline scripts / eval for HMR; production build does not need them.
    `script-src 'self'${isDev ? " 'unsafe-inline' 'unsafe-eval'" : ''}${devServer}`,
    "style-src 'self' 'unsafe-inline'", // MUI/emotion inject style tags
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    "media-src 'self' data: blob:",
    `connect-src 'self' ${BACKEND_URL} ${wsBackend}${devServer}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'none'",
  ].join('; ');

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({ responseHeaders: { ...details.responseHeaders, 'Content-Security-Policy': [csp] } });
  });
}

function createWindow() {
  const saved = store.get('windowBounds');
  const { workArea } = screen.getPrimaryDisplay();
  const width = Math.min(saved.width, workArea.width);
  const height = Math.min(saved.height, workArea.height);

  mainWindow = new BrowserWindow({
    width,
    height,
    x: saved.x ?? Math.round(workArea.x + (workArea.width - width) / 2),
    y: saved.y ?? Math.round(workArea.y + (workArea.height - height) / 2),
    minWidth: 900,
    minHeight: 640,
    show: false,
    backgroundColor: '#f5f5f5',
    icon: path.join(__dirname, '..', '..', 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL(DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'build', 'index.html'));
  }

  mainWindow.once('ready-to-show', () => mainWindow && mainWindow.show());

  // External links open in the OS browser, never inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    const allowed = isDev ? url.startsWith(DEV_SERVER_URL) : url.startsWith('file://');
    if (!allowed) event.preventDefault();
  });

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    log.error(`Renderer process gone: ${details.reason}`);
  });
  mainWindow.webContents.on('console-message', (_event, level, message) => {
    if (level >= 2) log.warn(`[renderer] ${message}`);
  });

  let boundsTimer = null;
  const persistBounds = () => {
    clearTimeout(boundsTimer);
    boundsTimer = setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isMaximized()) {
        store.set('windowBounds', mainWindow.getBounds());
      }
    }, 300);
  };
  mainWindow.on('resize', persistBounds);
  mainWindow.on('move', persistBounds);
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------

function setupIpc() {
  ipcMain.handle('get-settings', () => ({ ...store.store, backendUrl: BACKEND_URL }));

  ipcMain.handle('update-settings', (_event, patch) => {
    if (!patch || typeof patch !== 'object') return false;
    for (const [key, value] of Object.entries(patch)) {
      if (key === 'backendUrl') continue; // derived, not user-settable
      store.set(key, value);
    }
    return true;
  });

  ipcMain.handle('get-backend-url', () => BACKEND_URL);
  ipcMain.handle('get-app-version', () => app.getVersion());

  ipcMain.handle('get-system-info', () => ({
    platform: process.platform,
    arch: process.arch,
    version: app.getVersion(),
    electronVersion: process.versions.electron,
    nodeVersion: process.versions.node,
    chromeVersion: process.versions.chrome,
    isPackaged: app.isPackaged,
    memory: { total: os.totalmem(), free: os.freemem() },
    cpu: { model: os.cpus()[0]?.model || 'unknown', cores: os.cpus().length },
  }));

  ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'] }],
    });
    return { canceled: result.canceled, filePaths: result.filePaths };
  });

  ipcMain.handle('save-file-dialog', async (_event, options) => {
    if (!options || typeof options.data !== 'string') throw new Error('save-file requires { data }');
    const encoding = options.encoding === 'base64' ? 'base64' : 'utf8';
    const ext = path.extname(options.defaultPath || '').replace('.', '') || 'txt';
    const result = await dialog.showSaveDialog(mainWindow, {
      defaultPath: options.defaultPath,
      filters: [{ name: ext.toUpperCase(), extensions: [ext] }, { name: 'All files', extensions: ['*'] }],
    });
    if (result.canceled || !result.filePath) return { canceled: true };
    await fs.promises.writeFile(result.filePath, Buffer.from(options.data, encoding));
    return { canceled: false, filePath: result.filePath };
  });

  ipcMain.handle('restart-backend', async () => {
    if (!backendOwnedByUs && (await probeBackend())) {
      log.info('Backend is externally managed; not restarting');
      return false;
    }
    await stopBackend();
    await ensureBackend();
    return true;
  });

  ipcMain.handle('window-minimize', () => mainWindow?.minimize());
  ipcMain.handle('window-maximize', () => (mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize()));
  ipcMain.handle('window-close', () => mainWindow?.close());
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    installContentSecurityPolicy();
    setupIpc();
    createWindow();
    ensureBackend().catch((error) => log.error(`ensureBackend failed: ${error.message}`));

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });

  app.on('before-quit', (event) => {
    if (quitting || !backendProcess) return;
    quitting = true;
    event.preventDefault();
    stopBackend().finally(() => app.quit());
  });
}

process.on('uncaughtException', (error) => log.error('Uncaught exception:', error));
process.on('unhandledRejection', (reason) => log.error('Unhandled rejection:', reason));
