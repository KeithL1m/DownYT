import type { Socket } from 'socket.io-client';
import { pickFiles, pickFolder, pickSave, addConversions, openFolder } from './api';
import type { ConvertFile, ConvertJob, ConvertOperation } from './types';

// The Convert and Remove Background tabs share one implementation; each tab is a
// "tool view" configured below and identified by the id prefix of its DOM elements.
interface ToolConfig {
  prefix: string;
  operation: ConvertOperation;
  onlyKind?: 'image';
  // true: after choosing files, go straight to a native Save As dialog (no options card)
  saveDialog?: boolean;
  // Options card (used when saveDialog is false)
  pickFormat?: boolean;     // show a per-file output-format picker
  selectionHint?: string;
  emptyActive: string;
  emptyDone: string;
  startLabel?: string;
  arrowLabel: (job: ConvertJob) => string;
}

const KIND_LABEL: Record<string, string> = { image: 'IMG', audio: 'AUD', video: 'VID' };

const CONFIGS: ToolConfig[] = [
  {
    prefix: 'convert',
    operation: 'convert',
    pickFormat: true,
    selectionHint: 'Choose an output format for each file',
    emptyActive: 'No active conversions — choose some files above to get started.',
    emptyDone: 'Converted files will appear here.',
    startLabel: 'Convert',
    arrowLabel: (job) => `${job.title} → .${job.target_format}`,
  },
  {
    prefix: 'bg',
    operation: 'remove_bg',
    onlyKind: 'image',
    saveDialog: true,
    emptyActive: 'No active jobs — choose some images above to get started.',
    emptyDone: 'Images with the background removed will appear here.',
    arrowLabel: (job) => `${job.title} → background removed`,
  },
];

export function initConvert(socket: Socket, onError: (msg: string) => void): void {
  const views = new Map<ConvertOperation, ToolView>();
  for (const cfg of CONFIGS) views.set(cfg.operation, createToolView(cfg, onError));

  const dispatch = (job: ConvertJob) => views.get(job.operation ?? 'convert')?.updateJob(job);
  socket.on('convert_update', dispatch);
  fetch('/api/convert')
    .then(r => r.json())
    .then((jobs: ConvertJob[]) => jobs.forEach(dispatch))
    .catch(() => {});
}

interface ToolView {
  updateJob(job: ConvertJob): void;
}

function createToolView(cfg: ToolConfig, showError: (msg: string) => void): ToolView {
  const $ = (suffix: string) => document.getElementById(`${cfg.prefix}-${suffix}`)!;
  const chooseBtn   = $('choose-btn')  as HTMLButtonElement;
  const selectionEl = $('selection');
  const activeEl    = $('active');
  const doneEl      = $('done');

  const activeJobs = new Map<string, ConvertJob>();
  const doneJobs = new Map<string, ConvertJob>();
  let selected: ConvertFile[] = [];
  let outputDir: string | null = null; // null = same folder as each original

  chooseBtn.addEventListener('click', handleChoose);
  $('clear-active').addEventListener('click', () => { activeJobs.clear(); renderActive(); });
  $('clear-done').addEventListener('click', () => { doneJobs.clear(); renderDone(); });
  renderActive();
  renderDone();

  async function handleChoose(): Promise<void> {
    chooseBtn.disabled = true;
    chooseBtn.textContent = 'Opening…';
    try {
      const { files, skipped } = await pickFiles(cfg.onlyKind);
      if (skipped > 0) showError(`${skipped} file${skipped > 1 ? 's' : ''} skipped: unsupported type.`);
      if (files.length > 0) {
        selected = files;
        if (cfg.saveDialog) await startWithSaveDialog();
        else renderSelection();
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
        ${cfg.pickFormat ? `
          <span class="convert-arrow">→</span>
          <select class="resolution-picker convert-format" data-index="${i}">
            ${f.formats.map(fmt => `<option value="${fmt}" ${fmt === defaultFormat(f) ? 'selected' : ''}>.${fmt}</option>`).join('')}
          </select>` : ''}
        <button class="convert-remove" data-index="${i}" title="Remove">&times;</button>
      </div>`).join('');

    selectionEl.innerHTML = `
      <div class="playlist-card">
        <div class="playlist-header">
          <div>
            <h2 class="preview-title">${selected.length} file${selected.length > 1 ? 's' : ''} selected</h2>
            <p class="preview-channel">${cfg.selectionHint ?? ''}</p>
          </div>
        </div>
        <div class="playlist-entries">${rows}</div>
        <div class="playlist-footer convert-footer">
          <div class="convert-folder">
            <span class="hint">Save to</span>
            <input id="${cfg.prefix}-folder-display" type="text" class="folder-input folder-display" readonly value="${escapeHtml(outputDir ?? 'Same folder as original')}">
            <button id="${cfg.prefix}-folder-btn" class="btn-secondary">Browse…</button>
            ${outputDir ? `<button id="${cfg.prefix}-folder-reset" class="btn-ghost">Reset</button>` : ''}
          </div>
          <button id="${cfg.prefix}-start-btn" class="btn-primary">${cfg.startLabel ?? 'Start'}</button>
        </div>
      </div>`;

    selectionEl.querySelectorAll<HTMLButtonElement>('.convert-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        selected.splice(parseInt(btn.dataset.index!), 1);
        renderSelection();
      });
    });

    $('folder-btn').addEventListener('click', async () => {
      const folder = await pickFolder().catch(() => null);
      if (folder) {
        outputDir = folder;
        renderSelection();
      }
    });
    document.getElementById(`${cfg.prefix}-folder-reset`)?.addEventListener('click', () => {
      outputDir = null;
      renderSelection();
    });
    $('start-btn').addEventListener('click', startJobs);
  }

  const dirOf = (p: string) => p.substring(0, p.lastIndexOf('\\'));
  const stemOf = (name: string) => name.replace(/\.[^.]+$/, '');

  // Choose files -> native dialog straight away (same flow as downloading a video):
  // one image gets a Save As dialog to pick the folder and name, several get a folder picker.
  // Both open in the original's folder, so "save next to it" is one click.
  async function startWithSaveDialog(): Promise<void> {
    const files = selected;
    selected = [];
    try {
      let where: { output_dir: string; output_name?: string };
      if (files.length === 1) {
        const choice = await pickSave(`${stemOf(files[0].name)}_nobg`, {
          initialDir: dirOf(files[0].path),
          extension: 'png',
          title: 'Save image without background as',
        });
        if (choice.cancelled || !choice.folder) return;
        where = { output_dir: choice.folder, output_name: choice.filename ?? undefined };
      } else {
        const folder = await pickFolder({
          initialDir: dirOf(files[0].path),
          title: `Choose a folder for the ${files.length} images`,
        });
        if (!folder) return;
        where = { output_dir: folder };
      }
      await addConversions(files.map(f => ({
        source: f.path,
        operation: cfg.operation,
        target_format: 'png',
        ...where,
      })));
    } catch (e: unknown) {
      showError(e instanceof Error ? e.message : 'Failed to start');
    }
  }

  async function startJobs(): Promise<void> {
    const formats = selectionEl.querySelectorAll<HTMLSelectElement>('.convert-format');
    const items = selected.map((f, i) => ({
      source: f.path,
      operation: cfg.operation,
      target_format: cfg.pickFormat ? formats[i].value : 'png',
      ...(outputDir ? { output_dir: outputDir } : {}),
    }));
    try {
      await addConversions(items);
      selected = [];
      renderSelection();
    } catch (e: unknown) {
      showError(e instanceof Error ? e.message : 'Failed to start');
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
      activeEl.innerHTML = `<div class="queue-empty"><p>${cfg.emptyActive}</p></div>`;
      return;
    }
    activeEl.innerHTML = '';
    for (const job of activeJobs.values()) activeEl.appendChild(createCard(job));
  }

  function renderDone(): void {
    if (doneJobs.size === 0) {
      doneEl.innerHTML = `<div class="queue-empty"><p>${cfg.emptyDone}</p></div>`;
      return;
    }
    doneEl.innerHTML = '';
    for (const job of doneJobs.values()) doneEl.appendChild(createCard(job));
  }

  function createCard(job: ConvertJob): HTMLElement {
    const card = document.createElement('div');
    card.className = `queue-card status-${job.status}`;
    card.dataset.id = job.id;

    const label: Record<string, string> = { queued: 'Queued', converting: 'Working', completed: 'Done', error: 'Failed' };
    const detail = job.status === 'completed' && job.filename
      ? `<span class="queue-filepath">${escapeHtml(job.filename)}</span>`
      : job.error ? `<span class="queue-error-msg">${escapeHtml(job.error)}</span>` : '';

    const retry = job.status === 'error' ? `<button class="btn-retry" title="Retry">Retry</button>` : '';
    const open = job.status === 'completed' && job.filename ? `
      <button class="btn-open-folder" title="Open folder">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        Open Folder
      </button>` : '';

    // Image jobs show a preview (the result once done); the type badge is the fallback
    const icon = `<span class="file-icon kind-${job.kind}">${KIND_LABEL[job.kind] ?? '?'}</span>`;
    const preview = job.kind === 'image'
      ? `<img class="file-preview" alt="" src="/api/convert/${job.id}/file?which=${job.status === 'completed' ? 'output' : 'source'}">`
      : '';

    card.innerHTML = `
      ${preview || icon}
      <div class="queue-info">
        <span class="queue-title">${escapeHtml(cfg.arrowLabel(job))}</span>
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

    // Browsers can't render every image format (tiff, ico...): fall back to the badge
    card.querySelector<HTMLImageElement>('.file-preview')?.addEventListener('error', (e) => {
      (e.target as HTMLElement).outerHTML = icon;
    });
    card.querySelector('.btn-retry')?.addEventListener('click', async () => {
      activeJobs.delete(job.id);
      renderActive();
      try {
        await addConversions([{
          source: job.source,
          operation: job.operation,
          target_format: job.target_format,
          ...(job.output_dir ? { output_dir: job.output_dir } : {}),
          ...(job.output_name ? { output_name: job.output_name } : {}),
        }]);
      } catch (e: unknown) {
        showError(e instanceof Error ? e.message : 'Failed to retry');
      }
    });
    card.querySelector('.btn-open-folder')?.addEventListener('click', () => {
      openFolder(job.filename!).catch(() => {});
    });

    return card;
  }

  return { updateJob };
}

function escapeHtml(str: string): string {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
