"""C local integration launcher; preflight never loads models or calls paid APIs."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.env.c-integration'


def prepare():
    # Explicit overrides keep the existing demo DB, uploads and 256-dimensional vectors isolated.
    data = ROOT / '.tmp' / 'c-integration'
    values = {
        'APP_ENV': 'dev',
        'DATABASE_URL': 'sqlite:///' + (data / 'app.db').as_posix(),
        'UPLOAD_DIR': str(data / 'uploads'),
        'CHROMA_DIR': str(data / 'chroma'),
        'CHROMA_COLLECTION': 'math_chunks',
        'EMBED_PROVIDER': 'local',
        'EMBED_LOCAL_MODEL': str(ROOT / 'data/models/bge-m3'),
        'EMBED_MODEL': 'BAAI/bge-m3',
        'EMBED_DIM': '1024',
        'EMBED_API_BASE': '',
        'EMBED_API_KEY': '',
        'VECTOR_BACKEND': 'chroma',
        'MOCK_LLM': 'false',
        'RERANK_PROVIDER': 'local',
        'RERANK_LOCAL_MODEL': str(ROOT / 'data/models/bge-reranker-v2-m3'),
        'RELEVANCE_THRESHOLD': '0.62',
        'OCR_FORMULA': 'rapid_latex',
        # Prevent model libraries from downloading implicitly during startup/inference.
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
    }
    local = dotenv_values(CONFIG) if CONFIG.exists() else {}
    values.update({
        'DEEPSEEK_API_KEY': local.get('DEEPSEEK_API_KEY') or '',
        'DEEPSEEK_BASE_URL': local.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com',
        'DEEPSEEK_MODEL': local.get('DEEPSEEK_MODEL') or 'deepseek-flash',
        'LLM_MAX_TOKENS': local.get('LLM_MAX_TOKENS') or '4096',
        'LLM_THINKING': local.get('LLM_THINKING') or 'enabled',
        'LLM_REASONING_EFFORT': local.get('LLM_REASONING_EFFORT') or 'low',
        'LLM_MAX_RETRIES': '0',
    })
    os.environ.update(values)
    missing = []
    if not CONFIG.exists():
        missing.append('Local configuration .env.c-integration')
    if not values['DEEPSEEK_API_KEY'].strip():
        missing.append('DEEPSEEK_API_KEY (configure locally; never paste into chat)')
    for package in ('chromadb', 'sentence_transformers', 'uvicorn'):
        if importlib.util.find_spec(package) is None:
            missing.append(f'Python dependency: {package}')
    for name in ('bge-m3', 'bge-reranker-v2-m3'):
        folder = ROOT / 'data/models' / name
        weights = (list(folder.glob('*.safetensors')) + list(folder.glob('pytorch_model*.bin')))
        if not (folder / 'config.json').is_file() or not weights:
            missing.append(f'Local model files: data/models/{name}')
    return data, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prerequisites only; no DB writes or model calls')
    args = parser.parse_args()
    data, missing = prepare()
    print('REAL INTEGRATION: local BGE-M3 + Chroma + local rerank + DeepSeek (mock disabled).')
    print(f'Isolated data directory: {data}')
    print('Retrieval threshold: 0.62 (B delivered baseline; verify against imported corpus).')
    if missing:
        print('Not ready:')
        for item in missing:
            print(f'  - {item}')
        print('No service started. Existing demo data and service are unchanged.')
        return 1
    print('Prerequisite files/config found; actual model loading and service access remain to be verified.')
    if args.check:
        return 0
    import socket
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            print('Port 8000 is occupied. Stop the current backend before starting this service.')
            return 1
    sys.path.insert(0, str(ROOT / 'backend'))
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
