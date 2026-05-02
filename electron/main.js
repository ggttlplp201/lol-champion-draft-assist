const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const PORT = 5001;

// In dev: __dirname = .../LOL/electron  → project root is one level up
// In packaged app: resources are at process.resourcesPath/app
const IS_PACKED = app.isPackaged;
const PROJECT_ROOT = IS_PACKED
  ? path.join(process.resourcesPath, 'app')
  : path.join(__dirname, '..');

let mainWindow = null;
let tray = null;
let flaskProc = null;

function getPython() {
  const candidates = [
    path.join(PROJECT_ROOT, 'venv', 'bin', 'python'),
    path.join(PROJECT_ROOT, 'venv', 'bin', 'python3'),
    '/usr/bin/python3',
    'python3',
    'python',
  ];
  for (const p of candidates) {
    if (p.startsWith('/') && !fs.existsSync(p)) continue;
    return p;
  }
  return 'python3';
}

function startFlask() {
  let bin, args, cwd;

  if (IS_PACKED) {
    // Packaged app: use the bundled PyInstaller binary
    const exeName = process.platform === 'win32' ? 'DraftAdvisorServer.exe' : 'DraftAdvisorServer';
    bin  = path.join(process.resourcesPath, 'server', exeName);
    args = [];
    cwd  = process.resourcesPath;
    console.log('[electron] using bundled server:', bin);
  } else {
    // Dev mode: spawn via venv Python
    bin  = getPython();
    args = [path.join(PROJECT_ROOT, 'web_server.py')];
    cwd  = PROJECT_ROOT;
    console.log('[electron] python:', bin);
  }

  flaskProc = spawn(bin, args, {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });

  flaskProc.stdout.on('data', d => process.stdout.write('[flask] ' + d));
  flaskProc.stderr.on('data', d => process.stderr.write('[flask] ' + d));
  flaskProc.on('exit', code => console.log('[flask] exited with code', code));
}

function waitForServer(retries = 40) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      const req = http.get(`http://127.0.0.1:${PORT}/`, res => {
        res.resume();
        resolve();
      });
      req.on('error', () => {
        if (n <= 0) return reject(new Error('Flask server did not start in time'));
        setTimeout(() => attempt(n - 1), 500);
      });
      req.setTimeout(800, () => req.destroy());
    };
    attempt(retries);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 800,
    minWidth: 860,
    minHeight: 600,
    title: 'Draft Advisor',
    webPreferences: { nodeIntegration: false, contextIsolation: true, preload: path.join(__dirname, 'preload.js') },
  });

  mainWindow.loadURL(`http://127.0.0.1:${PORT}/`);
  mainWindow.on('closed', () => { mainWindow = null; });

  ipcMain.on('window-minimize', () => { mainWindow?.minimize(); });

  // Float above fullscreen windows (works over League windowed/borderless)
  mainWindow.setAlwaysOnTop(true, 'floating');
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
}

function createTray() {
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip('Draft Advisor');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show', click: () => { mainWindow ? mainWindow.show() : createWindow(); } },
    {
      label: 'Always on Top', type: 'checkbox', checked: true,
      click: (item) => mainWindow?.setAlwaysOnTop(item.checked, 'floating'),
    },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]));
}

app.whenReady().then(async () => {
  startFlask();
  try {
    await waitForServer();
    console.log('[electron] Flask ready');
  } catch (e) {
    console.error('[electron]', e.message);
  }
  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  // On macOS keep the process alive in the tray
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
});

app.on('before-quit', () => {
  if (flaskProc) { flaskProc.kill('SIGTERM'); flaskProc = null; }
});
