"""A acceptance regressions: real isolated stores, stubbed external services."""
import importlib.util
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.rag import indexer, vectorstore
from app.rag.retriever import load_chunk_records
from app.services import doc_service
from app.services.parsing import recognize


@pytest.fixture(params=['local', 'chroma'])
def isolated_store(request, tmp_path, monkeypatch):
    if request.param == 'chroma':
        pytest.importorskip('chromadb')
        monkeypatch.setattr(settings, 'chroma_dir', str(tmp_path / 'chroma'))
        store = vectorstore.ChromaVectorStore()
    else:
        store = vectorstore.LocalVectorStore(tmp_path / 'vectors.json')
    monkeypatch.setattr(vectorstore, 'get_store', lambda: store)
    monkeypatch.setattr(indexer, 'get_store', lambda: store)
    return store


def upload(client, filename='source.md'):
    headers = {'Authorization': 'Bearer dev:fix_' + uuid4().hex[:10]}
    raw = ('定义：连续函数在闭区间上可以取得最大值与最小值。\n' * 7).encode()
    result = client.post('/api/docs/upload', headers=headers, files={'file': (filename, raw, 'text/markdown')})
    assert result.status_code == 200, result.text
    doc_id = result.json()['data']['doc_id']
    assert client.get(f'/api/docs/{doc_id}/status', headers=headers).json()['data']['status'] == 'ready'
    return doc_id, raw, headers


def chunk_ids(doc_id):
    with SessionLocal() as db:
        return {row.id for row in db.query(Chunk).filter(Chunk.doc_id == doc_id)}


def test_reindex_removes_only_old_vectors(client, isolated_store):
    doc_id, _, headers = upload(client)
    previous = chunk_ids(doc_id)
    for _ in range(2):
        assert client.post(f'/api/docs/{doc_id}/reindex', headers=headers).status_code == 200
        current = chunk_ids(doc_id)
        assert current and current.isdisjoint(previous)
        assert isolated_store.ids() == current
        previous = current


def test_identical_overwrite_keeps_published_document(client, isolated_store):
    doc_id, raw, headers = upload(client)
    previous = isolated_store.ids()
    response = client.post('/api/docs/upload', headers=headers, data={'overwrite': 'true'},
                           files={'file': ('source.md', raw, 'text/markdown')})
    assert response.status_code == 409
    assert client.get(f'/api/docs/{doc_id}/status', headers=headers).json()['data']['status'] == 'ready'
    assert any(doc['id'] == doc_id for doc in client.get('/api/docs', headers=headers).json()['data'])
    assert isolated_store.ids() == previous


@pytest.mark.parametrize('failure', ['parse', 'embedding', 'vector_write', 'old_cleanup'])
def test_failed_reindex_keeps_old_version_usable(client, isolated_store, monkeypatch, failure):
    doc_id, raw, headers = upload(client)
    before = chunk_ids(doc_id)
    if failure == 'parse':
        def fail(*args):
            raise AppError(2003, 'isolated parse failure')
        monkeypatch.setattr(doc_service, 'load_pages', fail)
    elif failure == 'embedding':
        def fail(*args):
            raise AppError(5000, 'isolated embedding failure')
        monkeypatch.setattr(indexer, 'embed_texts', fail)
    elif failure == 'vector_write':
        upsert = isolated_store.upsert
        def fail(**kwargs):
            upsert(**kwargs)
            raise RuntimeError('vector batch written before failure')
        monkeypatch.setattr(isolated_store, 'upsert', fail)
    else:
        delete = isolated_store.delete_ids
        failed = False
        def fail(ids):
            nonlocal failed
            delete(ids)
            if set(ids) == before and not failed:
                failed = True
                raise RuntimeError('old vector cleanup failed after deletion')
        monkeypatch.setattr(isolated_store, 'delete_ids', fail)
    assert client.post(f'/api/docs/{doc_id}/reindex', headers=headers).status_code == 200
    status = client.get(f'/api/docs/{doc_id}/status', headers=headers).json()['data']
    assert status['status'] == 'ready' and status['error']
    assert client.get(f'/api/docs/{doc_id}/preview', headers=headers).status_code == 200
    assert chunk_ids(doc_id) == before == isolated_store.ids()
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        assert Path(doc.stored_path).read_bytes() == raw
        assert {row.chunk_id for row in load_chunk_records(db, [doc.kb_id])} == before
        assert doc_service._latest_task(db, doc_id).status in ('failed', 'rejected')


@pytest.fixture
def label_module(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/auto_label.py'
    spec = importlib.util.spec_from_file_location('label_acceptance', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(settings, 'label_api_base', 'https://offline.invalid')
    monkeypatch.setattr(settings, 'label_api_key', 'offline-test-placeholder')
    return module


@pytest.mark.parametrize('change', ['version', 'deleted', 'other_task', 'none'])
def test_labels_compare_source_version_before_writing(client, label_module, monkeypatch, capsys, change):
    doc_id, _, _ = upload(client, 'labels.md')
    module = label_module
    module._args.scope, module._args.force = doc_id, True
    tags = {'knowledge_points': ['连续函数'], 'question_types': ['计算题'], 'difficulty': '基础'}
    other = {**tags, 'knowledge_points': ['其他任务标签']}
    def finish(title, body):
        assert '连续函数' in body
        with SessionLocal() as db:
            doc = db.get(Document, doc_id)
            if change == 'version':
                doc.content_hash = 'f' * 64
                doc.tags_json = None
            elif change == 'deleted':
                doc_service.delete_document(db, doc)
            elif change == 'other_task':
                doc.tags_json = json.dumps(other, ensure_ascii=False)
            db.commit()
        return tags
    monkeypatch.setattr(module, 'call_llm', finish)
    assert module.main() == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary['done'] == (1 if change == 'none' else 0)
    assert summary['stale'] == (0 if change == 'none' else 1)
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if change == 'version':
            assert doc.tags_json is None
        elif change == 'deleted':
            assert doc is None
        else:
            assert json.loads(doc.tags_json) == (tags if change == 'none' else other)


def test_label_failure_preserves_saved_labels_and_returns_failure(client, label_module, monkeypatch):
    doc_id, _, _ = upload(client, 'label-fail.md')
    label_module._args.scope, label_module._args.force = doc_id, True
    original = json.dumps({'knowledge_points': ['旧有效标签'], 'difficulty': '基础'})
    with SessionLocal() as db:
        db.get(Document, doc_id).tags_json = original
        db.commit()
    monkeypatch.setattr(label_module, 'call_llm', lambda *args: None)
    assert label_module.main() == 1
    with SessionLocal() as db:
        assert db.get(Document, doc_id).tags_json == original


@pytest.mark.parametrize('question', [
    '$$x^2-3x+2=0$$',
    '已知 $$x^2-3x+2=0$$，求实根。',
    '先用 $x>0$，再求 $$f(x)=x^2$$ 的导数，比较 $$f(1)=1$$。',
])
def test_vlm_adapter_keeps_complete_formula_question(monkeypatch, question):
    monkeypatch.setattr(settings, 'ocr_engine', 'vlm')
    monkeypatch.setattr(recognize, '_recognize_vlm', lambda raw: question)
    picture = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(picture, format='PNG')
    output = recognize.recognize_question_image('question.png', picture.getvalue())
    assert output['text'] == question
    assert output['latex'] and not output['warnings']


@pytest.mark.parametrize('mismatch', ['id', 'content', 'ownership', 'none'])
def test_snapshot_import_requires_matching_relational_rows(client, tmp_path, monkeypatch, mismatch):
    doc_id, _, _ = upload(client, 'snapshot.md')
    with SessionLocal() as db:
        row = db.query(Chunk).filter(Chunk.doc_id == doc_id).first()
        item = {'id': row.id, 'v': [1.0, 0.0], 'd': row.content,
                'm': {name: getattr(row, name) for name in ('doc_id', 'kb_id', 'user_id')}}
    if mismatch == 'id':
        item['id'] = 'old-snapshot-id'
    elif mismatch == 'content':
        item['d'] = 'a different version'
    elif mismatch == 'ownership':
        item['m']['kb_id'] = 'another-kb'
    source = tmp_path / 'snapshot.json'
    source.write_text(json.dumps({'items': [item]}), encoding='utf-8')
    target = vectorstore.LocalVectorStore(tmp_path / 'target.json')
    monkeypatch.setattr(vectorstore, 'ChromaVectorStore', lambda: target)
    if mismatch == 'none':
        assert indexer.migrate_local_vectors(source)['migrated'] == 1
        assert target.ids() == {item['id']}
    else:
        with pytest.raises(AppError, match='不匹配'):
            indexer.migrate_local_vectors(source)
        assert not target.ids()
