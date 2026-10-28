"""Prepare official ONNX formula weights without modifying application data."""
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'data' / 'models' / 'formula-onnx'
SOURCE = 'https://github.com/RapidAI/RapidLaTeXOCR/releases/download/v0.0.0/'


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name in ('encoder.onnx', 'decoder.onnx', 'image_resizer.onnx', 'tokenizer.json'):
        target = DESTINATION / name
        if target.exists():
            print(f'Already present: {name}', flush=True)
            continue
        temporary = target.with_suffix('.download')
        try:
            with urlopen(SOURCE + name, timeout=30) as response, temporary.open('wb') as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    total += len(chunk)
                expected = response.headers.get('Content-Length')
                if total == 0 or (expected and int(expected) != total):
                    raise RuntimeError(f'Incomplete download: {name}')
            temporary.replace(target)
            print(f'Ready: {name} ({total:,} bytes)', flush=True)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
