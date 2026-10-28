import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.chat_models import Conversation, Message, MessageState
from app.db.session import SessionLocal
from app.main import app
from app.rag.context import load_related


def test_related_parser_handles_legacy_and_invalid_json_shapes():
    for raw in (None, '', 'bad', '[]', 'null', '1', '{"questions": 1, "materials": null}'):
        assert load_related(raw) == {"questions": [], "materials": []}


def test_history_serializes_stored_related_without_schema_migration():
    with TestClient(app) as client:
        data = client.post('/api/auth/register', json={
            'username': 'related_' + uuid4().hex[:8], 'password': 'Related-test-2026',
        }).json()['data']
        cid = 'related_' + uuid4().hex
        related = {'questions': ['如何验证？'], 'materials': [{'doc_id': 'd1', 'chunk_id': 'c1', 'seq': 6}]}
        with SessionLocal() as db:
            db.add(Conversation(id=cid, user_id=data['user']['id'], kb_ids='[]', title='推荐历史'))
            db.flush()
            db.add(Message(id=cid + '_a', conversation_id=cid, role='assistant', content='答案', related=json.dumps(related)))
            db.flush()
            db.add(MessageState(message_id=cid + '_a', status='done', details='{}'))
            db.commit()
        response = client.get(f'/api/conversations/{cid}/messages')
        assert response.status_code == 200
        item = response.json()['data']['items'][0]
        assert item['related_questions'] == related['questions']
        assert item['related_materials'] == related['materials']
