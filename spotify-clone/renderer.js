'use strict';

// ===== Firebase初期化 =====
firebase.initializeApp(FIREBASE_CONFIG);
const db = firebase.database();

// ===== ユーザー情報 =====
let myUserId = localStorage.getItem('userId');
if (!myUserId) {
  myUserId = 'user_' + Math.random().toString(36).substr(2, 9);
  localStorage.setItem('userId', myUserId);
}
let myName = localStorage.getItem('userName') || '';

function initNameModal() {
  const overlay = document.getElementById('name-modal-overlay');
  const input = document.getElementById('name-input');
  const btn = document.getElementById('name-submit-btn');
  const titlebarUser = document.getElementById('titlebar-user');

  if (myName) {
    overlay.style.display = 'none';
    titlebarUser.textContent = myName;
    initFirebase();
    return;
  }

  overlay.style.display = 'flex';
  input.focus();

  function submit() {
    const name = input.value.trim();
    if (!name) return;
    myName = name;
    localStorage.setItem('userName', name);
    overlay.style.display = 'none';
    titlebarUser.textContent = name;
    initFirebase();
  }

  btn.addEventListener('click', submit);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
}

function initFirebase() {
  // オンライン時に自分のデータを登録、オフライン時に削除
  const myRef = db.ref('users/' + myUserId);
  myRef.update({ name: myName, song: '', artist: '', isPlaying: false, timestamp: Date.now() });
  myRef.onDisconnect().remove();

  // フレンド一覧をリアルタイム監視
  db.ref('users').on('value', (snapshot) => {
    renderFriends(snapshot.val());
  });
}

function renderFriends(data) {
  const list = document.getElementById('friends-list');
  if (!data) {
    list.innerHTML = '<div class="friends-empty">フレンドがいません</div>';
    return;
  }

  const entries = Object.entries(data).filter(([id]) => id !== myUserId);
  if (entries.length === 0) {
    list.innerHTML = '<div class="friends-empty">フレンドがいません</div>';
    return;
  }

  list.innerHTML = entries.map(([id, user]) => {
    const initial = (user.name || '?')[0].toUpperCase();
    const isPlaying = user.isPlaying && user.song;
    const statusText = isPlaying ? escapeHtml(user.song) : '停止中';
    return `
      <div class="friend-item">
        <div class="friend-avatar" style="background:${stringToColor(user.name || '')}">${escapeHtml(initial)}</div>
        <div class="friend-info">
          <div class="friend-name">${escapeHtml(user.name || '不明')}</div>
          <div class="friend-status ${isPlaying ? 'playing' : ''}">
            ${isPlaying ? '<span class="friend-bars"><span></span><span></span><span></span></span>' : ''}
            ${statusText}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function stringToColor(str) {
  const colors = ['#e91e63','#9c27b0','#3f51b5','#2196f3','#009688','#ff5722','#795548','#607d8b'];
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function updateFirebaseStatus(song, artist, isPlaying) {
  if (!myUserId || !myName) return;
  db.ref('users/' + myUserId).update({ song: song || '', artist: artist || '', isPlaying: !!isPlaying, timestamp: Date.now() });
}

// ===== 状態管理 =====
const state = {
  tracks: [],
  filteredTracks: [],
  currentIndex: -1,
  isPlaying: false,
  isShuffle: false,
  repeatMode: 0, // 0: off, 1: all, 2: one
  isMuted: false,
  volume: 0.7,
  favorites: new Set(JSON.parse(localStorage.getItem('favorites') || '[]')),
  folders: JSON.parse(localStorage.getItem('folders') || '[]'),
  currentView: 'library' // 'library' | 'favorites'
};

// ===== DOM参照 =====
const audio = document.getElementById('audio-player');
const elems = {
  welcomeScreen: document.getElementById('welcome-screen'),
  trackListContainer: document.getElementById('track-list-container'),
  trackList: document.getElementById('track-list'),
  playlistList: document.getElementById('playlist-list'),
  playerTrackName: document.getElementById('player-track-name'),
  playerTrackArtist: document.getElementById('player-track-artist'),
  playerAlbumArt: document.getElementById('player-album-art'),
  btnPlayPause: document.getElementById('btn-play-pause'),
  iconPlay: document.querySelector('.icon-play'),
  iconPause: document.querySelector('.icon-pause'),
  timeCurrent: document.getElementById('time-current'),
  timeTotal: document.getElementById('time-total'),
  progressBar: document.getElementById('progress-bar'),
  progressFill: document.getElementById('progress-fill'),
  progressThumb: document.getElementById('progress-thumb'),
  volumeBar: document.getElementById('volume-bar'),
  volumeFill: document.getElementById('volume-fill'),
  volumeThumb: document.getElementById('volume-thumb'),
  btnShuffle: document.getElementById('btn-shuffle'),
  btnRepeat: document.getElementById('btn-repeat'),
  btnMute: document.getElementById('btn-mute'),
  iconVolume: document.querySelector('.icon-volume'),
  iconMute: document.querySelector('.icon-mute'),
  searchInput: document.getElementById('search-input'),
  playerFavoriteBtn: document.getElementById('player-favorite-btn'),
  navLibrary: document.getElementById('nav-library'),
  navFavorites: document.getElementById('nav-favorites'),
  contentArea: document.getElementById('content-area')
};

// ===== ユーティリティ =====
function formatTime(sec) {
  if (!isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function saveFavorites() {
  localStorage.setItem('favorites', JSON.stringify([...state.favorites]));
}

function saveFolders() {
  localStorage.setItem('folders', JSON.stringify(state.folders));
}

function parseTags(track) {
  // ファイル名からアーティスト/タイトルを推定
  // 例: "Artist - Title" or "Title"
  const name = track.name;
  const sep = name.indexOf(' - ');
  if (sep > 0) {
    return {
      title: name.substring(sep + 3).trim(),
      artist: name.substring(0, sep).trim()
    };
  }
  return { title: name, artist: track.folder || 'Unknown' };
}

// ===== 曲リスト描画 =====
function renderTrackList(tracks) {
  if (tracks.length === 0) {
    elems.trackList.innerHTML = '<div style="padding:32px;color:var(--text-subdued);text-align:center">曲が見つかりません</div>';
    return;
  }

  elems.trackList.innerHTML = tracks.map((track, i) => {
    const tags = parseTags(track);
    const isPlaying = state.filteredTracks[state.currentIndex] === track && state.isPlaying;
    const globalIdx = state.filteredTracks.indexOf(track);
    return `
      <div class="track-item ${globalIdx === state.currentIndex ? 'playing' : ''}" data-index="${globalIdx}">
        <span class="track-num">
          ${globalIdx === state.currentIndex
            ? '<span class="playing-bars"><span class="playing-bar"></span><span class="playing-bar"></span><span class="playing-bar"></span></span>'
            : `<span class="num-text">${i + 1}</span>`}
        </span>
        <div class="track-title-col">
          <span class="track-name">${escapeHtml(tags.title)}</span>
          <span class="track-artist">${escapeHtml(tags.artist)}</span>
        </div>
        <span class="track-album">${escapeHtml(track.folder)}</span>
        <span class="track-duration" data-path="${escapeHtml(track.path)}">--</span>
      </div>
    `;
  }).join('');

  // 曲長の非同期取得
  tracks.forEach((track, i) => {
    const el = elems.trackList.querySelector(`[data-path="${CSS.escape(track.path)}"]`);
    if (!el) return;
    const tmpAudio = new Audio();
    tmpAudio.src = `localfile://${track.path.replace(/\\/g, '/')}`;
    tmpAudio.addEventListener('loadedmetadata', () => {
      if (el) el.textContent = formatTime(tmpAudio.duration);
    }, { once: true });
  });

  // クリックイベント
  elems.trackList.querySelectorAll('.track-item').forEach(item => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.dataset.index);
      if (idx === state.currentIndex) {
        togglePlayPause();
      } else {
        playTrack(idx);
      }
    });
    item.addEventListener('dblclick', () => {
      const idx = parseInt(item.dataset.index);
      playTrack(idx);
    });
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderPlaylistSidebar() {
  if (state.folders.length === 0) {
    elems.playlistList.innerHTML = '<div class="playlist-empty">フォルダを追加してください</div>';
    return;
  }
  elems.playlistList.innerHTML = state.folders.map((folder, i) => {
    const name = folder.split(/[\\/]/).pop();
    return `<div class="playlist-item" data-folder="${escapeHtml(folder)}">${escapeHtml(name)}</div>`;
  }).join('');

  elems.playlistList.querySelectorAll('.playlist-item').forEach(item => {
    item.addEventListener('click', () => {
      const folder = item.dataset.folder;
      const folderTracks = state.tracks.filter(t => t.path.startsWith(folder));
      state.filteredTracks = folderTracks;
      showTrackList();
      renderTrackList(folderTracks);
      elems.playlistList.querySelectorAll('.playlist-item').forEach(p => p.classList.remove('active'));
      item.classList.add('active');
    });
  });
}

// ===== 再生制御 =====
function playTrack(index) {
  if (index < 0 || index >= state.filteredTracks.length) return;
  state.currentIndex = index;
  const track = state.filteredTracks[index];
  const tags = parseTags(track);

  audio.src = `localfile://${track.path.replace(/\\/g, '/')}`;
  audio.play().catch(console.error);
  state.isPlaying = true;

  elems.playerTrackName.textContent = tags.title;
  elems.playerTrackArtist.textContent = tags.artist;
  elems.playerAlbumArt.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>`;

  updatePlayIcon();
  updateFavoriteBtn();
  renderCurrentView();
  updateFirebaseStatus(tags.title, tags.artist, true);
}

function togglePlayPause() {
  if (state.currentIndex === -1) {
    if (state.filteredTracks.length > 0) playTrack(0);
    return;
  }
  if (state.isPlaying) {
    audio.pause();
    state.isPlaying = false;
    updateFirebaseStatus(elems.playerTrackName.textContent, elems.playerTrackArtist.textContent, false);
  } else {
    audio.play().catch(console.error);
    state.isPlaying = true;
    updateFirebaseStatus(elems.playerTrackName.textContent, elems.playerTrackArtist.textContent, true);
  }
  updatePlayIcon();
  renderCurrentView();
}

function playNext() {
  if (state.filteredTracks.length === 0) return;
  if (state.repeatMode === 2) {
    audio.currentTime = 0;
    audio.play();
    return;
  }
  let next;
  if (state.isShuffle) {
    next = Math.floor(Math.random() * state.filteredTracks.length);
  } else {
    next = state.currentIndex + 1;
    if (next >= state.filteredTracks.length) {
      if (state.repeatMode === 1) next = 0;
      else { state.isPlaying = false; updatePlayIcon(); return; }
    }
  }
  playTrack(next);
}

function playPrev() {
  if (state.filteredTracks.length === 0) return;
  if (audio.currentTime > 3) {
    audio.currentTime = 0;
    return;
  }
  let prev = state.currentIndex - 1;
  if (prev < 0) prev = state.filteredTracks.length - 1;
  playTrack(prev);
}

function updatePlayIcon() {
  if (state.isPlaying) {
    elems.iconPlay.style.display = 'none';
    elems.iconPause.style.display = 'block';
  } else {
    elems.iconPlay.style.display = 'block';
    elems.iconPause.style.display = 'none';
  }
}

function updateFavoriteBtn() {
  if (state.currentIndex === -1) return;
  const track = state.filteredTracks[state.currentIndex];
  if (!track) return;
  if (state.favorites.has(track.path)) {
    elems.playerFavoriteBtn.classList.add('active');
    elems.playerFavoriteBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`;
  } else {
    elems.playerFavoriteBtn.classList.remove('active');
    elems.playerFavoriteBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z"/></svg>`;
  }
}

// ===== ビュー管理 =====
function showTrackList() {
  elems.welcomeScreen.style.display = 'none';
  elems.trackListContainer.style.display = 'block';
}

function renderCurrentView() {
  if (state.currentView === 'favorites') {
    const favTracks = state.tracks.filter(t => state.favorites.has(t.path));
    state.filteredTracks = favTracks;
    renderTrackList(favTracks);
  } else {
    renderTrackList(state.filteredTracks);
  }
}

// ===== プログレスバー =====
audio.addEventListener('timeupdate', () => {
  if (!audio.duration) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  elems.progressFill.style.width = `${pct}%`;
  elems.progressThumb.style.left = `${pct}%`;
  elems.timeCurrent.textContent = formatTime(audio.currentTime);
});

audio.addEventListener('loadedmetadata', () => {
  elems.timeTotal.textContent = formatTime(audio.duration);
});

audio.addEventListener('ended', playNext);

// プログレスバークリック
let isDraggingProgress = false;

function seekTo(e) {
  const rect = elems.progressBar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  if (audio.duration) audio.currentTime = audio.duration * pct;
}

elems.progressBar.addEventListener('mousedown', (e) => {
  isDraggingProgress = true;
  seekTo(e);
});

document.addEventListener('mousemove', (e) => {
  if (isDraggingProgress) seekTo(e);
});

document.addEventListener('mouseup', () => {
  isDraggingProgress = false;
});

// ===== 音量 =====
audio.volume = state.volume;
elems.volumeFill.style.width = `${state.volume * 100}%`;
elems.volumeThumb.style.left = `${state.volume * 100}%`;

let isDraggingVolume = false;

function setVolume(e) {
  const rect = elems.volumeBar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  state.volume = pct;
  audio.volume = pct;
  elems.volumeFill.style.width = `${pct * 100}%`;
  elems.volumeThumb.style.left = `${pct * 100}%`;
  if (state.isMuted && pct > 0) {
    state.isMuted = false;
    elems.iconVolume.style.display = 'block';
    elems.iconMute.style.display = 'none';
  }
}

elems.volumeBar.addEventListener('mousedown', (e) => {
  isDraggingVolume = true;
  setVolume(e);
});

document.addEventListener('mousemove', (e) => {
  if (isDraggingVolume) setVolume(e);
});

document.addEventListener('mouseup', () => {
  isDraggingVolume = false;
});

elems.btnMute.addEventListener('click', () => {
  state.isMuted = !state.isMuted;
  audio.muted = state.isMuted;
  if (state.isMuted) {
    elems.iconVolume.style.display = 'none';
    elems.iconMute.style.display = 'block';
  } else {
    elems.iconVolume.style.display = 'block';
    elems.iconMute.style.display = 'none';
  }
});

// ===== キーボードショートカット =====
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.code === 'Space') { e.preventDefault(); togglePlayPause(); }
  if (e.code === 'ArrowRight') { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 5); }
  if (e.code === 'ArrowLeft') { audio.currentTime = Math.max(0, audio.currentTime - 5); }
  if (e.code === 'ArrowUp') { state.volume = Math.min(1, state.volume + 0.05); audio.volume = state.volume; elems.volumeFill.style.width = `${state.volume * 100}%`; elems.volumeThumb.style.left = `${state.volume * 100}%`; }
  if (e.code === 'ArrowDown') { state.volume = Math.max(0, state.volume - 0.05); audio.volume = state.volume; elems.volumeFill.style.width = `${state.volume * 100}%`; elems.volumeThumb.style.left = `${state.volume * 100}%`; }
  if (e.code === 'KeyN') playNext();
  if (e.code === 'KeyP') playPrev();
});

// ===== ボタンイベント =====
elems.btnPlayPause.addEventListener('click', togglePlayPause);
document.getElementById('btn-next').addEventListener('click', playNext);
document.getElementById('btn-prev').addEventListener('click', playPrev);

elems.btnShuffle.addEventListener('click', () => {
  state.isShuffle = !state.isShuffle;
  elems.btnShuffle.classList.toggle('active', state.isShuffle);
});

elems.btnRepeat.addEventListener('click', () => {
  state.repeatMode = (state.repeatMode + 1) % 3;
  elems.btnRepeat.classList.toggle('active', state.repeatMode > 0);
  if (state.repeatMode === 2) {
    elems.btnRepeat.title = 'リピート(1曲)';
  } else if (state.repeatMode === 1) {
    elems.btnRepeat.title = 'リピート(全曲)';
  } else {
    elems.btnRepeat.title = 'リピート';
  }
});

elems.playerFavoriteBtn.addEventListener('click', () => {
  if (state.currentIndex === -1) return;
  const track = state.filteredTracks[state.currentIndex];
  if (!track) return;
  if (state.favorites.has(track.path)) {
    state.favorites.delete(track.path);
  } else {
    state.favorites.add(track.path);
  }
  saveFavorites();
  updateFavoriteBtn();
  if (state.currentView === 'favorites') renderCurrentView();
});

// ===== フォルダ追加 =====
async function addFolder() {
  const folderPath = await window.electronAPI.selectFolder();
  if (!folderPath) return;

  if (!state.folders.includes(folderPath)) {
    state.folders.push(folderPath);
    saveFolders();
  }

  const newFiles = await window.electronAPI.getMusicFiles(folderPath);
  // 重複除去
  const existingPaths = new Set(state.tracks.map(t => t.path));
  const unique = newFiles.filter(f => !existingPaths.has(f.path));
  state.tracks.push(...unique);
  state.filteredTracks = state.tracks;

  renderPlaylistSidebar();
  showTrackList();
  renderTrackList(state.filteredTracks);
}

document.getElementById('btn-add-folder').addEventListener('click', addFolder);
document.getElementById('welcome-add-folder').addEventListener('click', addFolder);

// ===== ナビゲーション =====
elems.navLibrary.addEventListener('click', () => {
  state.currentView = 'library';
  state.filteredTracks = state.tracks;
  elems.navLibrary.classList.add('active');
  elems.navFavorites.classList.remove('active');
  if (state.tracks.length > 0) {
    showTrackList();
    renderTrackList(state.filteredTracks);
  } else {
    elems.trackListContainer.style.display = 'none';
    elems.welcomeScreen.style.display = 'flex';
  }
});

elems.navFavorites.addEventListener('click', () => {
  state.currentView = 'favorites';
  const favTracks = state.tracks.filter(t => state.favorites.has(t.path));
  state.filteredTracks = favTracks;
  elems.navFavorites.classList.add('active');
  elems.navLibrary.classList.remove('active');
  showTrackList();
  renderTrackList(favTracks);
});

// ===== 検索 =====
elems.searchInput.addEventListener('input', () => {
  const q = elems.searchInput.value.toLowerCase();
  const base = state.currentView === 'favorites'
    ? state.tracks.filter(t => state.favorites.has(t.path))
    : state.tracks;

  if (!q) {
    state.filteredTracks = base;
  } else {
    state.filteredTracks = base.filter(t => {
      const tags = parseTags(t);
      return tags.title.toLowerCase().includes(q) || tags.artist.toLowerCase().includes(q) || t.folder.toLowerCase().includes(q);
    });
  }
  renderTrackList(state.filteredTracks);
});

// ===== ウィンドウボタン =====
document.getElementById('btn-minimize').addEventListener('click', () => window.electronAPI.windowMinimize());
document.getElementById('btn-maximize').addEventListener('click', () => window.electronAPI.windowMaximize());
document.getElementById('btn-close').addEventListener('click', () => window.electronAPI.windowClose());

// ===== 起動時: 保存済みフォルダを読み込み =====
async function init() {
  if (state.folders.length === 0) return;

  for (const folder of state.folders) {
    try {
      const files = await window.electronAPI.getMusicFiles(folder);
      const existingPaths = new Set(state.tracks.map(t => t.path));
      state.tracks.push(...files.filter(f => !existingPaths.has(f.path)));
    } catch (e) {}
  }

  if (state.tracks.length > 0) {
    state.filteredTracks = state.tracks;
    renderPlaylistSidebar();
    showTrackList();
    renderTrackList(state.filteredTracks);
  }
}

init();
initNameModal();
