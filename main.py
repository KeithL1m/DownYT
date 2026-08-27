import sys
import os

# PyInstaller windowed builds (console=False) can leave sys.stdout/stderr as
# None. Flask/Werkzeug write startup log messages to them unconditionally,
# which raises AttributeError and silently kills the Flask thread (daemon
# thread exceptions have no console to print to). Give them a real stream
# before anything else imports logging.
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

import socket
import threading
import time
import traceback
import urllib.request
import urllib.error
import webview


def _resource(relative: str) -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _start_flask(port: int) -> None:
    try:
        from app import socketio, app
        # Local-only desktop app (127.0.0.1, single user) — the Werkzeug
        # dev server is appropriate here, not an actual production deployment.
        socketio.run(app, host='127.0.0.1', port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    except Exception:
        with open(os.path.join(_app_dir(), 'error.log'), 'w') as f:
            f.write(traceback.format_exc())
        raise


if __name__ == '__main__':
    port = _find_free_port()

    server_thread = threading.Thread(target=_start_flask, args=(port,), daemon=True)
    server_thread.start()

    # Wait until Flask is actually serving HTTP (not just TCP open). No fixed
    # cutoff: onefile extraction / cold antivirus scans can push startup well
    # past a few seconds, and opening the window before Flask is ready just
    # shows a permanent "connection refused" page.
    server_ready = False
    while server_thread.is_alive():
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1)
            server_ready = True
            break
        except Exception:
            time.sleep(0.25)

    url = f'http://127.0.0.1:{port}' if server_ready else None
    webview.create_window(
        'DownYT',
        url,
        html=None if server_ready else '<h2 style="font-family:sans-serif;padding:2em">DownYT failed to start. Check error.log next to the app, or restart it.</h2>',
        width=1100,
        height=750,
        resizable=True,
        min_size=(800, 600),
    )
    webview.start(icon=_resource('static/icon.ico'))
