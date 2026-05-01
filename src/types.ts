export interface Resolution {
  format_id: string;
  label: string;
  height: number | null;
  ext: string;
}

export interface VideoInfo {
  type: 'video';
  id: string;
  title: string;
  channel: string;
  duration: number;
  thumbnail: string;
  webpage_url: string;
  formats: Resolution[];
}

export interface PlaylistEntry {
  id: string;
  title: string;
  thumbnail: string;
  duration: number;
  webpage_url: string;
}

export interface PlaylistInfo {
  type: 'playlist';
  title: string;
  channel: string;
  count: number;
  entries: PlaylistEntry[];
}

export type FetchResult = VideoInfo | PlaylistInfo;

export type QueueStatus = 'queued' | 'downloading' | 'completed' | 'error';

export interface QueueItem {
  id: string;
  url: string;
  format_id: string;
  title: string;
  thumbnail: string;
  output_dir: string;
  custom_filename: string | null;
  download_subtitles: boolean;
  status: QueueStatus;
  progress: number;
  speed: number | null;
  eta: number | null;
  filename: string | null;
  error: string | null;
}

export interface AddToQueuePayload {
  url: string;
  format_id: string;
  title: string;
  thumbnail: string;
  output_dir: string;
  custom_filename?: string;
  download_subtitles?: boolean;
}
