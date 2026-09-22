import json
import os
import re
import sys
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
from downloader import fetch_info
from queue_manager import QueueManager, ConvertManager
from converter import inspect_file, IMAGE_EXTS, AUDIO_EXTS, VIDEO_EXTS

# When frozen by PyInstaller, resources live in sys._MEIPASS;
# user-writable data (downloads) lives next to the .exe.
if getattr(sys, 'frozen', False):
    _RES_DIR = sys._MEIPASS
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _RES_DIR = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = _RES_DIR

def _pick_downloads_dir() -> str:
    """Default download folder: next to the app when that's writable (portable use),
    otherwise the user's Downloads folder, e.g. when installed under Program Files."""
    for candidate in (os.path.join(_APP_DIR, 'downloads'),
                      os.path.join(os.path.expanduser('~'), 'Downloads', 'DownYT')):
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, '.write_test')
            with open(probe, 'w'):
                pass
            os.remove(probe)
            return candidate
        except OSError:
            continue
    return os.path.join(_APP_DIR, 'downloads')  # nothing writable: jobs will report the error


DOWNLOADS_DIR = _pick_downloads_dir()

app = Flask(
    __name__,
    template_folder=os.path.join(_RES_DIR, 'templates'),
    static_folder=os.path.join(_RES_DIR, 'static'),
)
app.config['SECRET_KEY'] = 'downyt-secret-key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

queue_manager = QueueManager(socketio)
convert_manager = ConvertManager(socketio)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/fetch', methods=['POST'])
def fetch():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        info = fetch_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/queue', methods=['POST'])
def add_to_queue():
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'No items provided'}), 400
    for item in items:
        d = item.get('output_dir', 'downloads')
        if not os.path.isabs(d):
            item['output_dir'] = DOWNLOADS_DIR if d == 'downloads' else os.path.join(_APP_DIR, d)
    try:
        added = [queue_manager.add(item) for item in items]
    except OSError as e:
        # e.g. a folder the user can't write to (chosen in the Save As dialog)
        return jsonify({'error': f'Cannot use that folder: {e.strerror or e}'}), 400
    return jsonify({'added': added})


@app.route('/api/queue', methods=['GET'])
def get_queue():
    return jsonify(queue_manager.get_all())


# The last folder used in the Save As / folder-picker dialogs, so repeat downloads
# reopen where the last one ended. This is the one deliberate exception to "no
# persistent storage": just a single folder path, not download history or content.
_SETTINGS_DIR = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'DownYT')
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, 'settings.json')


def _load_last_dir() -> str:
    try:
        with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            folder = json.load(f).get('last_dir')
        if folder and os.path.isdir(folder):
            return folder
    except (OSError, ValueError):
        pass
    return DOWNLOADS_DIR


def _save_last_dir(folder: str) -> None:
    try:
        os.makedirs(_SETTINGS_DIR, exist_ok=True)
        with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_dir': folder}, f)
    except OSError:
        pass  # best-effort: an unwritable settings location just means no persistence


_last_dir = _load_last_dir()


def _remember_dir(folder: str) -> None:
    global _last_dir
    if folder and os.path.isdir(folder):
        _last_dir = folder
        _save_last_dir(folder)


def _start_dir(requested) -> str:
    """Where a dialog should open: the caller's folder if it exists, else the last one used."""
    return requested if requested and os.path.isdir(requested) else _last_dir


@app.route('/api/pick-folder', methods=['POST'])
def pick_folder():
    import tkinter as tk
    from tkinter import filedialog
    body = request.get_json(silent=True) or {}
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    folder = filedialog.askdirectory(title=body.get('title') or 'Choose download folder',
                                     initialdir=_start_dir(body.get('initial_dir')))
    root.destroy()
    if not folder:
        return jsonify({'cancelled': True, 'folder': None})
    _remember_dir(folder)
    return jsonify({'cancelled': False, 'folder': folder})


_FILENAME_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MEDIA_EXTS = {'.mp4', '.mkv', '.webm', '.m4a', '.mp3', '.opus', '.ogg', '.wav', '.flac'}


@app.route('/api/pick-save', methods=['POST'])
def pick_save():
    """Save As dialog: the user picks the folder and edits the file name in one step.

    Body: `default_name`, plus optional `initial_dir`, `title` and `extension`
    (without the dot; defaults to the video download case, mp4).
    """
    import tkinter as tk
    from tkinter import filedialog
    body = request.get_json(silent=True) or {}
    extension = (body.get('extension') or 'mp4').lower().lstrip('.')
    default_name = body.get('default_name') or 'video'
    # Windows rejects some characters in file names; yt-dlp would sanitise them anyway
    default_name = _FILENAME_BAD_CHARS.sub('_', default_name).strip(' .')[:150] or 'video'

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    path = filedialog.asksaveasfilename(
        title=body.get('title') or 'Save video as',
        initialdir=_start_dir(body.get('initial_dir')),
        initialfile=default_name,
        defaultextension=f'.{extension}',
        filetypes=[(extension.upper(), f'*.{extension}')],
        confirmoverwrite=False,
    )
    root.destroy()
    if not path:
        return jsonify({'cancelled': True, 'folder': None, 'filename': None})

    folder, name = os.path.split(os.path.normpath(path))
    stem, ext = os.path.splitext(name)
    # The caller appends the real extension itself; only strip one the dialog/user added
    if ext.lower() == f'.{extension}' or ext.lower() in _MEDIA_EXTS:
        name = stem
    _remember_dir(folder)
    return jsonify({'cancelled': False, 'folder': folder, 'filename': name})


@app.route('/api/pick-files', methods=['POST'])
def pick_files():
    import tkinter as tk
    from tkinter import filedialog
    only_kind = (request.get_json(silent=True) or {}).get('only_kind')
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

    def patterns(exts):
        return ' '.join(f'*{e}' for e in sorted(exts))

    if only_kind == 'image':
        title = 'Choose images'
        filetypes = [('Images', patterns(IMAGE_EXTS))]
    else:
        title = 'Choose files to convert'
        filetypes = [
            ('Supported files', patterns(IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS)),
            ('Images', patterns(IMAGE_EXTS)),
            ('Audio', patterns(AUDIO_EXTS)),
            ('Video', patterns(VIDEO_EXTS)),
        ]
    paths = filedialog.askopenfilenames(title=title, filetypes=filetypes)
    root.destroy()
    files = [inspect_file(os.path.normpath(p)) for p in paths]
    if only_kind:
        files = [f if f and f['kind'] == only_kind else None for f in files]
    return jsonify({
        'files': [f for f in files if f],
        'skipped': sum(1 for f in files if f is None),
    })


@app.route('/api/convert', methods=['POST'])
def add_conversions():
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'No files provided'}), 400
    for item in items:
        if item.get('operation') == 'remove_bg':
            item['target_format'] = 'png'
        if not item.get('source') or not item.get('target_format'):
            return jsonify({'error': 'Each item needs a source file and target format'}), 400
    added = [convert_manager.add(item) for item in items]
    return jsonify({'added': added})


@app.route('/api/convert', methods=['GET'])
def get_conversions():
    return jsonify(convert_manager.get_all())


@app.route('/api/convert/<job_id>/file')
def convert_job_file(job_id):
    # Serve only a job's own source/output image (for on-screen previews), never arbitrary paths
    job = next((j for j in convert_manager.get_all() if j['id'] == job_id), None)
    which = 'filename' if request.args.get('which') == 'output' else 'source'
    path = job and job.get(which)
    if not path or job['kind'] != 'image' or not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    return send_file(path)


@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    data = request.get_json()
    path = data.get('path', '')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.exists(folder):
        return jsonify({'error': 'Folder not found'}), 400
    os.startfile(folder)
    return jsonify({'ok': True})


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
