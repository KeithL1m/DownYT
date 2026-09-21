import os
import sys
from flask import Flask, render_template, request, jsonify
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

DOWNLOADS_DIR = os.path.join(_APP_DIR, 'downloads')
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

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
            item['output_dir'] = os.path.join(_APP_DIR, d)
    added = [queue_manager.add(item) for item in items]
    return jsonify({'added': added})


@app.route('/api/queue', methods=['GET'])
def get_queue():
    return jsonify(queue_manager.get_all())


@app.route('/api/pick-folder', methods=['POST'])
def pick_folder():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    folder = filedialog.askdirectory(title='Choose download folder')
    root.destroy()
    if not folder:
        return jsonify({'cancelled': True, 'folder': None})
    return jsonify({'cancelled': False, 'folder': folder})


@app.route('/api/pick-files', methods=['POST'])
def pick_files():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

    def patterns(exts):
        return ' '.join(f'*{e}' for e in sorted(exts))

    paths = filedialog.askopenfilenames(
        title='Choose files to convert',
        filetypes=[
            ('Supported files', patterns(IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS)),
            ('Images', patterns(IMAGE_EXTS)),
            ('Audio', patterns(AUDIO_EXTS)),
            ('Video', patterns(VIDEO_EXTS)),
        ],
    )
    root.destroy()
    files = [inspect_file(os.path.normpath(p)) for p in paths]
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
        if not item.get('source') or not item.get('target_format'):
            return jsonify({'error': 'Each item needs a source file and target format'}), 400
    added = [convert_manager.add(item) for item in items]
    return jsonify({'added': added})


@app.route('/api/convert', methods=['GET'])
def get_conversions():
    return jsonify(convert_manager.get_all())


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
