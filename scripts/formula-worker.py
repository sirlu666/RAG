"""Isolated formula worker: PNG bytes on stdin, JSON on stdout, no data writes."""
import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from rapid_latex_ocr import LaTeXOCR

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'data' / 'models' / 'formula-onnx'


def main():
    files = ('image_resizer.onnx', 'encoder.onnx', 'decoder.onnx', 'tokenizer.json')
    if not all((MODELS / name).is_file() for name in files):
        raise RuntimeError('Prepare formula weights before serving requests.')
    model = LaTeXOCR(
        image_resizer_path=MODELS / 'image_resizer.onnx', encoder_path=MODELS / 'encoder.onnx',
        decoder_path=MODELS / 'decoder.onnx', tokenizer_json=MODELS / 'tokenizer.json',
    )
    # The upstream model works best at small screenshot resolutions. Oversized
    # crops can make its learned resizer lose symbols even for simple formulas.
    with Image.open(BytesIO(sys.stdin.buffer.read())) as source:
        image = source.convert('RGB')
    image.thumbnail((350, 128), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    latex, _ = model(buffer.getvalue())
    print(json.dumps({'latex': latex}, ensure_ascii=False))


if __name__ == '__main__':
    main()
