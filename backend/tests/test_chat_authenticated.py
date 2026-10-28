"""Exercise the existing B stream using C's real cookie + CSRF, not dev headers."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core import auth
from app.main import app


def register(client):
    response = client.post('/api/auth/register', json={
        'username': 'chat_' + uuid4().hex[:10], 'password': 'Chat-learning-2026',
    })
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json()['data']['csrf_token']}


def events(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


def test_real_session_upload_stream_followup_and_citation_preview():
    auth._attempts.clear()
    with TestClient(app) as client:
        headers = register(client)
        kb = client.post('/api/kbs', json={'name': '方程练习'}, headers=headers).json()['data']['id']
        content = '# 一元二次方程\n\n方程 ax^2+bx+c=0 的判别式是 b^2-4ac。例题：解方程 x^2-3x+2=0。解：因式分解得 (x-1)(x-2)=0，所以 x=1 或 x=2。'
        doc = client.post('/api/docs/upload', data={'kb_id': kb}, files={'file': ('方程.txt', content.encode(), 'text/plain')}, headers=headers)
        assert doc.status_code == 200
        result = events(client.post('/api/chat/stream', json={'kb_ids': [kb], 'question': '解方程 x^2-3x+2=0'}, headers=headers))
        assert result[0]['conversation_id']
        citation = next(item for item in result if 'chunk_id' in item)
        preview = client.get(f"/api/docs/{citation['doc_id']}/preview?page={citation['seq']//5+1}&size=5").json()['data']
        assert any(item['id'] == citation['chunk_id'] for item in preview['items'])
        assert result[-1]['model'] == 'mock'
        assert result[-1]['answer']
        followup = events(client.post('/api/chat/stream', json={
            'kb_ids': [kb], 'question': '为什么可以因式分解？', 'conversation_id': result[0]['conversation_id'],
        }, headers=headers))
        assert followup[0]['conversation_id'] == result[0]['conversation_id']
        assert client.post('/api/chat/stream', json={'kb_ids': [kb], 'question': '求根'}).status_code == 403
        other_headers = register(client)
        assert client.post('/api/chat/stream', json={'kb_ids': [kb], 'question': '求根'}, headers=other_headers).status_code == 403
        other_kb = client.post('/api/kbs', json={'name': '另一个账号'}, headers=other_headers).json()['data']['id']
        assert client.post('/api/chat/stream', json={
            'kb_ids': [other_kb], 'question': '求根', 'conversation_id': result[0]['conversation_id'],
        }, headers=other_headers).status_code == 403
    auth._attempts.clear()
