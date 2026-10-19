"""B4 · `/api/chat/stream`：SSE 问答接口（B 的对外边界）。

契约（docs/01 §6）事件顺序固定：meta → citation* → delta* → done；异常时补一个 error。
越权与参数错误在**建立流之前**抛出，走统一 JSON 信封（HTTP 403/404），不塞进 SSE。

持久化：用户消息在开流前落库；助手消息在流结束后落库（含 citations、token、耗时）。
用独立 session，避免 StreamingResponse 期间请求级依赖被回收。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api._dev_user import dev_current_user
from app.api.schemas import ChatRequest
from app.core.config import settings
from app.core.exceptions import AppError, ok
from app.db.chat_models import Conversation, Message
from app.db.models import KnowledgeBase, User, new_id, utcnow
from app.db.session import SessionLocal, get_db
from app.rag.context import dump_citations, load_history
from app.rag.pipeline import RagPipeline

logger = logging.getLogger("mathrag.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Nginx 反代必须关 buffering，否则前端看到的是一整块而不是逐字
    "X-Accel-Buffering": "no",
}


def _sse(event: dict) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"


def _assert_kbs_readable(db: Session, user: User, kb_ids: list[str]) -> list[str]:
    """先校验归属，再检索：kb_ids 来自请求体，绝不可直接信任（01 §3）。"""
    unique = list(dict.fromkeys(kb_ids))
    rows = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(unique)).all()
    owned = {kb.id for kb in rows if kb.user_id == user.id}
    if len(owned) != len(unique):
        raise AppError(1003, "知识库不存在或无权访问")
    return unique


def _get_or_create_conversation(
    db: Session, user: User, req: ChatRequest
) -> Conversation:
    if req.conversation_id:
        conv = db.get(Conversation, req.conversation_id)
        if conv is None:
            raise AppError(1004, "会话不存在")
        if conv.user_id != user.id:
            raise AppError(1003, "无权访问该会话")
        conv.kb_ids = json.dumps(req.kb_ids, ensure_ascii=False)
        conv.updated_at = utcnow()
        return conv

    conv = Conversation(
        id=new_id("c"),
        user_id=user.id,
        kb_ids=json.dumps(req.kb_ids, ensure_ascii=False),
        title=req.question.strip()[:30],
    )
    db.add(conv)
    return conv


@router.post("/stream", summary="SSE 流式问答")
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(dev_current_user),  # noqa: B008  FastAPI 依赖注入的标准写法
    db: Session = Depends(get_db),  # noqa: B008
):
    kb_ids = _assert_kbs_readable(db, user, req.kb_ids)
    conversation = _get_or_create_conversation(db, user, req)

    # 历史要在写入本轮问题之前读，避免把当前问题重复塞进上下文
    history = load_history(db, conversation.id if req.conversation_id else None)

    user_message = Message(
        id=new_id("m"), conversation_id=conversation.id, role="user", content=req.question.strip()
    )
    db.add(user_message)
    db.commit()

    conversation_id = conversation.id
    message_id = new_id("m")

    if not req.stream:
        with SessionLocal() as pipeline_db:
            result = await RagPipeline(pipeline_db).answer(
                question=req.question, kb_ids=kb_ids, history=history
            )
        _persist_assistant(
            conversation_id=conversation_id,
            message_id=message_id,
            text=result["text"],
            citations=result["citations"],
            meta={},
        )
        return ok(
            {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "answer": result["text"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "refused": result["refused"],
            }
        )

    async def event_stream() -> AsyncIterator[str]:
        chunks: list[str] = []
        citations: list[dict] = []
        done_meta: dict = {"tokens_in": 0, "tokens_out": 0, "latency_ms": 0, "first_token_ms": 0}
        failed = False
        with SessionLocal() as pipeline_db:
            pipeline = RagPipeline(pipeline_db)
            try:
                async for event in pipeline.run(
                    question=req.question,
                    kb_ids=kb_ids,
                    message_id=message_id,
                    conversation_id=conversation_id,
                    history=history,
                ):
                    if event["event"] == "delta":
                        chunks.append(event["data"]["text"])
                    elif event["event"] == "citation":
                        citations.append(event["data"])
                    elif event["event"] == "done":
                        done_meta = event["data"]
                    elif event["event"] == "error":
                        failed = True
                    yield _sse(event)
            except AppError as exc:
                failed = True
                yield _sse({"event": "error", "data": {"code": exc.code, "message": exc.message}})
            except Exception:
                logger.exception("chat stream crashed conversation=%s", conversation_id)
                failed = True
                yield _sse(
                    {"event": "error", "data": {"code": 5000, "message": "服务内部错误，请稍后重试"}}
                )
            finally:
                # 中断/失败但有半截内容时也保存，避免前端与历史不一致
                if chunks or not failed:
                    _persist_assistant(
                        conversation_id=conversation_id,
                        message_id=message_id,
                        text="".join(chunks),
                        citations=citations,
                        meta=done_meta,
                        failed=failed,
                    )

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


def _persist_assistant(
    *,
    conversation_id: str,
    message_id: str,
    text: str,
    citations: list[dict],
    meta: dict,
    failed: bool = False,
) -> None:
    if not text and failed:
        return
    with SessionLocal() as db:
        db.add(
            Message(
                id=message_id,
                conversation_id=conversation_id,
                role="assistant",
                content=text,
                citations=dump_citations(citations),
                tokens_in=int(meta.get("tokens_in") or 0),
                tokens_out=int(meta.get("tokens_out") or 0),
                latency_ms=int(meta.get("latency_ms") or 0),
                first_token_ms=int(meta.get("first_token_ms") or 0),
                model=str(meta.get("model") or ("error" if failed else settings.deepseek_model)),
            )
        )
        conv = db.get(Conversation, conversation_id)
        if conv is not None:
            conv.updated_at = utcnow()
        db.commit()


