"""B9 · 多轮上下文：只带最近 N 轮，且按字符预算截断。

范围基线明确砍掉了"指代消解 / query 改写"（06 §2），这里只做**上下文拼接**：
把最近 3 轮原文放进 Prompt 让模型自己理解指代，不改写用户问题。
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.chat_models import Message


def load_history(db: Session, conversation_id: str | None, *, before_message_id: str | None = None) -> list[dict[str, str]]:
    """取最近 N 轮（user + assistant 成对），按时间正序返回。"""
    if not conversation_id:
        return []

    query = db.query(Message).filter(Message.conversation_id == conversation_id)
    if before_message_id:
        # 排除本轮刚写入的用户消息，避免把当前问题重复塞进历史
        query = query.filter(Message.id != before_message_id)
    rows = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(
        settings.history_turns * 2
    ).all()

    history = [{"role": m.role, "content": m.content} for m in reversed(rows)]

    # 按字符预算从后往前保留（越近越重要）
    budget = settings.history_char_budget
    kept: list[dict[str, str]] = []
    for item in reversed(history):
        size = len(item["content"])
        if size > budget:
            continue
        budget -= size
        kept.append(item)
    return list(reversed(kept))


def dump_citations(citations: list[dict]) -> str:
    return json.dumps(citations, ensure_ascii=False)


def load_citations(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def dump_related(questions: list[str], materials: list[dict]) -> str:
    """B-04 推荐持久化：{"questions": [...], "materials": [...]}。"""
    return json.dumps({"questions": questions, "materials": materials}, ensure_ascii=False)


def load_related(raw: str) -> dict:
    """历史恢复推荐；旧数据（无 related）返回空结构。"""
    try:
        data = json.loads(raw or "{}")
        return {
            "questions": data.get("questions") if isinstance(data.get("questions"), list) else [],
            "materials": data.get("materials") if isinstance(data.get("materials"), list) else [],
        }
    except json.JSONDecodeError:
        return {"questions": [], "materials": []}
