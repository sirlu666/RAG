"""Guest/source boundaries are enforced by the backend, not just hidden in the UI."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import public
from app.core import auth
from app.db.chat_models import Conversation, Message
from app.db.models import KnowledgeBase, PublishedKnowledgeBase
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture()
def browser():
    auth._attempts.clear()
    public._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()
    public._attempts.clear()


def login(browser):
    data = browser.post('/api/auth/register', json={'username': 'pub_' + uuid4().hex[:10],
        'password': 'Public-learning-2026'}).json()['data']
    return {'X-CSRF-Token': data['csrf_token']}


def create(browser, headers, name='公开练习'):
    return browser.post('/api/kbs', json={'name': name}, headers=headers).json()['data']


def publish(browser, headers, kb, enabled=True):
    return browser.put(f"/api/kbs/{kb['id']}/visibility", json={'public': enabled}, headers=headers)


def upload(browser, headers, kb):
    text = '一元二次方程 ax^2+bx+c=0，其中 a 不等于零。判别式大于零时有两个不同的实根。例题：x^2-3x+2=0，可分解成 (x-1)(x-2)=0。' + uuid4().hex
    response = browser.post('/api/docs/upload', data={'kb_id': kb['id']},
        files={'file': ('source.txt', text.encode('utf-8'), 'text/plain')}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['data']['doc_id']


def ask(browser, kb, **extra):
    return browser.post('/api/public/chat/stream', json={'kb_ids': [kb['id']], 'question': '解方程 x^2-3x+2=0', **extra})


def frames(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_publication_is_explicit_owner_only_and_can_be_revoked(browser):
    owner = login(browser)
    kb = create(browser, owner)
    assert kb['is_public'] is False
    assert all(item['id'] != kb['id'] for item in browser.get('/api/public/kbs').json()['data'])
    assert publish(browser, {}, kb).status_code == 403
    assert publish(browser, owner, kb).status_code == 200
    assert browser.get(f"/api/kbs/{kb['id']}").json()['data']['is_public'] is True
    assert next(item for item in browser.get('/api/public/kbs').json()['data'] if item['id'] == kb['id']) == {'id': kb['id'], 'name': kb['name']}
    other = login(browser)
    assert publish(browser, other, kb, False).status_code == 403
    browser.cookies.clear()
    assert publish(browser, owner, kb, False).status_code == 401
    # A new owned KB can be published, unpublished and removed without touching others.
    fresh_headers = login(browser)
    fresh = create(browser, fresh_headers)
    assert publish(browser, fresh_headers, fresh).status_code == 200
    assert publish(browser, fresh_headers, fresh, False).status_code == 200
    assert publish(browser, fresh_headers, fresh).status_code == 200
    assert browser.delete(f"/api/kbs/{fresh['id']}", headers=fresh_headers).status_code == 200
    with SessionLocal() as db:
        assert db.get(PublishedKnowledgeBase, fresh['id']) is None
        assert db.get(KnowledgeBase, kb['id']) is not None


def test_guest_answer_has_no_sources_or_saved_history_and_private_ids_are_rejected(browser):
    headers = login(browser)
    kb = create(browser, headers)
    doc_id = upload(browser, headers, kb)
    private = create(browser, headers, '私人资料')
    assert publish(browser, headers, kb).status_code == 200
    with SessionLocal() as db:
        counts = db.query(Conversation).count(), db.query(Message).count()
    browser.cookies.clear()
    response = ask(browser, kb)
    assert response.status_code == 200 and 'text/event-stream' in response.headers['content-type']
    assert 'event: delta' in response.text and 'event: done' in response.text
    assert 'event: citation' not in response.text
    assert doc_id not in response.text and 'source.txt' not in response.text
    assert all('snippet' not in value and 'doc_id' not in value and 'chunk_id' not in value for value in frames(response))
    assert frames(response)[-1]['citations'] == []
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 401
    assert browser.get('/api/docs').status_code == 401
    assert browser.get('/api/conversations').status_code == 401
    assert browser.post('/api/chat/stream', json={'kb_ids': [kb['id']], 'question': '问题'}).status_code == 401
    assert ask(browser, private).status_code == 403
    assert ask(browser, kb, kb_ids=[kb['id'], private['id']]).status_code == 403
    assert ask(browser, kb, conversation_id='stolen').status_code == 400
    assert ask(browser, kb, include_citations=True).status_code == 400
    with SessionLocal() as db:
        assert counts == (db.query(Conversation).count(), db.query(Message).count())


def test_logged_reader_can_ask_and_view_public_sources_but_cannot_manage_them(browser):
    owner = login(browser)
    kb = create(browser, owner)
    doc_id = upload(browser, owner, kb)
    private = create(browser, owner, '私人资料')
    private_doc = upload(browser, owner, private)
    assert publish(browser, owner, kb).status_code == 200
    reader = login(browser)
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 200
    assert browser.get(f'/api/docs/{private_doc}/preview').status_code == 403
    assert browser.get('/api/kbs').json()['data'] == []
    assert browser.get('/api/docs').json()['data'] == []
    response = browser.post('/api/chat/stream', json={'kb_ids': [kb['id']], 'question': '方程求根'}, headers=reader)
    assert response.status_code == 200 and 'event: citation' in response.text
    assert browser.delete(f'/api/docs/{doc_id}', headers=reader).status_code == 403
    assert browser.post(f'/api/docs/{doc_id}/reindex', headers=reader).status_code == 403
    assert publish(browser, reader, kb, False).status_code == 403
    # Revoke via the owning session; other readers immediately lose source access.
    owner_client = TestClient(app)
    # Restore owner's cookie without exposing a token in test output.
    # The owner can sign in using its known test username.
    with SessionLocal() as db:
        from app.db.models import User
        username = db.get(User, db.get(KnowledgeBase, kb['id']).user_id).username
    signed = owner_client.post('/api/auth/login', json={'username': username, 'password': 'Public-learning-2026'}).json()['data']
    assert publish(owner_client, {'X-CSRF-Token': signed['csrf_token']}, kb, False).status_code == 200
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 403
    assert browser.post('/api/chat/stream', json={'kb_ids': [kb['id']], 'question': '问题'}, headers=reader).status_code == 403
    assert ask(browser, kb).status_code == 403
    owner_client.close()


def test_guest_payload_whitelist_and_refusal_text_are_preserved(browser, monkeypatch):
    owner = login(browser)
    kb = create(browser, owner)
    publish(browser, owner, kb)
    browser.cookies.clear()
    async def fake_run(self, **values):
        assert values['kb_ids'] == [kb['id']] and values['history'] == []
        yield {'event': 'meta', 'data': {'conversation_id': 'internal', 'secret': 'hidden-meta'}}
        yield {'event': 'citation', 'data': {'snippet': 'hidden-snippet', 'doc_id': 'hidden-doc'}}
        yield {'event': 'delta', 'data': {'text': '未找到依据'}}
        yield {'event': 'done', 'data': {'refused': True, 'citations': [{'snippet': 'hidden-snippet'}], 'extra': 'hidden-done'}}
    monkeypatch.setattr(public.RagPipeline, 'run', fake_run)
    response = ask(browser, kb)
    assert 'hidden-' not in response.text and 'internal' not in response.text
    assert frames(response)[-1]['answer'] == '未找到依据'


def test_guest_rate_origin_and_schema_guards(browser, monkeypatch):
    owner = login(browser)
    kb = create(browser, owner)
    publish(browser, owner, kb)
    browser.cookies.clear()
    async def fake_run(self, **values):
        yield {'event': 'done', 'data': {'answer': '完成'}}
    monkeypatch.setattr(public.RagPipeline, 'run', fake_run)
    assert browser.post('/api/public/chat/stream', json={'kb_ids': [kb['id']], 'question': '问题'}, headers={'Origin': 'https://unknown.example'}).status_code == 403
    assert ask(browser, kb, question='   ').status_code == 400
    assert ask(browser, kb, stream=False).status_code == 400
    for _ in range(10):
        assert ask(browser, kb).status_code == 200
    assert ask(browser, kb).status_code == 429
