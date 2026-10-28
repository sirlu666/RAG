"""Owner-scoped history, cursor-paged messages and confirmed UI deletion."""

import json
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.exceptions import AppError, ok
from app.db.chat_models import Conversation, Message, MessageState
from app.db.models import User, utcnow
from app.db.session import get_db
from app.rag.context import load_citations, load_related
from app.services.conversation_activity import active_conversations, conversation_lock

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def owned(db: Session, user: User, conversation_id: str) -> Conversation:
    row = db.get(Conversation, conversation_id)
    if row is None:
        raise AppError(1004, "对话不存在或已删除")
    if row.user_id != user.id:
        raise AppError(1003, "无权访问该对话")
    return row


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def json_array(raw):
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def serialize(row: Conversation) -> dict:
    return {"id": row.id, "title": row.title, "kb_ids": json_array(row.kb_ids),
            "created_at": iso(row.created_at), "updated_at": iso(row.updated_at)}


class TitleBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.get("", summary="当前账号的对话历史")
def list_conversations(kb_id: str | None = None, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Conversation).filter(Conversation.user_id == user.id)
    if kb_id:
        # Canonical JSON strings contain each generated KB id in double quotes.
        query = query.filter(Conversation.kb_ids.contains(json.dumps(kb_id), autoescape=True))
    total = query.count()
    rows = query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).offset((page - 1) * size).limit(size).all()
    return ok({"items": [serialize(row) for row in rows], "total": total, "page": page, "size": size})


@router.get("/{conversation_id}/messages", summary="读取消息（最近开始，游标加载更早消息）")
def messages(conversation_id: str, before_id: str | None = None, size: int = Query(50, ge=1, le=100),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = owned(db, user, conversation_id)
    query = db.query(Message, MessageState).outerjoin(MessageState, MessageState.message_id == Message.id).filter(Message.conversation_id == conversation.id)
    if before_id:
        anchor = db.get(Message, before_id)
        if anchor is None or anchor.conversation_id != conversation.id:
            raise AppError(1001, "消息游标失效，请重新打开对话")
        query = query.filter(or_(Message.created_at < anchor.created_at,
                                 and_(Message.created_at == anchor.created_at, Message.id < anchor.id)))
    rows = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(size + 1).all()
    has_more = len(rows) > size
    rows = rows[:size]
    items = []
    for message, state in reversed(rows):
        try:
            details = json.loads(state.details) if state else {}
            if not isinstance(details, dict):
                details = {}
        except ValueError:
            details = {}
        related = load_related(message.related)
        items.append({"related_questions": related["questions"], "related_materials": related["materials"],
                      "id": message.id, "role": message.role, "content": message.content,
                      "citations": load_citations(message.citations), "model": message.model,
                      "status": state.status if state else "legacy", "refused": bool(details.get("refused")),
                      "declined": bool(details.get("declined")), "created_at": iso(message.created_at)})
    return ok({"conversation": serialize(conversation), "items": items, "has_more": has_more,
               "next_before_id": rows[-1][0].id if has_more else None})


@router.patch("/{conversation_id}", summary="修改对话标题")
def rename(conversation_id: str, body: TitleBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with conversation_lock:
        row = owned(db, user, conversation_id)
        row.title = body.title
        row.updated_at = utcnow()
        db.commit()
        return ok(serialize(row))


@router.delete("/{conversation_id}", summary="删除选中对话及消息（不删除知识库资料）")
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with conversation_lock:
        row = owned(db, user, conversation_id)
        if row.id in active_conversations:
            raise AppError(1005, "该对话仍在生成，请停止并等待结束后再删除")
        message_ids = db.query(Message.id).filter(Message.conversation_id == row.id)
        db.query(MessageState).filter(MessageState.message_id.in_(message_ids)).delete(synchronize_session=False)
        db.query(Message).filter(Message.conversation_id == row.id).delete(synchronize_session=False)
        db.delete(row)
        db.commit()
    return ok({"conversation_id": conversation_id, "deleted": True})
