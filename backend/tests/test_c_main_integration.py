"""A/B changes combined with C cookie auth, mutation locks and message state."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.api import chat
from app.core.exceptions import AppError
from app.db.chat_models import Message, MessageState
from app.db.models import Chunk, Document, DocumentCategory, DocumentOcrText
from app.db.session import SessionLocal
from app.main import app
from app.rag.vectorstore import get_store
from app.services import doc_service, document_text
from app.services.parsing import recognize


@pytest.fixture
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        data=client.post('/api/auth/register',json={
            'username':'merge_'+uuid4().hex[:10],'password':'Integration-2026-good',
        }).json()['data']
        yield client,{'X-CSRF-Token':data['csrf_token']}
    auth._attempts.clear()


def upload(client,headers,raw=None,kb=None,overwrite=False):
    raw=raw or ('定义：增函数在定义域区间内满足自变量增大时函数值也增大。'*5).encode()
    data={'overwrite':str(overwrite).lower()}
    if kb:data['kb_id']=kb
    response=client.post('/api/docs/upload',headers=headers,data=data,
                         files={'file':('integration.txt',raw,'text/plain')})
    assert response.status_code==200,response.text
    return response.json()['data']['doc_id']


def test_b_question_image_uses_real_c_session_and_csrf(browser,monkeypatch):
    client,headers=browser
    seen=[]
    def fake(filename,raw):
        seen.append((filename,raw))
        return {'text':'求极限 sin x/x','latex':'','warnings':[]}
    monkeypatch.setattr(recognize,'recognize_question_image',fake)
    payload={'file':('q.png',b'fixture','image/png')}
    with SessionLocal() as db: before=db.query(Document).count()
    assert client.post('/api/chat/image/recognize',files=payload).status_code==403
    result=client.post('/api/chat/image/recognize',headers=headers,files=payload)
    assert result.status_code==200 and result.json()['data']['text']=='求极限 sin x/x'
    assert seen==[('q.png',b'fixture')]
    client.cookies.clear()
    assert client.post('/api/chat/image/recognize',headers=headers,files=payload).status_code==401
    with SessionLocal() as db: assert db.query(Document).count()==before


def test_successful_overwrite_cleans_c_metadata_without_relocking(browser):
    client,headers=browser
    old_id=upload(client,headers)
    with SessionLocal() as db:
        old=db.get(Document,old_id);kb=old.kb_id;stored=Path(old.stored_path)
        old_chunks={c.id for c in db.query(Chunk).filter_by(doc_id=old_id)}
        db.add(DocumentCategory(doc_id=old_id,category='练习',revision='old'))
        db.add(DocumentOcrText(doc_id=old_id,source_hash=old.content_hash,content='old'))
        db.commit()
    new_id=upload(client,headers,('定义：减函数在区间上随着自变量增大而减小。'*6).encode(),kb,True)
    with SessionLocal() as db:
        assert db.get(Document,old_id) is None
        assert db.get(DocumentCategory,old_id) is None
        assert db.get(DocumentOcrText,old_id) is None
        new=db.get(Document,new_id)
        assert new.status=='ready' and not new.error_msg
    assert not stored.exists() and not (old_chunks & get_store().ids())


def test_pending_reindex_keeps_old_index_and_blocks_another_mutation(browser):
    client,headers=browser;doc_id=upload(client,headers)
    before=get_store().snapshot_doc(doc_id)
    with SessionLocal() as db:
        doc=db.get(Document,doc_id)
        doc_service.reindex(db,doc)
        assert doc.status=='ready'
        with pytest.raises(AppError) as error:doc_service.reindex(db,doc)
        assert error.value.code==1005
        with pytest.raises(AppError):doc_service.delete_document(db,doc)
    assert get_store().snapshot_doc(doc_id)==before
    assert client.get(f'/api/docs/{doc_id}/preview').status_code==200
    doc_service.run_ingest(doc_id)
    assert client.get(f'/api/docs/{doc_id}/status').json()['data']['status']=='ready'


@pytest.mark.parametrize('stream',[False,True])
def test_related_results_and_c_completion_state_are_both_persisted(browser,stream):
    client,headers=browser;doc_id=upload(client,headers)
    with SessionLocal() as db:kb=db.get(Document,doc_id).kb_id
    response=client.post('/api/chat/stream',headers=headers,json={
        'kb_ids':[kb],'question':'增函数的定义是什么','stream':stream,
    })
    assert response.status_code==200,response.text
    if stream:
        events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        conv=events[0]['conversation_id'];done=events[-1]
    else:
        done=response.json()['data'];conv=done['conversation_id']
    with SessionLocal() as db:
        message=db.query(Message).filter_by(conversation_id=conv,role='assistant').one()
        assert db.get(MessageState,message.id).status=='done'
        related=json.loads(message.related)
        assert related['questions']==done['related_questions'] and related['questions']
        assert related['materials']==done['related_materials']


def test_coarse_clock_preserves_question_then_failed_answer_order(browser,monkeypatch):
    client,headers=browser;doc_id=upload(client,headers)
    with SessionLocal() as db:kb=db.get(Document,doc_id).kb_id
    frozen=datetime(2026,10,28,tzinfo=timezone.utc)
    monkeypatch.setattr(chat,'utcnow',lambda:frozen)
    async def partial(self,**kwargs):
        yield {'event':'meta','data':{'conversation_id':kwargs['conversation_id']}}
        yield {'event':'delta','data':{'text':'失败前的正文'}}
        yield {'event':'error','data':{'code':4001,'message':'模拟中断'}}
    monkeypatch.setattr(chat.RagPipeline,'run',partial)
    response=client.post('/api/chat/stream',headers=headers,json={
        'kb_ids':[kb],'question':'增函数是什么',
    })
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    cid=events[0]['conversation_id']
    messages=client.get(f'/api/conversations/{cid}/messages').json()['data']['items']
    assert [m['role'] for m in messages]==['user','assistant']
    assert messages[-1]['status']=='failed' and messages[-1]['content']=='失败前的正文'
    assert messages[0]['created_at'] < messages[1]['created_at']


@pytest.mark.parametrize('permanent',[False,True])
def test_windows_sharing_retry_is_bounded_and_keeps_original_until_success(tmp_path,monkeypatch,permanent):
    path=tmp_path/'original.docx';path.write_bytes(b'old')
    staged=tmp_path/'new.tmp';staged.write_bytes(b'new')
    replace=Path.replace;calls=[]
    def held(source,target):
        calls.append(source)
        if permanent or len(calls)<3:
            assert path.read_bytes()==b'old'
            exc=PermissionError('isolated Windows sharing violation');exc.winerror=32
            raise exc
        return replace(source,target)
    monkeypatch.setattr(Path,'replace',held)
    monkeypatch.setattr(document_text.time,'sleep',lambda delay:None)
    if permanent:
        with pytest.raises(AppError) as error:document_text._replace_staged(staged,path)
        assert error.value.code==1005 and len(calls)==5
        assert path.read_bytes()==b'old' and staged.read_bytes()==b'new'
    else:
        document_text._replace_staged(staged,path)
        assert len(calls)==3 and path.read_bytes()==b'new' and not staged.exists()
