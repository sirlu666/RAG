"""C: owner-scoped knowledge-base CRUD. Nonempty deletion is intentionally refused."""

from datetime import timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.exceptions import AppError, ok
from app.db.models import Document, KnowledgeBase, User, PublishedKnowledgeBase
from app.db.session import get_db

router = APIRouter(prefix="/api/kbs", tags=["knowledge-base"])


class KnowledgeBaseName(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


def owned_kb(db: Session, user: User, kb_id: str) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise AppError(1004, "知识库不存在")
    if kb.user_id != user.id:
        raise AppError(1003, "无权访问该知识库")
    return kb


def document_count(db: Session, kb: KnowledgeBase) -> int:
    return db.query(Document).filter(Document.kb_id == kb.id).count()


def serialize(kb: KnowledgeBase, count: int, is_public: bool = False) -> dict:
    created = kb.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {"id": kb.id, "name": kb.name, "document_count": count, "created_at": created.isoformat(), 'is_public': is_public}


@router.get("", summary="列出我的知识库")
def list_kbs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(KnowledgeBase, func.count(Document.id))
        .outerjoin(Document, Document.kb_id == KnowledgeBase.id)
        .filter(KnowledgeBase.user_id == user.id)
        .group_by(KnowledgeBase.id)
        .order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id)
        .all()
    )
    published = {row.kb_id for row in db.query(PublishedKnowledgeBase).filter(
        PublishedKnowledgeBase.kb_id.in_([kb.id for kb, _ in rows])).all()} if rows else set()
    return ok([serialize(kb, count, kb.id in published) for kb, count in rows])


class VisibilityBody(BaseModel):
    public: bool


@router.put('/{kb_id}/visibility', summary='由所有者公开或撤销公开知识库')
def change_visibility(kb_id: str, body: VisibilityBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = owned_kb(db, user, kb_id)
    row = db.get(PublishedKnowledgeBase, kb.id)
    if body.public and row is None:
        db.add(PublishedKnowledgeBase(kb_id=kb.id))
    elif not body.public and row is not None:
        db.delete(row)
    db.commit()
    return ok(serialize(kb, document_count(db, kb), body.public))


@router.post("", summary="创建个人知识库")
def create_kb(body: KnowledgeBaseName, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = KnowledgeBase(user_id=user.id, name=body.name)
    db.add(kb)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(1005, "你已创建同名知识库，请换一个名称") from exc
    return ok(serialize(kb, 0))


@router.get("/{kb_id}", summary="查看个人知识库详情")
def get_kb(kb_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = owned_kb(db, user, kb_id)
    return ok(serialize(kb, document_count(db, kb), db.get(PublishedKnowledgeBase, kb.id) is not None))


@router.patch("/{kb_id}", summary="修改知识库名称")
def rename_kb(kb_id: str, body: KnowledgeBaseName, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = owned_kb(db, user, kb_id)
    kb.name = body.name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(1005, "你已创建同名知识库，请换一个名称") from exc
    return ok(serialize(kb, document_count(db, kb), db.get(PublishedKnowledgeBase, kb.id) is not None))


@router.delete("/{kb_id}", summary="删除空知识库（不级联删除文档）")
def delete_kb(kb_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kb = owned_kb(db, user, kb_id)
    if document_count(db, kb):
        raise AppError(1005, "知识库中仍有文档，请先处理文档后再删除知识库")
    db.query(PublishedKnowledgeBase).filter_by(kb_id=kb.id).delete(synchronize_session=False)
    db.delete(kb)
    try:
        db.commit()
    except IntegrityError as exc:
        # SQLite foreign keys also prevent a concurrent upload from being orphaned.
        db.rollback()
        raise AppError(1005, "知识库内容已发生变化，请刷新后重试") from exc
    return ok({"kb_id": kb_id, "deleted": True})
