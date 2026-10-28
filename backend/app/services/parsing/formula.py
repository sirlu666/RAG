"""Run CPU formula OCR in an isolated environment, with no request-time downloads."""
import json
import os
import subprocess
from io import BytesIO
from threading import Lock

from app.core.config import ROOT_DIR

MODEL_DIR = ROOT_DIR / 'data' / 'models' / 'formula-onnx'
MODEL_FILES = ('encoder.onnx', 'decoder.onnx', 'image_resizer.onnx', 'tokenizer.json')
PYTHON = ROOT_DIR / '.venv-formula' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
_lock = Lock()


def require_ready():
    if not PYTHON.is_file() or not all((MODEL_DIR / name).is_file() for name in MODEL_FILES):
        raise RuntimeError('本机公式环境或模型未准备，请按 C-FORMULA-OCR.md 准备')


def recognize_array(image):
    from PIL import Image
    require_ready()
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format='PNG')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with _lock:
        result = subprocess.run(
            [str(PYTHON), '-X', 'utf8', str(ROOT_DIR / 'scripts' / 'formula-worker.py')],
            input=buffer.getvalue(), capture_output=True, timeout=120, cwd=str(ROOT_DIR), **options,
        )
    if result.returncode:
        raise RuntimeError('本机公式识别失败，原始 OCR 文字保留')
    latex = json.loads(result.stdout.decode('utf-8'))['latex']
    if not isinstance(latex, str) or len(latex) > 10000:
        raise RuntimeError('公式模型返回内容异常')
    return latex
