const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  getMusicFiles: (folderPath) => ipcRenderer.invoke('get-music-files', folderPath),
  readAudioFile: (filePath) => ipcRenderer.invoke('read-audio-file', filePath),
  windowMinimize: () => ipcRenderer.send('window-minimize'),
  windowMaximize: () => ipcRenderer.send('window-maximize'),
  windowClose: () => ipcRenderer.send('window-close')
});
