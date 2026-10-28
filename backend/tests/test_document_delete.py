"""Authenticated deletion, index cleanup and ingestion conflict protection."""
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.db.models import Chunk, Document, IngestTask
from app.db.session import SessionLocal
from app.main import app
from app.rag.vectorstore import get_store
from app.services import doc_service


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    data = browser.post('/api/auth/register', json={
        'username': 'del_' + uuid4().hex[:10], 'password': 'Document-learning-2026',
    }).json()['data']
    return {'X-CSRF-Token': data['csrf_token']}


def upload(browser, headers):
    text = '一元二次方程的判别式用于判断实数根的个数。例题：方程 x^2-3x+2=0 的根是 1 和 2，因式分解得到 (x-1)(x-2)=0。' + uuid4().hex
    response = browser.post('/api/docs/upload', files={
        'file': ('delete-practice.txt', text.encode('utf-8'), 'text/plain'),
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['data']['doc_id']


def test_delete_cleans_only_target_file_chunks_tasks_and_vectors(browser):
    headers = login(browser)
    target = upload(browser, headers)
    retained = upload(browser, headers)
    with SessionLocal() as db:
        stored = Path(db.get(Document, target).stored_path)
        chunks = {row.id for row in db.query(Chunk).filter_by(doc_id=target)}
    assert stored.exists() and chunks
    assert chunks <= get_store().ids()
    assert browser.delete(f'/api/docs/{target}', headers=headers).status_code == 200
    assert not stored.exists()
    assert not (chunks & get_store().ids())
    with SessionLocal() as db:
        assert db.get(Document, target) is None
        assert db.query(Chunk).filter_by(doc_id=target).count() == 0
        assert db.query(IngestTask).filter_by(doc_id=target).count() == 0
        assert db.get(Document, retained).status == 'ready'
    assert browser.get(f'/api/docs/{retained}/preview').status_code == 200
    assert browser.delete(f'/api/docs/{target}', headers=headers).status_code == 404


def test_delete_requires_login_csrf_and_ownership(browser):
    owner = login(browser)
    target = upload(browser, owner)
    assert browser.delete(f'/api/docs/{target}').status_code == 403
    other = login(browser)
    assert browser.delete(f'/api/docs/{target}', headers=other).status_code == 403
    browser.cookies.clear()
    assert browser.delete(f'/api/docs/{target}', headers=owner).status_code == 401
    with SessionLocal() as db:
        assert db.get(Document, target).status == 'ready'


@pytest.mark.parametrize('status', ['pending', 'parsing', 'embedding'])
def test_processing_document_cannot_be_deleted(browser, status):
    headers = login(browser)
    target = upload(browser, headers)
    with SessionLocal() as db:
        doc = db.get(Document, target)
        doc.status = status
        stored = Path(doc.stored_path)
        db.commit()
    before = get_store().ids()
    assert browser.delete(f'/api/docs/{target}', headers=headers).status_code == 409
    assert stored.exists() and get_store().ids() == before


def test_ingestion_lock_blocks_delete_and_reindex_without_changes(browser):
    headers = login(browser)
    target = upload(browser, headers)
    before = get_store().ids()
    with doc_service._INGEST_LOCK:
        assert browser.delete(f'/api/docs/{target}', headers=headers).status_code == 409
        assert browser.post(f'/api/docs/{target}/reindex', headers=headers).status_code == 409
    assert get_store().ids() == before
    assert browser.get(f'/api/docs/{target}/preview').status_code == 200
