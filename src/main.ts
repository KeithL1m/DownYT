import { io } from 'socket.io-client';
import { fetchVideoInfo, addToQueue } from './api';
import { initQueue, updateQueueItem, clearActive, clearDownloaded } from './queue';
import type { VideoInfo, PlaylistInfo, QueueItem } from './types';

const socket = io();

const urlInput        = document.getElementById('url-input')          as HTMLInputElement;
const fetchBtn        = document.getElementById('fetch-btn')           as HTMLButtonElement;
const previewSection  = document.getElementById('preview-section')     as HTMLElement;
const errorBanner     = document.getElementById('error-banner')        as HTMLElement;
const errorText       = document.getElementById('error-text')          as HTMLElement;
const errorDismiss    = document.getElementById('error-dismiss')       as HTMLElement;
const queueContainer  = document.getElementById('queue-container')     as HTMLElement;
const downloadedContainer = document.getElementById('downloaded-container') as HTMLElement;
const clearQueueBtn   = document.getElementById('clear-queue-btn')      as HTMLButtonElement;
const clearBtn        = document.getElementById('clear-downloaded-btn') as HTMLButtonElement;

initQueue(queueContainer, downloadedContainer);

// Load existing queue on page load
fetch('/api/queue')
  .then(r => r.json())
  .then((items: QueueItem[]) => items.forEach(item => updateQueueItem(item)))
  .catch(() => {});

socket.on('queue_update', (item: QueueItem) => updateQueueItem(item));

fetchBtn.addEventListener('click', handleFetch);
urlInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleFetch(); });
errorDismiss.addEventListener('click', () => setError(''));
clearQueueBtn.addEventListener('click', () => clearActive());
clearBtn.addEventListener('click', () => clearDownloaded());

async function handleFetch(): Promise<void> {
  const url = urlInput.value.trim();
  if (!url) return;

  setError('');
  setLoading(true);
  previewSection.innerHTML = '';

  try {
    const info = await fetchVideoInfo(url);
    if (info.type === 'video') renderVideoPreview(info);
    else renderPlaylistPreview(info);
  } catch (e: unknown) {
    setError(e instanceof Error ? e.message : 'Something went wrong');
  } finally {
    setLoading(false);
  }
}

// ── Save options modal ────────────────────────────────────────
interface SaveOptions { folder: string; filename: string; subtitles: boolean; }

function showSaveModal(defaultTitle: string, showFilename: boolean): Promise<SaveOptions | null> {
  return new Promise((resolve) => {
    const modal           = document.getElementById('save-modal')        as HTMLElement;
    const folderDisplay   = document.getElementById('folder-display')    as HTMLInputElement;
    const browseBtn       = document.getElementById('folder-browse-btn') as HTMLButtonElement;
    const filenameField   = document.getElementById('filename-field')    as HTMLElement;
    const filenameInput   = document.getElementById('filename-input')    as HTMLInputElement;
    const subtitleToggle  = document.getElementById('subtitle-toggle')   as HTMLInputElement;
    const confirmBtn      = document.getElementById('save-confirm-btn')  as HTMLButtonElement;
    const cancelBtn       = document.getElementById('save-cancel-btn')   as HTMLButtonElement;

    let selectedFolder = 'downloads';
    folderDisplay.value = selectedFolder;
    filenameInput.value = defaultTitle;
    subtitleToggle.checked = false;
    filenameField.style.display = showFilename ? '' : 'none';
    modal.style.display = 'flex';

    browseBtn.onclick = async () => {
      browseBtn.disabled = true;
      browseBtn.textContent = 'Opening…';
      try {
        const res = await fetch('/api/pick-folder', { method: 'POST' });
        const data = await res.json();
        if (!data.cancelled && data.folder) {
          selectedFolder = data.folder;
          folderDisplay.value = selectedFolder;
        }
      } catch { /* ignore */ } finally {
        browseBtn.disabled = false;
        browseBtn.textContent = 'Browse\u2026';
      }
    };

    const close = (result: SaveOptions | null) => {
      modal.style.display = 'none';
      browseBtn.onclick  = null;
      confirmBtn.onclick = null;
      cancelBtn.onclick  = null;
      resolve(result);
    };

    confirmBtn.onclick = () => close({
      folder: selectedFolder,
      filename: filenameInput.value.trim() || defaultTitle,
      subtitles: subtitleToggle.checked,
    });
    cancelBtn.onclick = () => close(null);
  });
}

// ── Video preview ─────────────────────────────────────────────
function renderVideoPreview(info: VideoInfo): void {
  previewSection.innerHTML = `
    <div class="preview-card">
      <img class="preview-thumb" src="${info.thumbnail}" alt="Thumbnail">
      <div class="preview-meta">
        <h2 class="preview-title">${escapeHtml(info.title)}</h2>
        <p class="preview-channel">${escapeHtml(info.channel)} &middot; ${formatDuration(info.duration)}</p>
        <select id="resolution-picker" class="resolution-picker">
          ${info.formats.map(f => `<option value="${f.format_id}">${f.label} (.${f.ext})</option>`).join('')}
        </select>
        <button id="add-queue-btn" class="btn-primary">Add to Queue</button>
      </div>
    </div>`;

  document.getElementById('add-queue-btn')!.addEventListener('click', async () => {
    const formatId = (document.getElementById('resolution-picker') as HTMLSelectElement).value;
    const saveOpts = await showSaveModal(info.title, true);
    if (saveOpts === null) return;

    try {
      await addToQueue([{ url: info.webpage_url, format_id: formatId, title: info.title, thumbnail: info.thumbnail, output_dir: saveOpts.folder, custom_filename: saveOpts.filename, download_subtitles: saveOpts.subtitles }]);
      previewSection.innerHTML = '';
      urlInput.value = '';
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add to queue');
    }
  });
}

// ── Playlist preview ──────────────────────────────────────────
function renderPlaylistPreview(info: PlaylistInfo): void {
  const entryRows = info.entries.map((entry, i) => `
    <div class="playlist-entry">
      <input type="checkbox" class="playlist-check" data-index="${i}" checked>
      <img class="playlist-thumb" src="${entry.thumbnail || ''}" alt="">
      <span class="playlist-entry-title">${escapeHtml(entry.title)}</span>
    </div>`).join('');

  previewSection.innerHTML = `
    <div class="playlist-card">
      <div class="playlist-header">
        <div>
          <h2 class="preview-title">${escapeHtml(info.title)}</h2>
          <p class="preview-channel">${escapeHtml(info.channel)} &middot; ${info.count} videos</p>
        </div>
        <label class="select-all-label">
          <input type="checkbox" id="select-all" checked> Select all
        </label>
      </div>
      <div class="playlist-entries">${entryRows}</div>
      <div class="playlist-footer">
        <select id="playlist-resolution" class="resolution-picker">
          <option value="bestvideo+bestaudio/best">Best quality</option>
          <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
          <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
          <option value="bestvideo[height<=480]+bestaudio/best">480p</option>
          <option value="bestaudio/best">Audio only</option>
        </select>
        <button id="add-playlist-btn" class="btn-primary">Add Selected to Queue</button>
      </div>
    </div>`;

  document.getElementById('select-all')!.addEventListener('change', (e) => {
    const checked = (e.target as HTMLInputElement).checked;
    document.querySelectorAll<HTMLInputElement>('.playlist-check').forEach(cb => { cb.checked = checked; });
  });

  document.getElementById('add-playlist-btn')!.addEventListener('click', async () => {
    const formatId    = (document.getElementById('playlist-resolution') as HTMLSelectElement).value;
    const checkedBoxes = document.querySelectorAll<HTMLInputElement>('.playlist-check:checked');
    const selected = Array.from(checkedBoxes).map(cb => {
      const entry = info.entries[parseInt(cb.dataset.index!)];
      return { url: entry.webpage_url, format_id: formatId, title: entry.title, thumbnail: entry.thumbnail || '' };
    });

    if (selected.length === 0) { setError('No videos selected.'); return; }

    const saveOpts = await showSaveModal('', false);
    if (saveOpts === null) return;

    try {
      await addToQueue(selected.map(s => ({ ...s, output_dir: saveOpts.folder, download_subtitles: saveOpts.subtitles })));
      previewSection.innerHTML = '';
      urlInput.value = '';
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add to queue');
    }
  });
}

// ── Helpers ───────────────────────────────────────────────────
function setLoading(on: boolean): void {
  fetchBtn.disabled = on;
  fetchBtn.textContent = on ? 'Fetching...' : 'Fetch';
  if (on) previewSection.innerHTML = '<div class="loading-spinner"></div>';
}

function setError(msg: string): void {
  errorText.textContent = msg;
  errorBanner.style.display = msg ? 'flex' : 'none';
}

function escapeHtml(str: string): string {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function formatDuration(secs: number): string {
  if (!secs) return '';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}
