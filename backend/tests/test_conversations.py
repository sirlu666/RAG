import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.chat import chat_stream
from app.api.schemas import ChatRequest
from app.core import auth
from app.db.chat_models import Conversation, Message, MessageState
from app.db.models import Document, User
from app.db.session import SessionLocal
from app.main import app
from app.rag.pipeline import RagPipeline
from app.services.conversation_activity import active_conversations


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()


def login(client):
    response = client.post('/api/auth/register', json={'username': 'history_' + uuid4().hex[:8], 'password': 'History-lesson-2026'})
    assert response.status_code == 200
    data = response.json()['data']
    return {'X-CSRF-Token': data['csrf_token']}, data['user']['id']


def conversation(client, headers):
    kb = client.post('/api/kbs', json={'name':'历史练习_' + uuid4().hex[:6]}, headers=headers).json()['data']['id']
    response = client.post('/api/chat/stream', json={'kb_ids':[kb], 'question':'求根公式'}, headers=headers)
    assert response.status_code == 200, response.text
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    return frames[0]['conversation_id'], kb


def test_list_reopen_followup_rename_and_delete_only_selected_conversation(browser):
    headers, _ = login(browser)
    cid, kb = conversation(browser, headers)
    other, _ = conversation(browser, headers)
    first_page = browser.get('/api/conversations?size=1&page=1').json()['data']
    second_page = browser.get('/api/conversations?size=1&page=2').json()['data']
    assert first_page['total'] == second_page['total'] == 2
    assert {first_page['items'][0]['id'], second_page['items'][0]['id']} == {cid, other}
    rows = browser.get('/api/conversations', params={'kb_id':kb}).json()['data']
    assert [item['id'] for item in rows['items']] == [cid]
    assert browser.get('/api/conversations', params={'kb_id':kb[:-1]}).json()['data']['items'] == []
    messages = browser.get(f'/api/conversations/{cid}/messages').json()['data']['items']
    assert [item['role'] for item in messages] == ['user', 'assistant']
    assert messages[-1]['status'] == 'done' and messages[-1]['refused'] is True
    assert browser.post('/api/chat/stream', json={'kb_ids':[kb], 'question':'第二步为什么这样？', 'conversation_id':cid}, headers=headers).status_code == 200
    assert len(browser.get(f'/api/conversations/{cid}/messages').json()['data']['items']) == 4
    assert browser.patch(f'/api/conversations/{cid}', json={'title':'  我的方程练习  '}, headers=headers).json()['data']['title'] == '我的方程练习'
    assert browser.get('/api/conversations').json()['data']['items'][0]['title'] == '我的方程练习'
    # A document in the same KB must survive conversation deletion.
    uploaded = browser.post('/api/docs/upload', data={'kb_id':kb}, files={'file':('kept.txt', ('一元二次方程的判别式用于判断实数根的数量。' * 4).encode(), 'text/plain')}, headers=headers).json()['data']['doc_id']
    assert browser.delete(f'/api/conversations/{cid}', headers=headers).status_code == 200
    assert browser.get(f'/api/conversations/{cid}/messages').status_code == 404
    assert browser.get(f'/api/conversations/{other}/messages').status_code == 200
    assert browser.get(f'/api/docs/{uploaded}/preview').status_code == 200
    with SessionLocal() as db:
        assert db.query(Message).filter(Message.conversation_id == cid).count() == 0
        assert db.query(MessageState).count() >= 1  # The other conversation remains.
        assert db.get(Document, uploaded)


def test_history_isolation_csrf_and_validation(browser):
    headers, _ = login(browser)
    cid, _ = conversation(browser, headers)
    assert browser.patch(f'/api/conversations/{cid}', json={'title':'no csrf'}).status_code == 403
    assert browser.delete(f'/api/conversations/{cid}').status_code == 403
    for title in ('   ', 'x'*121):
        assert browser.patch(f'/api/conversations/{cid}', json={'title':title}, headers=headers).status_code == 400
    second_headers, _ = login(browser)
    assert browser.get('/api/conversations').json()['data']['items'] == []
    assert browser.get(f'/api/conversations/{cid}/messages').status_code == 403
    assert browser.patch(f'/api/conversations/{cid}', json={'title':'other'}, headers=second_headers).status_code == 403
    assert browser.delete(f'/api/conversations/{cid}', headers=second_headers).status_code == 403
    assert browser.get('/api/conversations/c_missing/messages').status_code == 404
    browser.cookies.clear()
    assert browser.get('/api/conversations').status_code == 401
    assert browser.get(f'/api/conversations/{cid}/messages').status_code == 401


def test_cursor_is_stable_with_equal_timestamps_and_new_messages(browser):
    headers, user_id = login(browser)
    stamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    suffix = uuid4().hex[:8]
    cid = 'cursor_' + suffix
    with SessionLocal() as db:
        db.add(Conversation(id=cid, user_id=user_id, title='游标', kb_ids='[]'))
        db.flush()
        db.add_all([Message(id=f'{suffix}_{i}', conversation_id=cid, role='user', content=str(i), created_at=stamp) for i in range(3)])
        db.commit()
    page = browser.get(f'/api/conversations/{cid}/messages?size=1').json()['data']
    assert page['items'][0]['content'] == '2' and page['has_more']
    with SessionLocal() as db:
        db.add(Message(id=f'{suffix}_3', conversation_id=cid, role='user', content='new', created_at=stamp))
        db.commit()
    second = browser.get(f'/api/conversations/{cid}/messages', params={'size':1,'before_id':page['next_before_id']}).json()['data']
    assert second['items'][0]['content'] == '1'
    third = browser.get(f'/api/conversations/{cid}/messages', params={'size':1,'before_id':second['next_before_id']}).json()['data']
    assert third['items'][0]['content'] == '0' and not third['has_more']
    assert browser.get(f'/api/conversations/{cid}/messages?before_id=not_a_message').status_code == 400
    assert browser.get('/api/conversations?size=1&page=0').status_code == 400


def test_active_conversation_cannot_be_deleted_or_generate_twice(browser):
    headers, _ = login(browser)
    cid, kb = conversation(browser, headers)
    active_conversations.add(cid)
    try:
        assert browser.delete(f'/api/conversations/{cid}', headers=headers).status_code == 409
        assert browser.post('/api/chat/stream', json={'kb_ids':[kb], 'question':'重复生成', 'conversation_id':cid}, headers=headers).status_code == 409
    finally:
        active_conversations.discard(cid)
    assert browser.get(f'/api/conversations/{cid}/messages').status_code == 200


def test_canonical_done_text_and_status_survive_reload(browser, monkeypatch):
    headers, _ = login(browser)
    async def fake_run(self, **kwargs):
        yield {'event':'meta','data':{'conversation_id':kwargs['conversation_id'], 'message_id':kwargs['message_id']}}
        yield {'event':'delta','data':{'text':'未经修正 [9]'}}
        yield {'event':'done','data':{'answer':'已修正 [1]', 'citations':[], 'model':'mock', 'refused':False}}
    monkeypatch.setattr(RagPipeline, 'run', fake_run)
    cid, _ = conversation(browser, headers)
    rows = browser.get(f'/api/conversations/{cid}/messages').json()['data']['items']
    assert rows[-1]['content'] == '已修正 [1]'
    assert rows[-1]['status'] == 'done' and rows[-1]['model'] == 'mock'


def test_interrupted_generation_records_partial_state(browser, monkeypatch):
    headers, user_id = login(browser)
    kb = browser.post('/api/kbs', json={'name':'中断练习'}, headers=headers).json()['data']['id']
    async def fake_run(self, **kwargs):
        yield {'event':'meta','data':{'conversation_id':kwargs['conversation_id'], 'message_id':kwargs['message_id']}}
        yield {'event':'delta','data':{'text':'部分回答'}}
        yield {'event':'done','data':{'answer':'不应到达'}}
    monkeypatch.setattr(RagPipeline, 'run', fake_run)
    async def interrupt():
        with SessionLocal() as db:
            response = await chat_stream(ChatRequest(kb_ids=[kb], question='模拟停止'), db=db, user=db.get(User, user_id))
            iterator = response.body_iterator
            meta = await anext(iterator)
            cid = json.loads(meta.split('data: ', 1)[1].strip())['conversation_id']
            await anext(iterator)
            await iterator.aclose()
            return cid
    cid = asyncio.run(interrupt())
    rows = browser.get(f'/api/conversations/{cid}/messages').json()['data']['items']
    assert rows[-1]['content'] == '部分回答' and rows[-1]['status'] == 'stopped'
    assert rows[-1]['model'] == 'mock'
    assert cid not in active_conversations


def test_failed_partial_answer_stays_failed_in_history(browser, monkeypatch):
    headers, _ = login(browser)
    async def fake_run(self, **kwargs):
        yield {'event':'meta','data':{'conversation_id':kwargs['conversation_id'], 'message_id':kwargs['message_id']}}
        yield {'event':'delta','data':{'text':'失败前收到的内容'}}
        yield {'event':'error','data':{'code':4001, 'message':'模型临时失败'}}
    monkeypatch.setattr(RagPipeline, 'run', fake_run)
    cid, _ = conversation(browser, headers)
    rows = browser.get(f'/api/conversations/{cid}/messages').json()['data']['items']
    assert rows[-1]['status'] == 'failed'
    assert rows[-1]['content'] == '失败前收到的内容'
    assert cid not in active_conversations
