import type { QueueItem } from './types';
import { openFolder } from './api';

const activeItems = new Map<string, QueueItem>();
const completedItems = new Map<string, QueueItem>();

let activeEl: HTMLElement;
let downloadedEl: HTMLElement;

export function initQueue(activeContainer: HTMLElement, downloadedContainer: HTMLElement): void {
  activeEl = activeContainer;
  downloadedEl = downloadedContainer;
  renderActive();
  renderDownloaded();
}

export function updateQueueItem(item: QueueItem): void {
  if (item.status === 'completed') {
    activeItems.delete(item.id);
    completedItems.set(item.id, item);
    renderActive();
    renderDownloaded();
  } else {
    activeItems.set(item.id, item);
    renderActive();
  }
}

export function clearActive(): void {
  activeItems.clear();
  renderActive();
}

export function clearDownloaded(): void {
  completedItems.clear();
  renderDownloaded();
}

function renderActive(): void {
  if (activeItems.size === 0) {
    activeEl.innerHTML = `
      <div class="queue-empty">
        <p>No active downloads — paste a YouTube link above to get started.</p>
      </div>`;
    return;
  }
  activeEl.innerHTML = '';
  for (const item of activeItems.values()) {
    activeEl.appendChild(createActiveCard(item));
  }
}

function renderDownloaded(): void {
  if (completedItems.size === 0) {
    downloadedEl.innerHTML = `<div class="queue-empty"><p>Completed downloads will appear here.</p></div>`;
    return;
  }
  downloadedEl.innerHTML = '';
  for (const item of completedItems.values()) {
    downloadedEl.appendChild(createDownloadedCard(item));
  }
}

function createActiveCard(item: QueueItem): HTMLElement {
  const card = document.createElement('div');
  card.className = `queue-card status-${item.status}`;
  card.dataset.id = item.id;

  const statusLabel: Record<string, string> = {
    queued: 'Queued',
    downloading: 'Downloading',
    error: 'Failed',
    completed: 'Done',
  };

  const metaExtras = [
    item.speed ? `<span class="queue-speed">${formatSpeed(item.speed)}</span>` : '',
    item.eta   ? `<span class="queue-eta">ETA ${formatEta(item.eta)}</span>` : '',
    item.error ? `<span class="queue-error-msg">${escapeHtml(item.error)}</span>` : '',
  ].filter(Boolean).join('');

  card.innerHTML = `
    <img class="queue-thumb" src="${item.thumbnail}" alt="">
    <div class="queue-info">
      <span class="queue-title">${escapeHtml(item.title)}</span>
      <div class="queue-meta">
        <span class="queue-status-badge badge-${item.status}">${statusLabel[item.status]}</span>
        ${metaExtras}
      </div>
      <div class="queue-progress-bar">
        <div class="queue-progress-fill" style="width: ${item.progress}%"></div>
      </div>
    </div>`;

  return card;
}

function createDownloadedCard(item: QueueItem): HTMLElement {
  const card = document.createElement('div');
  card.className = 'queue-card status-completed';
  card.dataset.id = item.id;

  card.innerHTML = `
    <img class="queue-thumb" src="${item.thumbnail}" alt="">
    <div class="queue-info">
      <span class="queue-title">${escapeHtml(item.title)}</span>
      <div class="queue-meta">
        <span class="queue-status-badge badge-completed">Done</span>
        ${item.filename ? `<span class="queue-filepath">${escapeHtml(item.filename)}</span>` : ''}
      </div>
      <div class="queue-progress-bar">
        <div class="queue-progress-fill" style="width: 100%"></div>
      </div>
    </div>
    ${item.filename ? `<button class="btn-open-folder" title="Open folder" data-path="${escapeHtml(item.filename)}">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      Open Folder
    </button>` : ''}`;

  const openBtn = card.querySelector<HTMLButtonElement>('.btn-open-folder');
  if (openBtn) {
    openBtn.addEventListener('click', async () => {
      try {
        await openFolder(openBtn.dataset.path!);
      } catch {
        // silently ignore — folder may have been moved
      }
    });
  }

  return card;
}

function escapeHtml(str: string): string {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec >= 1_000_000) return `${(bytesPerSec / 1_000_000).toFixed(1)} MB/s`;
  return `${(bytesPerSec / 1_000).toFixed(0)} KB/s`;
}

function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
