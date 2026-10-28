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
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.api.schemas import ChatRequest, ImageRecognizeOut
from app.core.config import settings
from app.core.exceptions import AppError, ok
from app.db.chat_models import Conversation, Message, MessageState
from app.db.models import KnowledgeBase, PublishedKnowledgeBase, User, new_id, utcnow
from app.db.session import SessionLocal, get_db
from app.rag.context import dump_citations, dump_related, load_history
from app.rag.pipeline import RagPipeline
from app.services.conversation_activity import active_conversations, conversation_lock

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
    """先校验为自有或已公开知识库，再检索；不信任请求体中的 kb_ids。"""
    unique = list(dict.fromkeys(kb_ids))
    rows = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(unique)).all()
    public = {row.kb_id for row in db.query(PublishedKnowledgeBase).filter(PublishedKnowledgeBase.kb_id.in_(unique)).all()}
    owned = {kb.id for kb in rows if kb.user_id == user.id or kb.id in public}
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


def _next_message_time(db: Session, conversation_id: str):
    # Windows clocks may return the same timestamp for both messages of a short stream.
    # UUID order is unrelated to question/answer order and must not decide that tie.
    current = utcnow()
    previous = db.query(Message.created_at).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.desc()).first()
    if previous:
        stamp = previous[0]
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        current = max(current, stamp + timedelta(microseconds=1))
    return current


@router.post(
    "/stream",
    summary="SSE 流式问答",
    responses={
        200: {
            "description": "SSE 事件流：meta → citation* → delta* → done（异常补 error）",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "example": (
                        'event: meta\ndata: {"message_id":"m_1","conversation_id":"c_1",'
                        '"retrieval_ms":212,"hits":5}\n\n'
                        'event: delta\ndata: {"text":"由题意，"}\n\n'
                    ),
                }
            },
        },
        403: {"description": "知识库/会话不属于当前用户（code=1003，JSON 信封）"},
        404: {"description": "会话不存在（code=1004，JSON 信封）"},
    },
)
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    kb_ids = _assert_kbs_readable(db, user, req.kb_ids)
    with conversation_lock:
        conversation = _get_or_create_conversation(db, user, req)
        if conversation.id in active_conversations:
            raise AppError(1005, "该对话仍在生成，请等待结束后再追问")
        # Read history before inserting the new question.
        history = load_history(db, conversation.id if req.conversation_id else None)
        user_message = Message(
            id=new_id("m"), conversation_id=conversation.id, role="user", content=req.question.strip(),
            created_at=_next_message_time(db, conversation.id),
        )
        db.add(user_message)
        db.commit()
        conversation_id = conversation.id
        message_id = new_id("m")
        active_conversations.add(conversation_id)

    if not req.stream:
        try:
            with SessionLocal() as pipeline_db:
                result = await RagPipeline(pipeline_db).answer(
                    question=req.question, kb_ids=kb_ids, history=history
                )
            _persist_assistant(
                conversation_id=conversation_id, message_id=message_id,
                text=result["text"], citations=result["citations"],
                related=result.get("related"),
                meta={"refused": result["refused"], "declined": result.get("declined", False)},
            )
        finally:
            with conversation_lock:
                active_conversations.discard(conversation_id)
        return ok(
            {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "answer": result["text"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "refused": result["refused"],
                "declined": result.get("declined", False),
                "related_questions": result.get("related", {}).get("questions", []),
                "related_materials": result.get("related", {}).get("materials", []),
            }
        )

    async def event_stream() -> AsyncIterator[str]:
        chunks: list[str] = []
        citations: list[dict] = []
        related: dict = {"questions": [], "materials": []}
        done_meta: dict = {"tokens_in": 0, "tokens_out": 0, "latency_ms": 0, "first_token_ms": 0}
        failed = False
        completed = False
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
                        completed = True
                        related = {"questions": done_meta.get("related_questions") or [],
                                   "materials": done_meta.get("related_materials") or []}
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
                try:
                    if chunks or completed:
                        _persist_assistant(
                            conversation_id=conversation_id, message_id=message_id,
                            text="".join(chunks), citations=citations, related=related, meta=done_meta,
                            failed=failed, status="failed" if failed else "done" if completed else "stopped",
                        )
                finally:
                    with conversation_lock:
                        active_conversations.discard(conversation_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post(
    "/image/recognize",
    summary="图片题目识别（B-03）：图片 → 校对文本，供 C 校对后走 /api/chat/stream",
    responses={
        200: {"description": "识别结果 {text, latex, warnings}，C 校对 text 后作为 question 发起问答"},
        400: {"description": "图片类型/大小/像素/内容非法（code=2001/2002/1001，JSON 信封）"},
        403: {"description": "未登录或越权（JSON 信封）"},
    },
)
async def recognize_image(
    file: UploadFile = File(...),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """临时题目图片识别，不写入知识库/向量索引，不修改用户资料。

    复用 A 的 recognize_question_image（OCR/公式处理），返回可校对文本；
    空/低质量文本不自动发起猜测回答，由 C 侧决定是否让用户补充。
    临时文件随请求生命周期释放，不落用户上传目录。
    """
    raw = await file.read()
    try:
        from app.services.parsing.recognize import recognize_question_image

        result = recognize_question_image(file.filename or "image", raw)
    except AppError:
        raise
    return ok(ImageRecognizeOut(**result).model_dump())


def _persist_assistant(
    *,
    conversation_id: str,
    message_id: str,
    text: str,
    citations: list[dict],
    related: dict | None = None,
    meta: dict,
    failed: bool = False,
    status: str = "done",
) -> None:
    if not text and failed:
        return
    related = related or {"questions": [], "materials": []}
    if isinstance(meta.get("answer"), str):
        text = meta["answer"]
    if isinstance(meta.get("citations"), list):
        citations = meta["citations"]
    if meta.get("refused") or meta.get("declined"):
        citations = []
        related = {"questions": [], "materials": []}
    with SessionLocal() as db:
        db.add(
            Message(
                id=message_id,
                conversation_id=conversation_id,
                role="assistant",
                content=text,
                citations=dump_citations(citations),
                related=dump_related(related.get("questions", []), related.get("materials", [])),
                tokens_in=int(meta.get("tokens_in") or 0),
                tokens_out=int(meta.get("tokens_out") or 0),
                latency_ms=int(meta.get("latency_ms") or 0),
                first_token_ms=int(meta.get("first_token_ms") or 0),
                model=str(meta.get("model") or ("mock" if settings.mock_llm else settings.deepseek_model)),
                created_at=_next_message_time(db, conversation_id),
            )
        )
        db.flush()
        db.add(MessageState(message_id=message_id, status=status,
                            details=json.dumps({"refused": bool(meta.get("refused")), "declined": bool(meta.get("declined"))})))
        conv = db.get(Conversation, conversation_id)
        if conv is not None:
            conv.updated_at = utcnow()
        db.commit()


