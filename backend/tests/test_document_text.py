"""Text updates preserve old content on validation, vector and DB failures."""
from pathlib import Path
import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import auth
from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.main import app
from app.rag.vectorstore import get_store
from app.services import document_text, doc_service

CONTENT = '一元二次方程的判别式用于判断实数根的个数。例题：方程 x^2-3x+2=0 的根是 1 和 2，因式分解得到 (x-1)(x-2)=0。'
NEW = '函数导数的新版本知识点：函数 f(x)=x^3 的导数为 3x^2。导数可以描述瞬时变化率，也可以用于分析函数的单调性、极值以及切线斜率。'


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    result = browser.post('/api/auth/register', json={
        'username': 'edit_' + uuid4().hex[:10], 'password': 'Text-learning-2026',
    })
    assert result.status_code == 200, result.text
    return {'X-CSRF-Token': result.json()['data']['csrf_token']}


def setup(browser, suffix='txt'):
    headers = login(browser)
    response = browser.post('/api/docs/upload', files={
        'file': ('edit.' + suffix, (CONTENT + uuid4().hex).encode('utf-8'), 'text/plain'),
    }, headers=headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()['data']['doc_id']
    url = f'/api/docs/{doc_id}/text'
    old = browser.get(url).json()['data']
    return headers, doc_id, url, old


@pytest.mark.parametrize('suffix', ['txt', 'md'])
def test_save_updates_source_chunks_vectors_and_keeps_backup(browser, suffix):
    headers, doc_id, url, old = setup(browser, suffix)
    with SessionLocal() as db:
        path = Path(db.get(Document, doc_id).stored_path)
        old_ids = {c.id for c in db.query(Chunk).filter_by(doc_id=doc_id)}
    before = path.read_bytes()
    response = browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers)
    assert response.status_code == 200, response.text
    updated = browser.get(url).json()['data']
    assert updated['content'] == NEW and updated['version'] != old['version']
    assert path.read_text(encoding='utf-8') == NEW
    assert not (old_ids & get_store().ids())
    assert '新版本知识点' in browser.get(f'/api/docs/{doc_id}/preview').text
    backups = list((path.parent / '.versions' / doc_id).glob('*/' + path.name))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    assert backups[0].with_name('index.json').exists()
    assert browser.put(url, json={'content': NEW + '旧页面', 'version': old['version']}, headers=headers).status_code == 409
    assert browser.get(url).json()['data']['content'] == NEW
    no_change = browser.put(url, json={'content': NEW, 'version': updated['version']}, headers=headers)
    assert no_change.json()['data']['changed'] is False
    assert browser.delete(f'/api/docs/{doc_id}', headers=headers).status_code == 200
    assert not (path.parent / '.versions' / doc_id).exists()


def test_validation_csrf_and_ownership_retain_old_data(browser):
    headers, doc_id, url, old = setup(browser)
    assert browser.put(url, json={'content': '太短', 'version': old['version']}, headers=headers).status_code == 422
    assert browser.put(url, json={'content': NEW, 'version': old['version']}).status_code == 403
    assert browser.put(url, json={'content': 'x'*200001, 'version': old['version']}, headers=headers).status_code == 400
    assert browser.get(url).json()['data'] == old
    other = login(browser)
    assert browser.get(url).status_code == 403
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=other).status_code == 403
    browser.cookies.clear()
    assert browser.get(url).status_code == 401


@pytest.mark.parametrize('failure', ['embedding', 'vector', 'database'])
def test_failed_update_preserves_source_and_index(browser, monkeypatch, failure):
    headers, doc_id, url, old = setup(browser)
    store = get_store()
    before = store.snapshot_doc(doc_id)
    with SessionLocal() as db:
        path = Path(db.get(Document, doc_id).stored_path)
        raw = path.read_bytes()
    if failure == 'embedding':
        monkeypatch.setattr(document_text, 'embed_texts', lambda texts: (_ for _ in ()).throw(RuntimeError('embedding failed')))
    else:
        target, name = (store, '_save') if failure == 'vector' else (Session, 'commit')
        original = getattr(target, name)
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('injected write failure')
            return original(*args, **kwargs)
        monkeypatch.setattr(target, name, fail_once)
    response = browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers)
    assert response.status_code == 500, response.text
    assert path.read_bytes() == raw
    assert store.snapshot_doc(doc_id) == before
    assert browser.get(url).json()['data'] == old
    assert browser.get(f'/api/docs/{doc_id}/preview').json()['data']['items']


def test_busy_and_external_file_changes_are_rejected(browser):
    headers, doc_id, url, old = setup(browser)
    with doc_service._INGEST_LOCK:
        assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 409
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        path = Path(doc.stored_path)
        doc.status = 'parsing'
        db.commit()
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 409
    path.write_text('outside change', encoding='utf-8')
    assert browser.get(url).status_code == 409


def test_non_text_document_and_non_utf8_are_not_rewritten(browser):
    headers, doc_id, url, old = setup(browser)
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        doc.file_type = 'pdf'
        db.commit()
    assert browser.get(url).status_code == 415
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 415
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        doc.file_type = 'txt'
        raw = CONTENT.encode('gb18030')
        Path(doc.stored_path).write_bytes(raw)
        doc.content_hash = hashlib.sha256(raw).hexdigest()
        db.commit()
    assert browser.get(url).status_code == 422


def test_duplicate_text_does_not_replace_existing_document(browser):
    headers, doc_id, url, old = setup(browser)
    response = browser.post('/api/docs/upload', files={
        'file': ('existing.txt', NEW.encode('utf-8'), 'text/plain'),
    }, headers=headers)
    assert response.status_code == 200
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 409
    assert browser.get(url).json()['data'] == old


def test_chroma_replacement_compensates_failed_transaction():
    import chromadb
    from app.rag.vectorstore import ChromaVectorStore
    store = object.__new__(ChromaVectorStore)
    client = chromadb.EphemeralClient()
    name = 'edit-test-' + uuid4().hex
    store.collection = client.create_collection(name)
    old = [{'id': 'old', 'v': [1., 0.], 'd': 'old text', 'm': {'doc_id': 'doc-test', 'kb_id': 'kb-test'}}]
    new = [{'id': 'new', 'v': [0., 1.], 'd': 'new text', 'm': {'doc_id': 'doc-test', 'kb_id': 'kb-test'}}]
    try:
        store._restore_items(old)
        with pytest.raises(RuntimeError):
            with store.replacing_doc('doc-test', new):
                raise RuntimeError('database failed')
        assert store.snapshot_doc('doc-test') == old
        with store.replacing_doc('doc-test', new):
            pass
        assert store.snapshot_doc('doc-test') == new
    finally:
        client.delete_collection(name)
