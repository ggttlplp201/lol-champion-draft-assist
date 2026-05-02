const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('draftAdvisor', {
  minimize: () => ipcRenderer.send('window-minimize'),
});
