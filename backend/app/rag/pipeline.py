"""B2/B3/B4/B8/B9 · RAG 编排：召回 → 融合 → 重排 → 拒答判定 → Prompt → 流式生成。

本模块不 import FastAPI：`api/chat.py` 只负责把这里产出的事件翻译成 SSE，
`scripts/eval.py` 也复用同一套逻辑（评估与线上走同一条链路，指标才有意义）。

事件形状（与 docs/01 §6 一一对应）：
    {"event": "meta",     "data": {...}}
    {"event": "citation", "data": {...}}
    {"event": "delta",    "data": {"text": "..."}}
    {"event": "done",     "data": {...}}
    {"event": "error",    "data": {"code": 4001, "message": "..."}}
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.rag import reranker
from app.rag.llm import LlmClient, estimate_tokens, get_llm
from app.rag.prompt import REFUSAL_TEMPLATE, build_messages
from app.rag.retriever import Candidate, RetrievalResult, retrieve

logger = logging.getLogger("mathrag.pipeline")

_CITE = re.compile(r"\[(\d+)\]")
SNIPPET_MAX = 160


@dataclass
class Citation:
    index: int
    chunk_id: str
    doc_id: str
    doc_name: str
    page: int | None
    snippet: str
    score: float
    content_type: str

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "page": self.page,
            "snippet": self.snippet,
            "score": round(float(self.score), 4),
            "content_type": self.content_type,
        }


def _snippet(text: str) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= SNIPPET_MAX else clean[:SNIPPET_MAX] + "…"


def sanitize_citations(text: str, allowed: int) -> str:
    """第三层幻觉防护：删掉不存在资料编号的引用标记（如只给了 5 条却有 [9]）。"""

    def _replace(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return match.group(0) if 1 <= idx <= allowed else ""

    return _CITE.sub(_replace, text)


def to_citations(candidates: list[Candidate]) -> list[Citation]:
    return [
        Citation(
            index=i,
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            doc_name=c.doc_name,
            page=c.page,
            snippet=_snippet(c.content),
            score=c.relevance,
            content_type=c.content_type,
        )
        for i, c in enumerate(candidates, start=1)
    ]


class RagPipeline:
    def __init__(self, db: Session, llm: LlmClient | None = None) -> None:
        self.db = db
        self.llm = llm or get_llm()

    # ------------------------------------------------------------------ 检索
    def search(self, question: str, kb_ids: list[str]) -> RetrievalResult:
        return retrieve(self.db, question, kb_ids)

    def pick(self, question: str, result: RetrievalResult) -> list[Candidate]:
        """Rerank + 截断。Rerank 未配置时等价于按融合顺序取 Top-N。"""
        return reranker.rerank(question, result.candidates, settings.rerank_top_n)

    def confidence(self, picked: list[Candidate]) -> float:
        return round(max((c.relevance for c in picked), default=0.0), 4)

    def should_refuse(self, picked: list[Candidate], confidence: float) -> bool:
        return (not picked) or confidence < settings.relevance_threshold

    # ------------------------------------------------------------------ 主流程
    async def run(
        self,
        *,
        question: str,
        kb_ids: list[str],
        message_id: str,
        conversation_id: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict]:
        started = time.perf_counter()

        try:
            result = await asyncio.to_thread(self.search, question, kb_ids)
            picked = await asyncio.to_thread(self.pick, question, result)
        except AppError:
            raise
        except Exception as exc:  # 检索基础设施故障
            logger.exception("retrieval failed")
            yield {"event": "error", "data": {"code": 4002, "message": "检索服务异常，请稍后重试"}}
            raise AppError(4002, "检索服务异常") from exc

        citations = to_citations(picked)
        confidence = self.confidence(picked)

        yield {
            "event": "meta",
            "data": {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "retrieval_ms": result.retrieval_ms,
                "hits": len(citations),
            },
        }

        # --- B8 拒答：检索不到就明说，绝不硬答 ---
        if self.should_refuse(picked, confidence):
            refusal = REFUSAL_TEMPLATE.format(
                score=confidence, threshold=settings.relevance_threshold
            )
            async for piece in self._plain_stream(refusal):
                yield {"event": "delta", "data": {"text": piece}}
            yield {
                "event": "done",
                "data": {
                    "message_id": message_id,
                    "tokens_in": estimate_tokens(question),
                    "tokens_out": estimate_tokens(refusal),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "first_token_ms": 0,
                    "confidence": confidence,
                    "refused": True,
                },
            }
            return

        for cite in citations:
            yield {"event": "citation", "data": cite.as_dict()}

        messages = build_messages(question, picked, history)
        stats: dict = {}
        buffer: list[str] = []

        try:
            async for delta in self.llm.stream_chat(messages, stats=stats):
                buffer.append(delta)
                yield {"event": "delta", "data": {"text": delta}}
        except AppError as exc:
            yield {"event": "error", "data": {"code": exc.code, "message": exc.message}}
            return

        answer = "".join(buffer)
        fixed = sanitize_citations(answer, allowed=len(citations))
        if fixed != answer:
            # 已经流式发出的内容无法回收，只能提示前端以 done 后的完整文本为准
            logger.warning("answer contained invalid citation index, sanitized copy kept")

        usage = stats.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or estimate_tokens("".join(m["content"] for m in messages)))
        tokens_out = int(usage.get("completion_tokens") or estimate_tokens(answer))

        yield {
            "event": "done",
            "data": {
                "message_id": message_id,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "first_token_ms": int(stats.get("first_token_ms") or 0),
                "confidence": confidence,
                "model": stats.get("model") or settings.deepseek_model,
                "answer": fixed,
                "citations": [c.as_dict() for c in citations],
            },
        }

    async def answer(
        self,
        *,
        question: str,
        kb_ids: list[str],
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        """非流式便捷入口（评估脚本用）：收集 run() 的结果。"""
        text, citations, confidence, refused = "", [], 0.0, False
        async for event in self.run(
            question=question,
            kb_ids=kb_ids,
            message_id="m_eval",
            conversation_id="c_eval",
            history=history,
        ):
            if event["event"] == "delta":
                text += event["data"]["text"]
            elif event["event"] == "citation":
                citations.append(event["data"])
            elif event["event"] == "done":
                confidence = event["data"]["confidence"]
                refused = bool(event["data"].get("refused"))
        return {"text": text, "citations": citations, "confidence": confidence, "refused": refused}

    # ------------------------------------------------------------------ 工具
    @staticmethod
    async def _plain_stream(text: str, size: int = 12) -> AsyncIterator[str]:
        for i in range(0, len(text), size):
            await asyncio.sleep(0)
            yield text[i : i + size]
