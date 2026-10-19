"""表结构 —— 只包含 A 负责的文档链路所需的表。

C 负责的 users 全量字段、B 负责的 conversations/messages/eval_runs 不在此文件内，
由各自在自己的迁移里追加（口径见 docs/01 §2）。
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("u"))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_kb_user_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("kb"))
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")
    subject: Mapped[str] = mapped_column(String(32), default="highschool_math")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


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
