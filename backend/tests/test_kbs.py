"""Real authenticated KB CRUD, ownership and non-destructive deletion."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.db.models import Document, KnowledgeBase
from app.db.session import SessionLocal
from app.main import app
from app.rag.vectorstore import get_store


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()


def sign_in(browser):
    response = browser.post('/api/auth/register', json={
        'username': 'kb_' + uuid4().hex[:10], 'password': 'KB-learning-2026',
    })
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json()['data']['csrf_token']}


def create(browser, headers, name='高等数学'):
    response = browser.post('/api/kbs', json={'name': name}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_create_read_rename_delete_persist(browser):
    headers = sign_in(browser)
    assert browser.get('/api/kbs').json()['data'] == []
    kb = create(browser, headers, '  高等数学  ')
    assert kb['name'] == '高等数学' and kb['document_count'] == 0
    assert browser.get('/api/kbs').json()['data'] == [kb]
    assert browser.get(f"/api/kbs/{kb['id']}").json()['data'] == kb
    renamed = browser.patch(f"/api/kbs/{kb['id']}", json={'name':'微积分'}, headers=headers)
    assert renamed.json()['data']['name'] == '微积分'
    assert browser.get('/api/kbs').json()['data'][0]['name'] == '微积分'
    assert browser.delete(f"/api/kbs/{kb['id']}", headers=headers).status_code == 200
    assert browser.get(f"/api/kbs/{kb['id']}").status_code == 404
    assert browser.get('/api/kbs').json()['data'] == []


def test_name_conflicts_do_not_erase_existing_data(browser):
    headers = sign_in(browser)
    first = create(browser, headers)
    second = create(browser, headers, '线性代数')
    assert browser.post('/api/kbs', json={'name':'高等数学'}, headers=headers).status_code == 409
    assert browser.patch(f"/api/kbs/{second['id']}", json={'name':'高等数学'}, headers=headers).status_code == 409
    assert browser.get(f"/api/kbs/{second['id']}").json()['data']['name'] == '线性代数'
    assert browser.patch(f"/api/kbs/{first['id']}", json={'name':'高等数学'}, headers=headers).status_code == 200


@pytest.mark.parametrize('name', ['', '   ', 'x'*65])
def test_invalid_names(browser, name):
    headers = sign_in(browser)
    assert browser.post('/api/kbs', json={'name': name}, headers=headers).status_code == 400
    assert browser.get('/api/kbs').json()['data'] == []


def test_other_accounts_cannot_list_read_rename_or_delete(browser):
    owner_headers = sign_in(browser)
    kb = create(browser, owner_headers)
    other_headers = sign_in(browser)
    assert browser.get('/api/kbs').json()['data'] == []
    assert browser.get(f"/api/kbs/{kb['id']}").status_code == 403
    assert browser.patch(f"/api/kbs/{kb['id']}", json={'name':'stolen'}, headers=other_headers).status_code == 403
    assert browser.delete(f"/api/kbs/{kb['id']}", headers=other_headers).status_code == 403
    # Same names are allowed for different owners.
    create(browser, other_headers)
    with SessionLocal() as db:
        assert db.get(KnowledgeBase, kb['id']).name == '高等数学'


@pytest.mark.parametrize('method,path', [
    ('GET','/api/kbs'), ('POST','/api/kbs'), ('GET','/api/kbs/kb_missing'),
    ('PATCH','/api/kbs/kb_missing'), ('DELETE','/api/kbs/kb_missing'),
])
def test_unauthenticated_requests_are_rejected(browser, method, path):
    response = browser.request(method, path, json={'name':'未登录'}, headers={'Authorization':'Bearer dev'})
    assert response.status_code == 401


def test_mutations_require_csrf_and_missing_ids_are_not_created(browser):
    headers = sign_in(browser)
    kb = create(browser, headers)
    assert browser.post('/api/kbs', json={'name':'无校验'}).status_code == 403
    assert browser.patch(f"/api/kbs/{kb['id']}", json={'name':'无校验'}).status_code == 403
    assert browser.delete(f"/api/kbs/{kb['id']}").status_code == 403
    assert browser.get('/api/kbs/kb_missing').status_code == 404
    assert browser.patch('/api/kbs/kb_missing', json={'name':'不存在'}, headers=headers).status_code == 404
    assert browser.delete('/api/kbs/kb_missing', headers=headers).status_code == 404


def test_nonempty_kb_refuses_deletion_and_retains_documents_and_vectors(browser):
    headers = sign_in(browser)
    kb = create(browser, headers)
    content = ('高等数学中，函数的导数用于描述变化率，定积分用于求曲线下的面积。'
               '例题：函数 f(x)=x^2 的导数为 2x，可用于判断区间上的单调性。')
    uploaded = browser.post('/api/docs/upload', data={'kb_id':kb['id']},
                            files={'file':('kb-retained.txt', content.encode('utf-8'),'text/plain')}, headers=headers)
    assert uploaded.status_code == 200
    doc_id = uploaded.json()['data']['doc_id']
    assert browser.get(f'/api/docs/{doc_id}/status').json()['data']['status'] == 'ready'
    assert browser.get('/api/kbs').json()['data'][0]['document_count'] == 1
    before_vectors = get_store().count()
    with SessionLocal() as db:
        stored = Path(db.get(Document, doc_id).stored_path)
    assert stored.exists()
    assert browser.delete(f"/api/kbs/{kb['id']}", headers=headers).status_code == 409
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 200
    assert stored.exists() and get_store().count() == before_vectors
    # Renaming changes only the KB name, not source ownership or vector data.
    assert browser.patch(f"/api/kbs/{kb['id']}", json={'name':'微积分'}, headers=headers).status_code == 200
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 200
    assert get_store().count() == before_vectors
    # After explicit document deletion the now-empty KB can be removed.
    assert browser.delete(f'/api/docs/{doc_id}', headers=headers).status_code == 200
    assert browser.delete(f"/api/kbs/{kb['id']}", headers=headers).status_code == 200
