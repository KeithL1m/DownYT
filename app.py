import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from downloader import fetch_info
from queue_manager import QueueManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'downyt-secret-key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

queue_manager = QueueManager(socketio)

os.makedirs('downloads', exist_ok=True)


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
