import type { FetchResult, AddToQueuePayload, ConvertFile, AddConversionPayload } from './types';

export async function fetchVideoInfo(url: string): Promise<FetchResult> {
  const res = await fetch('/api/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to fetch video info');
  return data as FetchResult;
}

export async function openFolder(path: string): Promise<void> {
  const res = await fetch('/api/open-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Failed to open folder');
  }
}

export async function addToQueue(items: AddToQueuePayload[]): Promise<{ added: string[] }> {
  const res = await fetch('/api/queue', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to add to queue');
  return data as { added: string[] };
}

export async function pickFiles(onlyKind?: 'image'): Promise<{ files: ConvertFile[]; skipped: number }> {
  const res = await fetch('/api/pick-files', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ only_kind: onlyKind ?? null }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to open file picker');
  return data;
}

export async function pickFolder(): Promise<string | null> {
  const res = await fetch('/api/pick-folder', { method: 'POST' });
  const data = await res.json();
  return data.cancelled ? null : data.folder;
}

export async function addConversions(items: AddConversionPayload[]): Promise<{ added: string[] }> {
  const res = await fetch('/api/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to start conversion');
  return data as { added: string[] };
}
