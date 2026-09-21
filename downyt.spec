# -*- mode: python ; coding: utf-8 -*-
import os
import shutil

# Bundle ffmpeg so the app runs on PCs without it installed. Prefer a copy in
# vendor/ffmpeg/ (drop ffmpeg.exe there to pin a version), else use PATH.
_ffmpeg = os.path.join('vendor', 'ffmpeg', 'ffmpeg.exe')
if not os.path.isfile(_ffmpeg):
    _ffmpeg = shutil.which('ffmpeg')
if not _ffmpeg:
    raise SystemExit('ffmpeg.exe not found: put it in vendor/ffmpeg/ or on PATH before building.')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        (_ffmpeg, 'ffmpeg'),
    ],
    hiddenimports=[
        'engineio.async_drivers.threading',
        'flask_socketio',
        'engineio',
        'socketio',
        'webview',
        'webview.platforms.winforms',
        'clr',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DownYT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='static/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='DownYT',
)
