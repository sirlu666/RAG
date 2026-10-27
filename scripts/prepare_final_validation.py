"""Build an isolated validation DB and Chroma collection from the shipped snapshot.

Preserves snapshot chunk/document/KB IDs and text; maps ownership to one validation
user. Never restores private accounts or overwrites an existing unowned database.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT/'data/chroma/vectors/math_chunks_bge-m3.json.gz')
    parser.add_argument('--corpus', type=Path, default=ROOT/'knowledge/raw')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--embedding-dir', type=Path, required=True)
    args = parser.parse_args()
    data = args.data_dir.resolve()
    if 'c-demo' in data.parts:
        parser.error('The existing demo directory is not a validation target')
    digest = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    marker = data/'validation-source.json'
    if data.exists() and any(data.iterdir()):
        if not marker.exists() or json.loads(marker.read_text(encoding='utf-8')).get('snapshot_sha256') != digest:
            parser.error('Target is not owned by this snapshot validation run; choose a new empty directory')
    with gzip.open(args.snapshot, 'rt', encoding='utf-8') as fh:
        snapshot = json.load(fh)
    items = snapshot['items']
    if not items or len({item['id'] for item in items}) != len(items):
        parser.error('Snapshot is empty or contains duplicate IDs')
    paths = {}
    for path in args.corpus.rglob('*.md'):
        if path.name in paths:
            parser.error('Ambiguous corpus filename: '+path.name)
        paths[path.name] = path
    documents = {}
    for item in items:
        meta = item['m']
        if len(item['v']) != 1024 or item['id'] != meta.get('chunk_id') or meta['doc_name'] not in paths:
            parser.error('Snapshot dimensions/IDs/source file are invalid')
        identity = (meta['kb_id'], meta['doc_name'])
        if documents.setdefault(meta['doc_id'], identity) != identity:
            parser.error('Conflicting document identity in snapshot')
    data.mkdir(parents=True, exist_ok=True)
    report = {'snapshot_sha256':digest, 'status':'preparing', 'user_id':'u_final_validation',
              'documents':len(documents), 'chunks':len(items), 'kb_ids':sorted({i['m']['kb_id'] for i in items}),
              'offsets':'Original char offsets unavailable; use doc_id/chunk_id/seq and source hash.'}
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    os.environ.update(DATABASE_URL='sqlite:///'+(data/'app.db').as_posix(), UPLOAD_DIR=str(data/'uploads'),
        CHROMA_DIR=str(data/'chroma'), EMBED_PROVIDER='local', EMBED_LOCAL_MODEL=str(args.embedding_dir.resolve()),
        EMBED_DIM='1024', VECTOR_BACKEND='chroma', ANONYMIZED_TELEMETRY='False')
    sys.path.insert(0, str(ROOT/'backend'))
    from app.db import chat_models  # noqa: F401
    from app.db.session import ensure_dirs, init_db, SessionLocal
    from app.db.models import User, KnowledgeBase, Document, Chunk
    from app.rag.vectorstore import get_store
    ensure_dirs()
    init_db()
    with SessionLocal() as db:
        if db.get(User, report['user_id']) is None:
            db.add(User(id=report['user_id'], username='final_validation'))
            db.flush()
        for kb_id in report['kb_ids']:
            if db.get(KnowledgeBase, kb_id) is None:
                db.add(KnowledgeBase(id=kb_id, user_id=report['user_id'], name='数学验证语料'))
        db.flush()
        for doc_id, (kb_id, name) in documents.items():
            raw = paths[name].read_bytes()
            target = data/'uploads'/(doc_id+'.md')
            if target.exists() and target.read_bytes() != raw:
                parser.error('Validation source changed; choose a new data directory')
            if not target.exists():
                target.write_bytes(raw)
            if db.get(Document, doc_id) is None:
                db.add(Document(id=doc_id,kb_id=kb_id,user_id=report['user_id'],filename=name,
                    stored_path=str(target),file_type='md',size_bytes=len(raw),status='ready',
                    content_hash=hashlib.sha256(raw).hexdigest(),
                    chunk_count=sum(i['m']['doc_id']==doc_id for i in items)))
        db.flush()
        for item in items:
            meta=item['m']
            if db.get(Chunk,item['id']) is None:
                db.add(Chunk(id=item['id'],doc_id=meta['doc_id'],kb_id=meta['kb_id'],user_id=report['user_id'],
                    seq=meta['seq'],content=item['d'],content_type=meta['content_type'],
                    page=meta.get('page'),char_start=0,char_end=0,has_formula=meta.get('has_formula',False)))
        db.commit()
    store=get_store()
    for start in range(0,len(items),128):
        batch=items[start:start+128]
        store.upsert(ids=[i['id'] for i in batch],vectors=[i['v'] for i in batch],
            documents=[i['d'] for i in batch],metadatas=[{**i['m'],'user_id':report['user_id']} for i in batch])
    with SessionLocal() as db:
        ids={row.id for row in db.query(Chunk)}
    if ids != store.ids():
        raise RuntimeError('Validation relational/vector IDs differ')
    report.update(status='ready',vectors=store.count())
    marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
