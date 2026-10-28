"""C local integration launcher; preflight never loads models or calls paid APIs."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import getpass

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.env.c-integration'


def prepare(args):
    # Explicit overrides keep the existing demo DB, uploads and 256-dimensional vectors isolated.
    data = args.data_dir.resolve()
    if 'c-demo' in data.parts or data == ROOT:
        raise ValueError('Choose an isolated integration data directory')
    values = {
        'APP_ENV': 'dev',
        'DATABASE_URL': 'sqlite:///' + (data / 'app.db').as_posix(),
        'UPLOAD_DIR': str(data / 'uploads'),
        'CHROMA_DIR': str(data / 'chroma'),
        'CHROMA_COLLECTION': 'math_chunks',
        'EMBED_PROVIDER': 'local',
        'EMBED_LOCAL_MODEL': str(args.embedding_dir.resolve()),
        'EMBED_MODEL': 'BAAI/bge-m3',
        'EMBED_DIM': '1024',
        'EMBED_API_BASE': '',
        'EMBED_API_KEY': '',
        'VECTOR_BACKEND': 'chroma',
        'MOCK_LLM': 'false',
        'RERANK_PROVIDER': 'local',
        'RERANK_CANDIDATE_LIMIT': '16',
        'RERANK_MAX_LENGTH': '512',
        'RERANK_BATCH_SIZE': '2',
        'RERANK_LOCAL_MODEL': str(args.reranker_dir.resolve()),
        'RELEVANCE_THRESHOLD': '0.62',
        'OCR_FORMULA': 'rapid_latex',
        # Prevent model libraries from downloading implicitly during startup/inference.
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
        'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4',
        'ANONYMIZED_TELEMETRY': 'False',
        'LLM_FIRST_TOKEN_TIMEOUT_S': '90', 'LLM_TIMEOUT_S': '180',
    }
    local = dotenv_values(CONFIG) if CONFIG.exists() else {}
    values.update({
        'DEEPSEEK_API_KEY': os.environ.get('DEEPSEEK_API_KEY') or local.get('DEEPSEEK_API_KEY') or '',
        'DEEPSEEK_BASE_URL': local.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com',
        'DEEPSEEK_MODEL': local.get('DEEPSEEK_MODEL') or 'deepseek-flash',
        'LLM_MAX_TOKENS': '4096',
        'LLM_THINKING': 'disabled',
        'LLM_REASONING_EFFORT': 'low',
        'LLM_MAX_RETRIES': '0',
    })
    os.environ.update(values)
    missing = []
    if not values['DEEPSEEK_API_KEY'].strip():
        missing.append('DEEPSEEK_API_KEY (configure locally; never paste into chat)')
    for package in ('chromadb', 'sentence_transformers', 'uvicorn'):
        if importlib.util.find_spec(package) is None:
            missing.append(f'Python dependency: {package}')
    for folder in (args.embedding_dir, args.reranker_dir):
        weights = (list(folder.glob('*.safetensors')) + list(folder.glob('pytorch_model*.bin')))
        if not (folder / 'config.json').is_file() or not weights:
            missing.append(f'Local model files: {folder}')
    return data, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prerequisites only; no DB writes or model calls')
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'Temp/mathrag-c-integration-20261028')
    parser.add_argument('--embedding-dir', type=Path, default=ROOT/'data/models/bge-m3')
    parser.add_argument('--reranker-dir', type=Path, default=ROOT/'data/models/bge-reranker-v2-m3')
    parser.add_argument('--port', type=int, default=8002, choices=range(1024,65536), metavar='PORT')
    parser.add_argument('--prompt-key', action='store_true')
    args = parser.parse_args()
    if args.prompt_key and not args.check:
        os.environ['DEEPSEEK_API_KEY']=getpass.getpass('DeepSeek key (hidden; memory only): ')
    data, missing = prepare(args)
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
        if probe.connect_ex(('127.0.0.1', args.port)) == 0:
            print(f'Port {args.port} is occupied; no existing process was stopped.')
            return 1
    if not (data/'validation-source.json').is_file():
        raise ValueError('Prepare the isolated snapshot data before starting integration')
    sys.path.insert(0, str(ROOT / 'backend'))
    from c_integration_budget import install_runtime
    install_runtime(data)
    from app.rag.embedder import embed_texts
    from app.rag import reranker
    print('Loading local embedding and reranking models (no paid call).',flush=True)
    if len(embed_texts(['函数的单调性'])[0])!=1024:
        raise RuntimeError('Unexpected embedding dimensions')
    reranker._local.scores('增函数的定义',['函数值随自变量增加而增加。'])
    print('Local models loaded. Persistent cumulative budget: 100 calls / USD 1.00.',flush=True)
    if os.environ.get('MATHRAG_SPEED_PROBE') == '1':
        from c_speed_probe import probe
        probe(data)
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
