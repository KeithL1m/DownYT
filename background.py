import os
import sys
import threading
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageOps

from converter import detect_kind, unique_path

# Same model and pre/post-processing as rembg's default "u2net" session, run
# directly through onnxruntime. rembg itself drags in scipy/scikit-image/numba
# (~450 MB) for optional alpha matting that we don't use.
MODEL_NAME = 'u2net.onnx'
_INPUT_SIZE = (320, 320)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_session = None
_session_lock = threading.Lock()


def _models_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'models')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor', 'models')


def _get_session():
    """Load the model once; it's ~176 MB so every job shares one session."""
    global _session
    with _session_lock:
        if _session is None:
            import onnxruntime as ort
            path = os.path.join(_models_dir(), MODEL_NAME)
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f'Background removal model not found ({MODEL_NAME}). '
                    'Run setup_models.ps1 and rebuild the app.')
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            _session = ort.InferenceSession(path, sess_options=opts, providers=['CPUExecutionProvider'])
        return _session


def _predict_mask(img: Image.Image) -> Image.Image:
    session = _get_session()
    small = img.convert('RGB').resize(_INPUT_SIZE, Image.Resampling.LANCZOS)
    arr = np.asarray(small, dtype=np.float32)
    arr = arr / max(float(arr.max()), 1e-6)
    arr = (arr - _MEAN) / _STD
    tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

    pred = session.run(None, {session.get_inputs()[0].name: tensor})[0][:, 0, :, :]
    lo, hi = float(pred.min()), float(pred.max())
    pred = np.squeeze((pred - lo) / max(hi - lo, 1e-6))
    mask = Image.fromarray((pred * 255).astype('uint8'), mode='L')
    return mask.resize(img.size, Image.Resampling.LANCZOS)


def remove_background(source: str, output_dir: Optional[str],
                      progress_cb: Callable[[int], None], output_name: Optional[str] = None) -> str:
    """Cut the background out of an image; saves a transparent PNG and returns its path.

    `output_name` (without extension) comes from the Save As dialog; by default the
    file is saved as `<name>_nobg.png`.
    """
    if detect_kind(source) != 'image':
        raise ValueError('Background removal only works on image files')
    if not os.path.isfile(source):
        raise FileNotFoundError(f'File not found: {source}')

    out_dir = output_dir or os.path.dirname(os.path.abspath(source))
    os.makedirs(out_dir, exist_ok=True)
    stem = output_name or f'{os.path.splitext(os.path.basename(source))[0]}_nobg'
    output = unique_path(out_dir, stem, 'png')

    try:
        progress_cb(5)
        with Image.open(source) as opened:
            img = ImageOps.exif_transpose(opened).convert('RGBA')
        _get_session()  # first job pays the model load; make that visible
        progress_cb(25)
        mask = _predict_mask(img)
        progress_cb(85)
        img.putalpha(mask)
        img.save(output, format='PNG')
    except BaseException:
        if os.path.exists(output):
            try:
                os.remove(output)
            except OSError:
                pass
        raise
    progress_cb(100)
    return output
