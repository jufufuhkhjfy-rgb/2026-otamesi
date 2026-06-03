const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  getMusicFiles: (folderPath) => ipcRenderer.invoke('get-music-files', folderPath),
  readAudioFile: (filePath) => ipcRenderer.invoke('read-audio-file', filePath),
  checkYtdlp: () => ipcRenderer.invoke('check-ytdlp'),
  downloadYtdlp: (url, outputDir) => ipcRenderer.invoke('download-ytdlp', url, outputDir),
  getDownloadDir: () => ipcRenderer.invoke('get-download-dir'),
  onYtdlpProgress: (cb) => ipcRenderer.on('ytdlp-progress', (_, msg) => cb(msg)),
  windowMinimize: () => ipcRenderer.send('window-minimize'),
  windowMaximize: () => ipcRenderer.send('window-maximize'),
  windowClose: () => ipcRenderer.send('window-close')
});
