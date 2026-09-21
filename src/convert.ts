import type { Socket } from 'socket.io-client';
import { pickFiles, pickFolder, addConversions, openFolder } from './api';
import type { ConvertFile, ConvertJob } from './types';

const activeJobs = new Map<string, ConvertJob>();
const doneJobs = new Map<string, ConvertJob>();

let selected: ConvertFile[] = [];
let outputDir: string | null = null; // null = same folder as each original

let chooseBtn: HTMLButtonElement;
let selectionEl: HTMLElement;
let activeEl: HTMLElement;
let doneEl: HTMLElement;
let showError: (msg: string) => void;

const KIND_LABEL: Record<string, string> = { image: 'IMG', audio: 'AUD', video: 'VID' };

export function initConvert(socket: Socket, onError: (msg: string) => void): void {
  showError = onError;
  chooseBtn   = document.getElementById('convert-choose-btn')  as HTMLButtonElement;
  selectionEl = document.getElementById('convert-selection')   as HTMLElement;
  activeEl    = document.getElementById('convert-active')      as HTMLElement;
  doneEl      = document.getElementById('convert-done')        as HTMLElement;

  chooseBtn.addEventListener('click', handleChoose);
  document.getElementById('convert-clear-active')!.addEventListener('click', () => { activeJobs.clear(); renderActive(); });
  document.getElementById('convert-clear-done')!.addEventListener('click', () => { doneJobs.clear(); renderDone(); });

  socket.on('convert_update', (job: ConvertJob) => updateJob(job));
  fetch('/api/convert')
    .then(r => r.json())
    .then((jobs: ConvertJob[]) => jobs.forEach(updateJob))
    .catch(() => {});

  renderActive();
  renderDone();
}

async function handleChoose(): Promise<void> {
  chooseBtn.disabled = true;
  chooseBtn.textContent = 'Opening…';
  try {
    const { files, skipped } = await pickFiles();
    if (skipped > 0) showError(`${skipped} file${skipped > 1 ? 's' : ''} skipped: unsupported type.`);
    if (files.length > 0) {
      selected = files;
      renderSelection();
    }
  } catch (e: unknown) {
    showError(e instanceof Error ? e.message : 'Could not open the file picker');
  } finally {
    chooseBtn.disabled = false;
    chooseBtn.textContent = 'Choose files…';
  }
}

function defaultFormat(file: ConvertFile): string {
  const ext = file.name.split('.').pop()!.toLowerCase();
  return file.formats.find(f => f !== ext && !(f === 'jpg' && ext === 'jpeg')) ?? file.formats[0];
}

function renderSelection(): void {
  if (selected.length === 0) {
    selectionEl.innerHTML = '';
    return;
  }

  const rows = selected.map((f, i) => `
    <div class="convert-row">
      <span class="file-icon kind-${f.kind}">${KIND_LABEL[f.kind]}</span>
      <span class="convert-row-name" title="${escapeHtml(f.path)}">${escapeHtml(f.name)}</span>
      <span class="convert-arrow">→</span>
      <select class="resolution-picker convert-format" data-index="${i}">
        ${f.formats.map(fmt => `<option value="${fmt}" ${fmt === defaultFormat(f) ? 'selected' : ''}>.${fmt}</option>`).join('')}
      </select>
      <button class="convert-remove" data-index="${i}" title="Remove">&times;</button>
    </div>`).join('');

  selectionEl.innerHTML = `
    <div class="playlist-card">
      <div class="playlist-header">
        <div>
          <h2 class="preview-title">${selected.length} file${selected.length > 1 ? 's' : ''} selected</h2>
          <p class="preview-channel">Choose an output format for each file</p>
        </div>
      </div>
      <div class="playlist-entries">${rows}</div>
      <div class="playlist-footer convert-footer">
        <div class="convert-folder">
          <span class="modal-hint">Save to</span>
          <input id="convert-folder-display" type="text" class="folder-input folder-display" readonly value="${escapeHtml(outputDir ?? 'Same folder as original')}">
          <button id="convert-folder-btn" class="btn-secondary">Browse…</button>
          ${outputDir ? '<button id="convert-folder-reset" class="btn-ghost">Reset</button>' : ''}
        </div>
        <button id="convert-start-btn" class="btn-primary">Convert</button>
      </div>
    </div>`;

  selectionEl.querySelectorAll<HTMLButtonElement>('.convert-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      selected.splice(parseInt(btn.dataset.index!), 1);
      renderSelection();
    });
  });

  document.getElementById('convert-folder-btn')!.addEventListener('click', async () => {
    const folder = await pickFolder().catch(() => null);
    if (folder) {
      outputDir = folder;
      renderSelection();
    }
  });
  document.getElementById('convert-folder-reset')?.addEventListener('click', () => {
    outputDir = null;
    renderSelection();
  });

  document.getElementById('convert-start-btn')!.addEventListener('click', startConversion);
}

async function startConversion(): Promise<void> {
  const formats = selectionEl.querySelectorAll<HTMLSelectElement>('.convert-format');
  const items = selected.map((f, i) => ({
    source: f.path,
    target_format: formats[i].value,
    ...(outputDir ? { output_dir: outputDir } : {}),
  }));
  try {
    await addConversions(items);
    selected = [];
    renderSelection();
  } catch (e: unknown) {
    showError(e instanceof Error ? e.message : 'Failed to start conversion');
  }
}

function updateJob(job: ConvertJob): void {
  if (job.status === 'completed') {
    activeJobs.delete(job.id);
    doneJobs.set(job.id, job);
    renderActive();
    renderDone();
  } else {
    activeJobs.set(job.id, job);
    renderActive();
  }
}

function renderActive(): void {
  if (activeJobs.size === 0) {
    activeEl.innerHTML = `<div class="queue-empty"><p>No active conversions — choose some files above to get started.</p></div>`;
    return;
  }
  activeEl.innerHTML = '';
  for (const job of activeJobs.values()) activeEl.appendChild(createCard(job));
}

function renderDone(): void {
  if (doneJobs.size === 0) {
    doneEl.innerHTML = `<div class="queue-empty"><p>Converted files will appear here.</p></div>`;
    return;
  }
  doneEl.innerHTML = '';
  for (const job of doneJobs.values()) doneEl.appendChild(createCard(job));
}

function createCard(job: ConvertJob): HTMLElement {
  const card = document.createElement('div');
  card.className = `queue-card status-${job.status}`;
  card.dataset.id = job.id;

  const label: Record<string, string> = { queued: 'Queued', converting: 'Converting', completed: 'Done', error: 'Failed' };
  const detail = job.status === 'completed' && job.filename
    ? `<span class="queue-filepath">${escapeHtml(job.filename)}</span>`
    : job.error ? `<span class="queue-error-msg">${escapeHtml(job.error)}</span>` : '';

  const retry = job.status === 'error' ? `<button class="btn-retry" title="Retry conversion">Retry</button>` : '';
  const open = job.status === 'completed' && job.filename ? `
    <button class="btn-open-folder" title="Open folder">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      Open Folder
    </button>` : '';

  card.innerHTML = `
    <span class="file-icon kind-${job.kind}">${KIND_LABEL[job.kind] ?? '?'}</span>
    <div class="queue-info">
      <span class="queue-title">${escapeHtml(job.title)} → .${escapeHtml(job.target_format)}</span>
      <div class="queue-meta">
        <span class="queue-status-badge badge-${job.status}">${label[job.status]}</span>
        ${job.status === 'converting' ? `<span class="queue-eta">${job.progress}%</span>` : ''}
        ${detail}
      </div>
      <div class="queue-progress-bar">
        <div class="queue-progress-fill" style="width: ${job.progress}%"></div>
      </div>
    </div>
    ${retry}${open}`;

  card.querySelector('.btn-retry')?.addEventListener('click', async () => {
    activeJobs.delete(job.id);
    renderActive();
    try {
      await addConversions([{ source: job.source, target_format: job.target_format, ...(job.output_dir ? { output_dir: job.output_dir } : {}) }]);
    } catch (e: unknown) {
      showError(e instanceof Error ? e.message : 'Failed to retry');
    }
  });
  card.querySelector('.btn-open-folder')?.addEventListener('click', () => {
    openFolder(job.filename!).catch(() => {});
  });

  return card;
}

function escapeHtml(str: string): string {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
