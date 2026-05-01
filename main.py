import sys
import os
import socket
import threading
import time
import urllib.request
import urllib.error
import webview


def _resource(relative: str) -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _start_flask(port: int) -> None:
    from app import socketio, app
    socketio.run(app, host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    port = _find_free_port()

    server_thread = threading.Thread(target=_start_flask, args=(port,), daemon=True)
    server_thread.start()

    # Wait until Flask is actually serving HTTP (not just TCP open)
    import urllib.request
    import urllib.error
    for _ in range(40):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1)
            break
        except Exception:
            time.sleep(0.25)

    webview.create_window(
        'DownYT',
        f'http://127.0.0.1:{port}',
        width=1100,
        height=750,
        resizable=True,
        min_size=(800, 600),
    )
    webview.start(icon=_resource('static/icon.ico'))
