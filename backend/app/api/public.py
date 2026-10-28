"""Stateless guest QA: published KBs only, no citation/source/history API access."""
import logging
import re
import time
from collections import deque
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.chat import _sse, SSE_HEADERS
from app.core.auth import check_origin
from app.core.exceptions import AppError, ok
from app.db.models import KnowledgeBase, PublishedKnowledgeBase, new_id
from app.db.session import get_db, SessionLocal
from app.rag.pipeline import RagPipeline

router = APIRouter(prefix='/api/public', tags=['public'])
logger = logging.getLogger('mathrag.public')
_attempts = {}
_rate_lock = Lock()


class GuestQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kb_ids: list[str] = Field(min_length=1, max_length=5)
    question: str = Field(min_length=1, max_length=2000)
    stream: Literal[True] = True

    @field_validator('question', mode='before')
    @classmethod
    def trim_question(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.get('/kbs', summary='公开知识库目录（不含文档或引用正文）')
def public_kbs(db: Session = Depends(get_db)):
    rows = db.query(KnowledgeBase).join(PublishedKnowledgeBase,
        PublishedKnowledgeBase.kb_id == KnowledgeBase.id).order_by(KnowledgeBase.name, KnowledgeBase.id).all()
    return ok([{'id': row.id, 'name': row.name} for row in rows])


def check_rate(request):
    host = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with _rate_lock:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] <= now - 60:
                del _attempts[key]
        timestamps = _attempts.setdefault(host, deque())
        while timestamps and timestamps[0] <= now - 60:
            timestamps.popleft()
        if len(timestamps) >= 10:
            raise AppError(3001, '游客每分钟最多提问 10 次，请稍后再试')
        timestamps.append(now)


@router.post('/chat/stream', summary='游客公共资料问答（不保存历史，不返回引用）',
             responses={200: {'content': {'text/event-stream': {'schema': {'type': 'string'}}}}})
async def guest_chat(body: GuestQuestion, request: Request, db: Session = Depends(get_db)):
    check_origin(request)
    check_rate(request)
    kb_ids = list(dict.fromkeys(body.kb_ids))
    published = {row.kb_id for row in db.query(PublishedKnowledgeBase).filter(PublishedKnowledgeBase.kb_id.in_(kb_ids)).all()}
    if set(kb_ids) != published:
        raise AppError(1003, '仅可使用当前公开的知识库')
    message_id, conversation_id = new_id('guest_m'), new_id('guest_c')

    async def events():
        chunks = []
        with SessionLocal() as pipeline_db:
            try:
                async for event in RagPipeline(pipeline_db).run(question=body.question, kb_ids=kb_ids,
                    message_id=message_id, conversation_id=conversation_id, history=[]):
                    kind, data = event['event'], event['data']
                    if kind == 'meta':
                        yield _sse({'event': 'meta', 'data': {'conversation_id': conversation_id, 'guest': True}})
                    elif kind == 'delta':
                        chunks.append(data['text'])
                        yield _sse({'event': 'delta', 'data': {'text': data['text']}})
                    elif kind == 'done':
                        # Explicit whitelist: never forward pipeline payloads or citation IDs/snippets.
                        safe = {key: data[key] for key in ('model', 'refused', 'declined') if key in data}
                        answer = data.get('answer') if isinstance(data.get('answer'), str) else ''.join(chunks)
                        safe.update(answer=re.sub(r'\[\d+\]', '', answer), citations=[], guest=True)
                        yield _sse({'event': 'done', 'data': safe})
                    elif kind == 'error':
                        yield _sse({'event': 'error', 'data': {'message': '公共问答暂不可用，请稍后重试'}})
                        return
            except Exception:
                logger.exception('public chat failed')
                yield _sse({'event': 'error', 'data': {'message': '公共问答暂不可用，请稍后重试'}})
    return StreamingResponse(events(), media_type='text/event-stream', headers=SSE_HEADERS)
