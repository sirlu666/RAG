"""Real-account metadata edits, retrieval names, failure recovery and category lifetime."""
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import auth
from app.db.models import Chunk, Document, DocumentCategory
from app.db.session import SessionLocal
from app.main import app
from app.rag.retriever import get_bm25_index, retrieve
from app.rag.vectorstore import get_store
from app.services import doc_service


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    response = browser.post('/api/auth/register', json={
        'username': 'meta_' + uuid4().hex[:10], 'password': 'Metadata-learning-2026',
    })
    assert response.status_code == 200, response.text
    return {'X-CSRF-Token': response.json()['data']['csrf_token']}


def upload(browser, headers, name='original.txt'):
    text = '一元二次方程的判别式用于判断实数根的个数。例题：方程 x^2-3x+2=0 的根是 1 和 2，因式分解得到 (x-1)(x-2)=0。' + uuid4().hex
    response = browser.post('/api/docs/upload', files={'file': (name, text.encode(), 'text/plain')}, headers=headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()['data']['doc_id']
    return next(doc for doc in browser.get('/api/docs').json()['data'] if doc['id'] == doc_id)


def test_list_exposes_existing_auto_labels_separately_from_manual_category(browser):
    headers = login(browser)
    doc = upload(browser, headers)
    assert doc['knowledge_points'] == [] and doc['question_types'] == [] and doc['difficulty'] is None
    with SessionLocal() as db:
        source = db.get(Document, doc['id'])
        source.tags_json = json.dumps({'knowledge_points': [' 判别式 ', '判别式', 12],
                                      'question_types': ['计算题'], 'difficulty': '进阶'})
        source.difficulty = '基础'
        db.commit()
    assert change(browser, headers, doc, category='手动分类').status_code == 200
    updated = next(item for item in browser.get('/api/docs').json()['data'] if item['id'] == doc['id'])
    assert updated['category'] == '手动分类'
    assert updated['knowledge_points'] == ['判别式']
    assert updated['question_types'] == ['计算题']
    assert updated['difficulty'] == '基础'
    login(browser)
    assert all(item['id'] != doc['id'] for item in browser.get('/api/docs').json()['data'])
    browser.cookies.clear()
    assert browser.get('/api/docs').status_code == 401


@pytest.mark.parametrize('raw', ['not-json', '[]', '{"knowledge_points":"判别式","question_types":12,"difficulty":{}}'])
def test_invalid_legacy_labels_do_not_break_document_list(browser, raw):
    headers = login(browser)
    doc = upload(browser, headers)
    with SessionLocal() as db:
        db.get(Document, doc['id']).tags_json = raw
        db.commit()
    response = browser.get('/api/docs')
    assert response.status_code == 200
    item = next(item for item in response.json()['data'] if item['id'] == doc['id'])
    assert item['knowledge_points'] == [] and item['question_types'] == [] and item['difficulty'] is None


def test_content_edit_removes_auto_labels_but_retains_manual_category_in_list(browser):
    headers = login(browser)
    doc = upload(browser, headers)
    assert change(browser, headers, doc, category='代数').status_code == 200
    with SessionLocal() as db:
        source = db.get(Document, doc['id'])
        source.tags_json = json.dumps({'knowledge_points': ['判别式'], 'question_types': ['计算题'], 'difficulty': '基础'})
        source.difficulty = '基础'
        db.commit()
    url = f"/api/docs/{doc['id']}/text"
    old = browser.get(url).json()['data']
    assert browser.put(url, json={'content': old['content'] + '补充正文后的自动标签需重新标注。', 'version': old['version']}, headers=headers).status_code == 200
    item = next(item for item in browser.get('/api/docs').json()['data'] if item['id'] == doc['id'])
    assert item['category'] == '代数'
    assert item['knowledge_points'] == [] and item['question_types'] == [] and item['difficulty'] is None


def change(browser, headers, doc, **values):
    body = {'filename': doc['filename'], 'category': doc['category'], 'version': doc['metadata_version'], **values}
    return browser.patch(f"/api/docs/{doc['id']}/metadata", json=body, headers=headers)


def test_rename_category_preserves_source_tags_and_updates_cached_retrieval(browser):
    headers = login(browser)
    doc = upload(browser, headers)
    with SessionLocal() as db:
        source = db.get(Document, doc['id'])
        path = Path(source.stored_path)
        raw = path.read_bytes()
        chunks = {row.id for row in db.query(Chunk).filter_by(doc_id=doc['id'])}
        source.tags_json = json.dumps({'knowledge_points': ['判别式']})
        source.difficulty = '基础'
        db.commit()
        cached = get_bm25_index(db, [doc['kb_id']])
    result = change(browser, headers, doc, filename='  方程讲义.txt  ', category='  代数  ')
    assert result.status_code == 200, result.text
    updated = next(row for row in browser.get('/api/docs').json()['data'] if row['id'] == doc['id'])
    assert updated['filename'] == '方程讲义.txt' and updated['category'] == '代数'
    assert updated['metadata_version'] != doc['metadata_version']
    assert path.read_bytes() == raw
    assert {item['id'] for item in get_store().snapshot_doc(doc['id'])} == chunks
    assert all(item['m']['doc_name'] == '方程讲义.txt' for item in get_store().snapshot_doc(doc['id']))
    with SessionLocal() as db:
        source = db.get(Document, doc['id'])
        assert source.stored_path == str(path)
        assert json.loads(source.tags_json)['knowledge_points'] == ['判别式']
        assert source.difficulty == '基础'
        assert get_bm25_index(db, [doc['kb_id']]) is not cached
        hits = retrieve(db, question='一元二次方程 判别式', kb_ids=[doc['kb_id']]).candidates
        assert hits and all(hit.doc_name == '方程讲义.txt' for hit in hits)
    assert change(browser, headers, doc, category='旧页面').status_code == 409
    assert change(browser, headers, updated).json()['data']['changed'] is False
    assert change(browser, headers, updated, category='').json()['data']['category'] == ''
    assert browser.delete(f"/api/docs/{doc['id']}", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.get(DocumentCategory, doc['id']) is None


@pytest.mark.parametrize('name', ['x.pdf', '../x.txt', 'bad?.txt', 'CON.txt', '   ', 'bad\nname.txt'])
def test_invalid_name_leaves_document_unchanged(browser, name):
    headers = login(browser)
    doc = upload(browser, headers)
    assert change(browser, headers, doc, filename=name).status_code == 400
    assert browser.get('/api/docs').json()['data'][0]['filename'] == doc['filename']


def test_duplicate_names_and_invalid_categories_never_overwrite(browser):
    headers = login(browser)
    doc = upload(browser, headers)
    other = upload(browser, headers, 'retained.txt')
    assert change(browser, headers, doc, filename=other['filename']).status_code == 409
    assert change(browser, headers, doc, category='x'*65).status_code == 400
    assert change(browser, headers, doc, category='a\nb').status_code == 400
    assert len(browser.get('/api/docs').json()['data']) == 2


def test_manual_category_survives_text_update_without_touching_auto_tags_on_classification(browser, monkeypatch):
    headers = login(browser)
    doc = upload(browser, headers)
    # A classification-only change must work without rewriting vectors.
    with monkeypatch.context() as patch:
        patch.setattr(get_store(), 'snapshot_doc', lambda doc_id: (_ for _ in ()).throw(AssertionError('unexpected vector rewrite')))
        assert change(browser, headers, doc, category='代数').status_code == 200
    text_url = f"/api/docs/{doc['id']}/text"
    old = browser.get(text_url).json()['data']
    response = browser.put(text_url, json={'content': old['content'] + '\n补充说明：根的和与积可以使用韦达定理进行验证。', 'version': old['version']}, headers=headers)
    assert response.status_code == 200, response.text
    assert browser.get('/api/docs').json()['data'][0]['category'] == '代数'


def test_auth_csrf_ownership_and_processing_guards(browser):
    owner = login(browser)
    doc = upload(browser, owner)
    assert change(browser, {}, doc, category='代数').status_code == 403
    with doc_service._INGEST_LOCK:
        assert change(browser, owner, doc, category='代数').status_code == 409
    with SessionLocal() as db:
        source = db.get(Document, doc['id'])
        source.status = 'parsing'
        db.commit()
    assert change(browser, owner, doc, category='代数').status_code == 409
    other = login(browser)
    assert change(browser, other, doc, category='代数').status_code == 403
    browser.cookies.clear()
    assert change(browser, owner, doc, category='代数').status_code == 401


def test_open_editor_reads_current_version_without_cached_list_metadata(browser):
    headers = login(browser)
    doc = upload(browser, headers)
    url = f"/api/docs/{doc['id']}/metadata"
    first = browser.get(url).json()['data']
    assert first['metadata_version'] == doc['metadata_version']
    assert change(browser, headers, doc, filename='new-name.txt', category='代数').status_code == 200
    fresh = browser.get(url).json()['data']
    assert fresh['filename'] == 'new-name.txt' and fresh['category'] == '代数'
    assert fresh['metadata_version'] != first['metadata_version']
    result = browser.patch(url, json={'filename': fresh['filename'], 'category': '微积分',
                                    'version': fresh['metadata_version']}, headers=headers)
    assert result.status_code == 200, result.text
    login(browser)
    assert browser.get(url).status_code == 403
    browser.cookies.clear()
    assert browser.get(url).status_code == 401


@pytest.mark.parametrize('failure', ['vector', 'database'])
def test_failed_rename_restores_names_categories_and_vectors(browser, monkeypatch, failure):
    headers = login(browser)
    doc = upload(browser, headers)
    store = get_store()
    before = store.snapshot_doc(doc['id'])
    target, name = (store, '_save') if failure == 'vector' else (Session, 'commit')
    original = getattr(target, name)
    calls = 0
    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('injected metadata failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, fail_once)
    response = change(browser, headers, doc, filename='new.txt', category='代数')
    assert response.status_code == 500, response.text
    assert store.snapshot_doc(doc['id']) == before
    assert browser.get('/api/docs').json()['data'][0] == doc
