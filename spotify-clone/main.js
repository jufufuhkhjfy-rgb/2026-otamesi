const { app, BrowserWindow, ipcMain, dialog, protocol, net } = require('electron');

protocol.registerSchemesAsPrivileged([
  { scheme: 'localfile', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } }
]);
const path = require('path');
const fs = require('fs');
const url = require('url');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#121212',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: false
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  protocol.handle('localfile', (request) => {
    const filePath = decodeURIComponent(request.url.slice('localfile://'.length));
    return net.fetch('file:///' + filePath.replace(/\\/g, '/'));
  });

  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// フォルダ選択ダイアログ
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '音楽フォルダを選択'
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

// MP3ファイル一覧取得
ipcMain.handle('get-music-files', async (event, folderPath) => {
  const supportedExts = ['.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac'];

  function scanDir(dirPath) {
    let files = [];
    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        if (entry.isDirectory()) {
          files = files.concat(scanDir(fullPath));
        } else if (supportedExts.includes(path.extname(entry.name).toLowerCase())) {
          files.push({
            path: fullPath,
            name: path.basename(entry.name, path.extname(entry.name)),
            ext: path.extname(entry.name),
            folder: path.basename(dirPath)
          });
        }
      }
    } catch (e) {}
    return files;
  }

  return scanDir(folderPath);
});

// 音声ファイル読み込み
ipcMain.handle('read-audio-file', async (event, filePath) => {
  try {
    const data = fs.readFileSync(filePath);
    return data.toString('base64');
  } catch (e) {
    return null;
  }
});

// ウィンドウ操作
ipcMain.on('window-minimize', () => mainWindow.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow.close());
