"""B9 · 多轮上下文：只带最近 N 轮，且按字符预算截断。

最近 3 轮原文用于生成上下文；短指代追问另外拼接最近的独立用户问题，
仅供召回与重排。界面、消息持久化和生成仍使用原始用户问题。
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.chat_models import Message


_FOLLOWUP = re.compile(
    r'第[一二三四五六七八九十\d]+步|第[一二两三\d]+种解法|另一种解法|为什么这样|接上题|这一步|继续解释'
    r'|(?:为什么|为何)(?:分界点|临界点|转折点|顶点|端点)(?:是|为|取|选)'
)
_NEW_TOPIC = re.compile(r'^(?:(?:请|我们|现在|接下来|那就)[，,\s]*)*(?:新问题|换题|换个题|另外一道|重新提问)')
_INDEPENDENT = re.compile(r'^(?:请)?(?:已知|设|给定|求解|计算|判断|解方程|求(?:方程|函数|极限|导数|积分|数列))')


def is_dependent_question(question: str) -> bool:
    text = question.strip()
    return (len(text) <= 200 and not _NEW_TOPIC.match(text) and not _INDEPENDENT.match(text)
            and bool(_FOLLOWUP.search(text)))


def build_retrieval_question(question: str, history: list[dict] | None = None) -> str:
    """Anchor short follow-ups to a user question, never to generated assistant text."""
    if not history or not is_dependent_question(question):
        return question
    for item in reversed(history):
        if not isinstance(item, dict) or item.get('role') != 'user':
            continue
        anchor = item.get('content')
        if not isinstance(anchor, str) or not anchor.strip() or is_dependent_question(anchor):
            continue
        prefix, separator = '原问题：', '\n追问：'
        remaining = settings.history_char_budget - len(prefix + separator + question)
        if remaining <= 0:
            return question
        return prefix + anchor.strip()[:remaining] + separator + question
    return question


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
        if not isinstance(data, dict):
            return {"questions": [], "materials": []}
        return {
            "questions": data.get("questions") if isinstance(data.get("questions"), list) else [],
            "materials": data.get("materials") if isinstance(data.get("materials"), list) else [],
        }
    except (ValueError, TypeError):
        return {"questions": [], "materials": []}
