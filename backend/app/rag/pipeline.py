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
import copy
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.rag import reranker
from app.rag.context import build_retrieval_question
from app.rag.llm import LlmClient, estimate_tokens, get_llm
from app.rag.prompt import REFUSAL_TEMPLATE, build_messages
from app.rag.retriever import Candidate, RetrievalResult, retrieve

logger = logging.getLogger("mathrag.pipeline")

_CITE = re.compile(r"\[(\d+)\]")
SNIPPET_MAX = 160

# system prompt 强制"资料不足时直接回答'未找到依据'"，所以这个措辞是契约而非巧合。
# 只认**开头**：模型常在真答案末尾补一句"未找到依据：资料未给出 X"作为小注
# （实测洛必达那题就是这样），用 in 会把好答案误判成拒答。
NO_EVIDENCE_MARK = "未找到依据"


def _related_materials(candidates: list[Candidate], exclude_chunk_ids: set[str], max_n: int) -> list[dict]:
    """从检索候选里取"没被选进 citation 的"资料做推荐（零额外模型调用，可回表）。

    与 citation 同源同定位字段，保证 doc_id/chunk_id 真实可回表、不编造。
    """
    out: list[dict] = []
    for c in candidates:
        if c.chunk_id in exclude_chunk_ids:
            continue
        out.append(
            {
                "doc_id": c.doc_id,
                "chunk_id": c.chunk_id,
                "doc_name": c.doc_name,
                "page": c.page,
                "seq": c.seq,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "content_type": c.content_type,
            }
        )
        if len(out) >= max_n:
            break
    return out


def _related_questions_rule(question: str, picked: list[Candidate], max_n: int) -> list[str]:
    """可解释规则生成相关问题（默认路径，不额外调模型、不产生费用）。

    从命中片段的内容类型与文档主题提炼"可追问"方向：证明方法、计算步骤、概念辨析等。
    不是固定三句通用问题——每句都锚定本轮命中的具体资料。
    """
    qs: list[str] = []
    seen: set[str] = set()
    type_hints = {
        "example": "这题还有哪些不同的解法？",
        "theory": "这个定理的适用条件是什么？",
        "concept": "这个概念和相邻概念有什么区别？",
        "exercise": "类似的练习还有哪些？",
    }
    for c in picked:
        hint = type_hints.get(c.content_type)
        doc = (c.doc_name or "").split("__")[-1].split(".")[0]
        if hint and doc and hint not in seen:
            seen.add(hint)
            qs.append(f"{doc}：{hint}")
        if len(qs) >= max_n:
            break
    return qs


# --------------------------------------------------------------------------
# B-05：消费 A 的知识标签（可解释的候选微调，不排除未标注资料）
# --------------------------------------------------------------------------

def _parse_tags(tags_json: str) -> dict:
    """从 documents.tags_json 解析 knowledge_points/question_types/difficulty。"""
    import json

    if not tags_json:
        return {}
    try:
        data = json.loads(tags_json)
    except json.JSONDecodeError:
        return {}
    return {
        "knowledge_points": data.get("knowledge_points") or [],
        "question_types": data.get("question_types") or [],
        "difficulty": data.get("difficulty"),
    }


def tag_match_score(question: str, candidate: Candidate) -> float:
    """候选文档的知识点与问题文本的子串匹配度（0/0.02/0.05 三档，可解释）。

    只做**加分**（boost），不做减分/过滤：未标注资料的候选得 0，绝不因此被排除。
    """
    tags = _parse_tags(candidate.tags_json)
    kps = tags.get("knowledge_points")
    if not kps:
        return 0.0
    q = question or ""
    hits = [kp for kp in kps if kp and kp in q]
    if not hits:
        return 0.0
    # 命中的知识点越多，boost 略高；上限 0.05，不足以盖过 rerank/向量分的差异
    return min(0.05, 0.02 * len(hits))


def apply_tag_boost(question: str, candidates: list[Candidate]) -> list[Candidate]:
    """Annotate tag_rank without changing retrieval order or evidence scores.

    The caller chooses the primary score (RRF/vector/rerank). This stage
    only adds tag annotations to copies, preserving all evidence scores.
    """
    if not candidates:
        return []
    boosted = []
    for c in candidates:
        rank = tag_match_score(question, c)
        if rank > 0:
            cc = copy.copy(c)
            cc.tag_rank = rank
            boosted.append(cc)
        else:
            boosted.append(c)
    return boosted


def answer_declined(answer: str) -> bool:
    """模型自己说"没依据"——检索过了阈值，但模型判断资料答不了这个问题。

    与 refused 的区别：refused 是**管线**在调用模型前就拒答（引用数恒为 0）；
    declined 是模型读到资料后仍判定不足，此时引用数 > 0，但不应展示成有据答案。
    """
    return (answer or "").lstrip().startswith(NO_EVIDENCE_MARK)


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
    seq: int = 0
    char_start: int = 0
    char_end: int = 0

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
            # 定位字段：PDF 用 page，markdown 用 char_start/char_end（page 为 null）
            "seq": self.seq,
            "char_start": self.char_start,
            "char_end": self.char_end,
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
            # 定位字段：PDF 用 page，markdown 用 char_start/char_end（page 为 null）
            seq=c.seq,
            char_start=c.char_start,
            char_end=c.char_end,
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
        """Rerank + 截断。Rerank 未配置时等价于按融合顺序取 Top-N。

        B-05：先做标签微调（设置 tag_rank 排序键，不污染证据分），再 rerank。
        tag_rank 只在证据分相同时做 tie-break，绝不改变 confidence/拒答判定。
        """
        boosted = apply_tag_boost(question, result.candidates)
        if any(c.tag_rank for c in boosted):
            # RRF is the primary hybrid score; cosine is primary for vector-only
            # retrieval. Stable ties preserve the retriever's original order.
            boosted.sort(key=lambda c: (
                c.rrf_score if result.mode == 'hybrid' else c.vector_score, c.tag_rank
            ), reverse=True)
        return reranker.rerank(question, boosted, settings.rerank_top_n)

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
        retrieval_question = build_retrieval_question(question, history)

        try:
            result = await asyncio.to_thread(self.search, retrieval_question, kb_ids)
            picked = await asyncio.to_thread(self.pick, retrieval_question, result)
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
                    "declined": False,
                    # 拒答无依据：推荐为空（任务书 B-04：无依据/失败可返回空数组）
                    "related_questions": [],
                    "related_materials": [],
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

        declined = answer_declined(answer)
        if declined:
            logger.info("model declined to answer (insufficient evidence), citations=%d", len(citations))

        usage = stats.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or estimate_tokens("".join(m["content"] for m in messages)))
        tokens_out = int(usage.get("completion_tokens") or estimate_tokens(answer))

        # B-04 推荐：相关资料（零成本、可回表）+ 相关问题（规则生成，默认不调模型）。
        # F3 修复：推荐是**附加能力**，任何故障都不应破坏已生成的主答案——
        # 用 try/except 隔离，失败静默降级为空数组，done 照常产出。
        # declined（模型拒答）与 refused 一样，均无依据，推荐返回空。
        if declined:
            related_materials: list[dict] = []
            related_questions: list[str] = []
        else:
            try:
                cited_ids = {c.chunk_id for c in citations}
                related_materials = _related_materials(result.candidates, cited_ids, settings.related_max)
                related_questions = _related_questions_rule(question, picked, settings.related_max)
            except Exception:
                logger.exception("recommendation generation failed, degraded to empty")
                related_materials = []
                related_questions = []

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
                # refused=管线拒答（没调模型）；declined=模型读了资料仍说没依据。
                # C 侧判定"按无依据展示"的条件是 refused or declined。
                "refused": False,
                "declined": declined,
                "answer": fixed,
                "citations": [c.as_dict() for c in citations],
                # B-04 推荐（可选字段，默认空数组；旧客户端不读也不影响）
                "related_questions": related_questions,
                "related_materials": related_materials,
            },
        }

    async def answer(
        self,
        *,
        question: str,
        kb_ids: list[str],
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        """非流式便捷入口（评估脚本用）：收集 run() 的结果。

        与流式一致的错误语义（修复 F2）：
        - run() 产出 error 且未产出 done → 抛出 AppError（保留 error 的 code/message），
          不把"未完成/失败"伪装成成功空答案；
        - 已产出 done 后又 error（罕见）→ 以 done 为准，但保留 partial 标记。
        """
        text, citations, confidence, refused, declined = "", [], 0.0, False, False
        related = {"questions": [], "materials": []}
        seen_done = False
        error = None
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
                seen_done = True
                confidence = event["data"]["confidence"]
                refused = bool(event["data"].get("refused"))
                declined = bool(event["data"].get("declined"))
                related = {
                    "questions": event["data"].get("related_questions") or [],
                    "materials": event["data"].get("related_materials") or [],
                }
            elif event["event"] == "error":
                error = event["data"]

        # F2：未收到 done 且发生了 error → 传播错误，不返回"成功空答案"
        if not seen_done and error is not None:
            raise AppError(int(error.get("code") or 5000), error.get("message") or "模型调用失败")

        return {
            "text": text,
            "citations": citations,
            "confidence": confidence,
            "refused": refused,
            "declined": declined,
            "related": related,
            "partial": bool(error),  # 已 done 又 error（部分输出），供调用方判断
            "retrieval_question": build_retrieval_question(question, history),
        }

    # ------------------------------------------------------------------ 工具
    @staticmethod
    async def _plain_stream(text: str, size: int = 12) -> AsyncIterator[str]:
        for i in range(0, len(text), size):
            await asyncio.sleep(0)
            yield text[i : i + size]
