import os
import uuid
import threading
from downloader import download_video, cleanup_partial_files
from converter import convert_file, detect_kind


class QueueManager:
    def __init__(self, socketio):
        self.socketio = socketio
        self.jobs: dict = {}
        self.lock = threading.Lock()
        self._semaphore = threading.Semaphore(2)

    def add(self, item: dict) -> str:
        job_id = str(uuid.uuid4())
        output_dir = item.get('output_dir', 'downloads')
        os.makedirs(output_dir, exist_ok=True)
        job = {
            'id': job_id,
            'url': item['url'],
            'format_id': item['format_id'],
            'title': item['title'],
            'thumbnail': item.get('thumbnail', ''),
            'output_dir': output_dir,
            'custom_filename': item.get('custom_filename') or None,
            'download_subtitles': bool(item.get('download_subtitles', False)),
            'status': 'queued',
            'progress': 0,
            'speed': None,
            'eta': None,
            'filename': None,
            'error': None,
        }
        with self.lock:
            self.jobs[job_id] = job

        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()
        return job_id

    def get_all(self) -> list:
        with self.lock:
            return list(self.jobs.values())

    def _run(self, job_id: str):
        self._semaphore.acquire()
        job = self.jobs[job_id]
        try:
            self._update(job_id, status='downloading')

            def progress_hook(d):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    progress = int((downloaded / total) * 100) if total else 0
                    self._update(job_id, progress=progress,
                                 speed=d.get('speed'), eta=d.get('eta'))
                elif d['status'] == 'finished':
                    self._update(job_id, progress=100)

            filename = download_video(
                url=job['url'],
                format_id=job['format_id'],
                output_dir=job['output_dir'],
                progress_hook=progress_hook,
                custom_filename=job.get('custom_filename'),
                download_subtitles=job.get('download_subtitles', False),
            )
            self._update(job_id, status='completed', filename=filename, progress=100)

        except Exception as e:
            self._update(job_id, status='error', error=str(e))
            cleanup_partial_files(
                output_dir=job['output_dir'],
                title=job['title'],
                custom_filename=job.get('custom_filename'),
                download_subtitles=job.get('download_subtitles', False),
            )

        finally:
            self._semaphore.release()

    def _update(self, job_id: str, **kwargs):
        job_data = None
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(kwargs)
                job_data = dict(self.jobs[job_id])
        if job_data is not None:
            self.socketio.emit('queue_update', job_data)


class ConvertManager:
    """Runs file conversions on background threads, mirroring QueueManager."""

    def __init__(self, socketio):
        self.socketio = socketio
        self.jobs: dict = {}
        self.lock = threading.Lock()
        self._semaphore = threading.Semaphore(2)

    def add(self, item: dict) -> str:
        job_id = str(uuid.uuid4())
        source = item['source']
        job = {
            'id': job_id,
            'source': source,
            'title': os.path.basename(source),
            'kind': detect_kind(source),
            'target_format': item['target_format'],
            'output_dir': item.get('output_dir') or None,
            'status': 'queued',
            'progress': 0,
            'filename': None,
            'error': None,
        }
        with self.lock:
            self.jobs[job_id] = job

        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()
        return job_id

    def get_all(self) -> list:
        with self.lock:
            return list(self.jobs.values())

    def _run(self, job_id: str):
        self._semaphore.acquire()
        job = self.jobs[job_id]
        try:
            self._update(job_id, status='converting')
            output = convert_file(
                source=job['source'],
                target_format=job['target_format'],
                output_dir=job['output_dir'],
                progress_cb=lambda pct: self._update(job_id, progress=pct),
            )
            self._update(job_id, status='completed', filename=output, progress=100)
        except Exception as e:
            self._update(job_id, status='error', error=str(e))
        finally:
            self._semaphore.release()

    def _update(self, job_id: str, **kwargs):
        job_data = None
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(kwargs)
                job_data = dict(self.jobs[job_id])
        if job_data is not None:
            self.socketio.emit('convert_update', job_data)
