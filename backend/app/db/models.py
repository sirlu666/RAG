"""表结构 —— 只包含 A 负责的文档链路所需的表。

users / knowledge_bases 在本文件里只保留 A 依赖的最小字段（外键目标）；
完整用户体系与知识库 CRUD 由 C 自己的迁移维护，A 不越界。
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """C 的账号字段；旧开发用户保留，空密码散列的账号不能登录。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("u"))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserProfile(Base):
    """Optional personal settings, without altering existing user rows."""
    __tablename__ = 'user_profiles'
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey('users.id'), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(30), default='')


class UserAppearance(Base):
    """Account appearance preferences; existing accounts default without migration."""
    __tablename__ = 'user_appearance'
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey('users.id'), primary_key=True)
    theme: Mapped[str] = mapped_column(String(16), default='default')


class UserFont(Base):
    """Font preference without changing existing appearance rows."""
    __tablename__ = 'user_fonts'
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey('users.id'), primary_key=True)
    font: Mapped[str] = mapped_column(String(16), default='default')


class UserAvatar(Base):
    """Small normalized avatars stored atomically with their revision."""
    __tablename__ = 'user_avatars'
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey('users.id'), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    revision: Mapped[str] = mapped_column(String(64))


class KnowledgeBase(Base):
    """同上：A 只关心归属关系，description/subject 等由 C 扩展。"""

    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_kb_user_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("kb"))
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublishedKnowledgeBase(Base):
    """Explicit owner publication; existing KBs remain private unless opted in."""
    __tablename__ = 'published_knowledge_bases'
    kb_id: Mapped[str] = mapped_column(String(32), ForeignKey('knowledge_bases.id'), primary_key=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_kb_status", "kb_id", "status"),
        Index("ix_documents_hash", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("doc"))
    kb_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_bases.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error_msg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)      # 大模型自动打标（scripts/auto_label.py）
    difficulty: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DocumentCategory(Base):
    """Manual organization stays separate from A's automatically generated tags."""
    __tablename__ = 'document_categories'

    doc_id: Mapped[str] = mapped_column(String(32), ForeignKey('documents.id'), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), default='')
    revision: Mapped[str] = mapped_column(String(32))


class DocumentOcrText(Base):
    """Corrected image text, stored separately from the original image bytes."""
    __tablename__ = 'document_ocr_texts'
    doc_id: Mapped[str] = mapped_column(String(32), ForeignKey('documents.id'), primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_doc", "doc_id"), Index("ix_chunks_kb", "kb_id"))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ch"))
    doc_id: Mapped[str] = mapped_column(String(32), ForeignKey("documents.id"))
    kb_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(16), default="other")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    has_formula: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IngestTask(Base):
    __tablename__ = "ingest_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("task"))
    doc_id: Mapped[str] = mapped_column(String(32), ForeignKey("documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(16), default="parse")
    error_msg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
