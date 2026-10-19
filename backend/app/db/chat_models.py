"""B 的表：会话与消息（C 的 /conversations 三个接口按此读，B 的 /chat/stream 写入）。

刻意与 A 的 models.py 分文件：A 的表只服务文档链路，这里只服务问答链路，
两边都继承同一个 Base，create_all 时统一建表。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, new_id, utcnow


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("c"))
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    # JSON 数组字符串：["kb_x", "kb_y"]，避免为一个字段引 JSON 类型
    kb_ids: Mapped[str] = mapped_column(Text, default="[]")
    title: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation", "conversation_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("m"))
    conversation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    # JSON 数组字符串：[{chunk_id, doc_id, doc_name, page, snippet, score}]
    citations: Mapped[str] = mapped_column(Text, default="[]")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    first_token_ms: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
