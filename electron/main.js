const { app, BrowserWindow, shell, dialog } = require('electron');
const path   = require('path');
const { spawn, execSync } = require('child_process');
const http   = require('http');
const fs     = require('fs');

let mainWindow;
let flaskProcess;

/* ── Resolve paths (works both in dev and packaged .exe) ── */
function resourcePath(...parts) {
  return app.isPackaged
    ? path.join(process.resourcesPath, ...parts)
    : path.join(__dirname, '..', ...parts);
}

/* ── Check if Flask is already running ── */
function waitForFlask(port, tries, resolve, reject) {
  http.get(`http://127.0.0.1:${port}/`, res => {
    resolve();
  }).on('error', () => {
    if (tries <= 0) { reject(new Error('Flask did not start in time.')); return; }
    setTimeout(() => waitForFlask(port, tries - 1, resolve, reject), 500);
  });
}

/* ── Start the Python / Flask backend ── */
async function startFlask() {
  const backendDir = resourcePath('backend');
  const appPy      = path.join(backendDir, 'app.py');

  /* Find python executable */
  let python = 'python';
  const venvPy = path.join(resourcePath(''), 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPy)) python = venvPy;

  console.log('[Electron] Starting Flask:', python, appPy);

  flaskProcess = spawn(python, [appPy], {
    cwd: resourcePath(''),
    env: { ...process.env, FLASK_ENV: 'production' },
    stdio: ['ignore', 'pipe', 'pipe']
  });

  flaskProcess.stdout.on('data', d => console.log('[Flask]', d.toString().trim()));
  flaskProcess.stderr.on('data', d => console.error('[Flask]', d.toString().trim()));
  flaskProcess.on('exit', code => console.log('[Flask] exited with code', code));

  /* Wait up to 15 s for Flask to be ready */
  await new Promise((res, rej) => waitForFlask(5000, 30, res, rej));
  console.log('[Electron] Flask is ready.');
}

/* ── Create the browser window ── */
function createWindow() {
  mainWindow = new BrowserWindow({
    width:  1400,
    height: 900,
    minWidth:  900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0d0d1a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'icon.ico'),
    title: 'LeadGenerator ERP',
  });

  /* Load the frontend */
  const indexHtml = resourcePath('frontend', 'index.html');
  mainWindow.loadFile(indexHtml);

  /* Open external links in the system browser */
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

/* ── App lifecycle ── */
app.whenReady().then(async () => {
  try {
    await startFlask();
  } catch (err) {
    dialog.showErrorBox(
      'Backend failed to start',
      `Could not start the Python backend:\n\n${err.message}\n\nMake sure Python is installed.`
    );
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (flaskProcess) { flaskProcess.kill(); console.log('[Electron] Flask killed.'); }
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (flaskProcess) flaskProcess.kill();
});
