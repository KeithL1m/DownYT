import os
import re
import subprocess
from typing import Callable, Optional

from PIL import Image

from downloader import _resolve_ffmpeg_location

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff', '.ico'}
AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.opus', '.wma'}
VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.flv', '.wmv', '.m4v'}

AUDIO_FORMATS = ['mp3', 'wav', 'flac', 'm4a', 'ogg', 'opus']

# Valid output formats per input kind. Video inputs can also extract audio.
OUTPUT_FORMATS = {
    'image': ['png', 'jpg', 'webp', 'bmp', 'gif', 'tiff', 'ico'],
    'audio': AUDIO_FORMATS,
    'video': ['mp4', 'mkv', 'webm', 'mov', 'gif'] + AUDIO_FORMATS,
}

# ffmpeg codec arguments per output format
_FFMPEG_ARGS = {
    'mp3':  ['-vn', '-c:a', 'libmp3lame', '-q:a', '2'],
    'wav':  ['-vn', '-c:a', 'pcm_s16le'],
    'flac': ['-vn', '-c:a', 'flac'],
    'm4a':  ['-vn', '-c:a', 'aac', '-b:a', '192k'],
    'ogg':  ['-vn', '-c:a', 'libvorbis', '-q:a', '5'],
    'opus': ['-vn', '-c:a', 'libopus', '-b:a', '128k'],
    'mp4':  ['-c:v', 'libx264', '-crf', '23', '-preset', 'medium', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart'],
    'mkv':  ['-c:v', 'libx264', '-crf', '23', '-preset', 'medium', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '160k'],
    'mov':  ['-c:v', 'libx264', '-crf', '23', '-preset', 'medium', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '160k'],
    'webm': ['-c:v', 'libvpx-vp9', '-crf', '32', '-b:v', '0', '-c:a', 'libopus', '-b:a', '128k'],
    'gif':  ['-an', '-vf', 'fps=12,scale=480:-1:flags=lanczos'],
}

_PIL_FORMATS = {
    'png': 'PNG', 'jpg': 'JPEG', 'webp': 'WEBP', 'bmp': 'BMP',
    'gif': 'GIF', 'tiff': 'TIFF', 'ico': 'ICO',
}

# Hide the console window ffmpeg would otherwise flash open from the windowed app
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def detect_kind(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in AUDIO_EXTS:
        return 'audio'
    if ext in VIDEO_EXTS:
        return 'video'
    return None


def inspect_file(path: str) -> Optional[dict]:
    kind = detect_kind(path)
    if kind is None:
        return None
    return {
        'path': path,
        'name': os.path.basename(path),
        'kind': kind,
        'formats': OUTPUT_FORMATS[kind],
    }


def unique_path(directory: str, stem: str, ext: str) -> str:
    """Return a path that doesn't exist yet, so a conversion never overwrites a file."""
    candidate = os.path.join(directory, f'{stem}.{ext}')
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f'{stem} ({n}).{ext}')
        n += 1
    return candidate


def convert_file(source: str, target_format: str, output_dir: Optional[str],
                 progress_cb: Callable[[int], None]) -> str:
    """Convert `source` to `target_format` and return the output path."""
    kind = detect_kind(source)
    if kind is None:
        raise ValueError('Unsupported file type')
    target_format = target_format.lower().lstrip('.')
    if target_format not in OUTPUT_FORMATS[kind]:
        raise ValueError(f'Cannot convert {kind} files to .{target_format}')
    if not os.path.isfile(source):
        raise FileNotFoundError(f'File not found: {source}')

    out_dir = output_dir or os.path.dirname(os.path.abspath(source))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(source))[0]
    output = unique_path(out_dir, stem, target_format)

    try:
        if kind == 'image':
            _convert_image(source, target_format, output)
            progress_cb(100)
        else:
            _convert_ffmpeg(source, target_format, output, progress_cb)
    except BaseException:
        # Never leave a half-written output behind
        if os.path.exists(output):
            try:
                os.remove(output)
            except OSError:
                pass
        raise
    return output


def _convert_image(source: str, target_format: str, output: str) -> None:
    with Image.open(source) as img:
        img.load()
        if target_format == 'jpg' and img.mode in ('RGBA', 'LA', 'P'):
            # JPEG has no alpha channel: flatten onto white
            rgba = img.convert('RGBA')
            flat = Image.new('RGB', rgba.size, (255, 255, 255))
            flat.paste(rgba, mask=rgba.split()[3])
            img = flat
        elif target_format in ('jpg', 'bmp') and img.mode != 'RGB':
            img = img.convert('RGB')
        elif target_format == 'ico':
            img = img.convert('RGBA')
            img.thumbnail((256, 256))
        img.save(output, format=_PIL_FORMATS[target_format])


def _ffmpeg_exe() -> str:
    location = _resolve_ffmpeg_location()
    if location:
        return os.path.join(location, 'ffmpeg.exe')
    return 'ffmpeg'


def _probe_duration(ffmpeg: str, source: str) -> float:
    """Read the duration (seconds) ffmpeg reports for `source`; 0 if unknown."""
    proc = subprocess.run(
        [ffmpeg, '-hide_banner', '-i', source],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=_NO_WINDOW, text=True, errors='replace',
    )
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', proc.stdout)
    if not m:
        return 0.0
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def _convert_ffmpeg(source: str, target_format: str, output: str,
                    progress_cb: Callable[[int], None]) -> None:
    ffmpeg = _ffmpeg_exe()
    duration = _probe_duration(ffmpeg, source)

    cmd = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-progress', 'pipe:1', '-nostats',
           '-i', source, *_FFMPEG_ARGS[target_format], output]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=_NO_WINDOW, text=True, errors='replace',
    )

    tail: list = []
    last = -1
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith('out_time_us=') or line.startswith('out_time_ms='):
                # both keys report microseconds
                try:
                    micros = int(line.split('=', 1)[1])
                except ValueError:
                    continue
                if duration > 0 and micros > 0:
                    pct = min(99, int(micros / 1_000_000 / duration * 100))
                    if pct != last:
                        last = pct
                        progress_cb(pct)
            elif '=' not in line and line:
                tail.append(line)
                tail = tail[-12:]
        code = proc.wait()
    except BaseException:
        proc.kill()
        raise

    if code != 0:
        detail = tail[-1] if tail else f'ffmpeg exited with code {code}'
        raise RuntimeError(detail)
    progress_cb(100)
