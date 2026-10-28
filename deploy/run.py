"""Portable single-process deployment; serves the built UI and API on one port."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def prepare_models(directory):
    from huggingface_hub import snapshot_download
    models = [('BAAI/bge-m3', 'bge-m3', '5617a9f61b028005a4858fdac845db406aefb181'),
              ('BAAI/bge-reranker-v2-m3', 'bge-reranker-v2-m3', '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e')]
    for repository, name, revision in models:
        target = directory / name
        if (target / 'config.json').exists() and any((target / weight).exists() for weight in ['pytorch_model.bin', 'model.safetensors']):
            continue
        snapshot_download(repository, revision=revision, local_dir=str(target),
                          allow_patterns=['*.json', '*.model', 'pytorch_model.bin', 'model.safetensors', '1_Pooling/*'])
    if os.environ.get('OCR_FORMULA') == 'rapid_latex':
        from urllib.request import urlopen
        target = directory / 'formula-onnx'
        target.mkdir(parents=True, exist_ok=True)
        for name in ['encoder.onnx', 'decoder.onnx', 'image_resizer.onnx', 'tokenizer.json']:
            path = target / name
            if path.exists():
                continue
            temporary = path.with_suffix('.download')
            with urlopen('https://github.com/RapidAI/RapidLaTeXOCR/releases/download/v0.0.0/' + name, timeout=120) as response, temporary.open('wb') as destination:
                import shutil
                shutil.copyfileobj(response, destination)
            if not temporary.stat().st_size:
                raise ValueError('Empty formula model download')
            temporary.replace(path)


def seed_materials():
    import hashlib
    from app.db.models import KnowledgeBase, User, PublishedKnowledgeBase, Document
    from app.db.session import SessionLocal
    from app.services import doc_service
    with SessionLocal() as db:
        user = db.query(User).filter_by(username='__package_materials__').first()
        if user is None:
            user = User(username='__package_materials__')  # no shared login or default password
            db.add(user); db.commit()
        kb = db.query(KnowledgeBase).filter_by(user_id=user.id, name='部署示例资料').first()
        if kb is None:
            kb = KnowledgeBase(user_id=user.id, name='部署示例资料')
            db.add(kb); db.commit()
        if db.get(PublishedKnowledgeBase, kb.id) is None:
            db.add(PublishedKnowledgeBase(kb_id=kb.id)); db.commit()
        for path in sorted((ROOT / 'deploy/sample-materials').glob('*.md')):
            raw = path.read_bytes()
            old = db.query(Document).filter_by(kb_id=kb.id, content_hash=hashlib.sha256(raw).hexdigest()).first()
            if old:
                continue
            doc, _ = doc_service.create_document(db, user, kb.id, path.name, raw)
            db.commit()
            doc_service.run_ingest(doc.id)
            db.expire_all()
            if db.get(Document, doc.id).status != 'ready':
                raise RuntimeError('Sample ingestion failed; inspect the document status')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='No key/models; template answers, not real mathematical QA')
    parser.add_argument('--download-models', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'runtime/data')
    parser.add_argument('--models-dir', type=Path, default=ROOT / 'runtime/models')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    from dotenv import dotenv_values
    for key, value in dotenv_values(ROOT / 'deploy/deploy.env').items():
        if value is not None:
            os.environ.setdefault(key, value)
    data, models = args.data_dir.resolve(), args.models_dir.resolve()
    os.environ.setdefault('FORMULA_MODEL_DIR', str(models / 'formula-onnx'))
    if data == ROOT or data == (ROOT / 'data').resolve():
        raise ValueError('Use a separate deployment data directory')
    data.mkdir(parents=True, exist_ok=True)
    os.environ.update({'DATABASE_URL': 'sqlite:///' + (data / 'app.db').as_posix(),
                       'UPLOAD_DIR': str(data / 'uploads'), 'CHROMA_DIR': str(data / 'chroma'),
                       'EMBED_PROVIDER': 'dev' if args.demo else 'local',
                       'VECTOR_BACKEND': 'local' if args.demo else 'chroma',
                       'EMBED_DIM': '256' if args.demo else '1024',
                       'EMBED_LOCAL_MODEL': str(models / 'bge-m3'),
                       'RERANK_LOCAL_MODEL': str(models / 'bge-reranker-v2-m3'),
                       'RERANK_PROVIDER': 'none' if args.demo else 'local',
                       'MOCK_LLM': 'true' if args.demo else 'false',
                       'RELEVANCE_THRESHOLD': '0.05' if args.demo else '0.62'})
    for key, value in {'LLM_THINKING': 'disabled', 'LLM_MAX_RETRIES': '0', 'RERANK_CANDIDATE_LIMIT': '16',
                       'RERANK_MAX_LENGTH': '512', 'RERANK_BATCH_SIZE': '2', 'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4'}.items():
        os.environ.setdefault(key, value)
    if not args.demo:
        if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
            raise ValueError('Set your own DEEPSEEK_API_KEY in deploy/deploy.env or the process environment')
        if args.download_models:
            prepare_models(models)
        for name in ['bge-m3', 'bge-reranker-v2-m3']:
            if not (models / name / 'config.json').is_file():
                raise ValueError('Models missing; start with --download-models once')
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.main import app
    from app.db.session import ensure_dirs, init_db
    ensure_dirs(); init_db(); seed_materials()
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException
    from starlette.responses import FileResponse
    static = ROOT / 'frontend/dist'
    if not (static / 'index.html').is_file():
        raise ValueError('Built frontend missing; use the deployment ZIP or build frontend first')
    class SPA(StaticFiles):
        async def get_response(self, path, scope):
            clean = path.replace('\\', '/').lstrip('/')
            try:
                return await super().get_response(path, scope)
            except HTTPException as error:
                if error.status_code == 404 and scope['method'] in ('GET', 'HEAD') and clean.split('/')[0] not in ('api', 'docs', 'redoc', 'openapi.json', 'assets') and '.' not in Path(clean).name:
                    return FileResponse(static / 'index.html')
                raise
    app.mount('/', SPA(directory=static, html=True), name='frontend')
    print('DEMO: template answers only.' if args.demo else 'REAL QA: uses your own provider key and billing.', flush=True)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == '__main__':
    main()
