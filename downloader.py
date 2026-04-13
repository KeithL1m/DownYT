import os
import yt_dlp


def fetch_info(url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get('_type') == 'playlist':
        return _format_playlist(info)
    return _format_video(info)


def _format_video(info: dict) -> dict:
    formats = []
    seen: set = set()

    for f in info.get('formats', []):
        height = f.get('height')
        vcodec = f.get('vcodec', 'none')
        acodec = f.get('acodec', 'none')

        if vcodec == 'none' and acodec != 'none':
            key = 'audio'
            label = 'Audio only'
        elif height and vcodec != 'none':
            key = str(height)
            label = f'{height}p'
        else:
            continue

        if key not in seen:
            seen.add(key)
            is_video = vcodec != 'none'
            formats.append({
                'format_id': f"{f['format_id']}+bestaudio/best" if is_video else f['format_id'],
                'label': label,
                'height': height,
                'ext': f.get('ext', 'mp4'),
            })

    formats.sort(key=lambda x: (x['height'] or 0), reverse=True)

    return {
        'type': 'video',
        'id': info.get('id'),
        'title': info.get('title'),
        'channel': info.get('uploader'),
        'duration': info.get('duration'),
        'thumbnail': info.get('thumbnail'),
        'webpage_url': info.get('webpage_url'),
        'formats': formats,
    }


def _format_playlist(info: dict) -> dict:
    entries = []
    for entry in info.get('entries', []):
        if entry is None:
            continue
        entries.append({
            'id': entry.get('id'),
            'title': entry.get('title'),
            'thumbnail': entry.get('thumbnail'),
            'duration': entry.get('duration'),
            'webpage_url': entry.get('webpage_url')
                or f"https://www.youtube.com/watch?v={entry.get('id')}",
        })

    return {
        'type': 'playlist',
        'title': info.get('title'),
        'channel': info.get('uploader'),
        'count': len(entries),
        'entries': entries,
    }


def download_video(url: str, format_id: str, output_dir: str, progress_hook, custom_filename: str = None) -> str:
    if custom_filename:
        outtmpl = f'{output_dir}/{custom_filename}.%(ext)s'
    else:
        outtmpl = f'{output_dir}/%(title)s.%(ext)s'
    ydl_opts = {
        'format': format_id,
        'outtmpl': outtmpl,
        'merge_output_format': 'mp4',
        'ffmpeg_location': r'C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin',
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progress_hook],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        return base + '.mp4'
