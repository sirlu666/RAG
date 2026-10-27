"""B2/B6 · 检索封装：向量 + BM25 → RRF 融合。

契约（A → B）：向量库 metadata 只做过滤与展示，**正文与页码以关系库 chunks 表为准**
（docs/A-接口与边界.md §4）。因此这里回表取正文，避免 metadata 里的 snippet 被截断。

安全：`kb_ids` 必须由上层先做归属校验（api 层调 kb 校验后传入），检索层只按白名单过滤。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chunk, Document
from app.rag.embedder import embed_query
from app.rag.hybrid import BM25Index, order_by_rrf, rrf_fuse
from app.rag.vectorstore import get_store

logger = logging.getLogger("mathrag.retriever")


@dataclass
class ChunkRecord:
    chunk_id: str
    kb_id: str
    doc_id: str
    doc_name: str
    content: str
    content_type: str = "other"
    page: int | None = None
    seq: int = 0
    # 原文定位：markdown/网页类语料没有页码（page 恒为 None），
    # C 侧要靠 char_start/char_end 才能把引用跳到原文对应段落。
    char_start: int = 0
    char_end: int = 0
    # B-05：文档级大模型标签（documents.tags_json 的原始 JSON 字符串），
    # 用于可解释的候选排序；无标签为 ""（回退，不影响召回）。
    tags_json: str = ""


@dataclass
class Candidate(ChunkRecord):
    vector_score: float = 0.0
    bm25_score: float = 0.0
    bm25_norm: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float | None = None
    # B-05：标签微调的**排序键**（0~0.05），只影响候选先后顺序，
    # 绝不参与 relevance/confidence/拒答判定——证据分与排序分必须分离。
    tag_rank: float = 0.0

    @property
    def relevance(self) -> float:
        """用于拒答阈值与前端展示的统一相关度（0-1）。

        优先级：Rerank 分 > 向量余弦 > BM25 归一化分 × 0.5。
        最后一档是给"公式精确命中、但语义向量没召回"的兜底：上限 0.5，
        既能通过 0.35 的默认阈值，又不会让纯 BM25 命中被当成高置信。

        注意：这里**不含** tag_rank——标签是排序键，不是证据分，
        避免标签污染拒答阈值（否则 0.61 的候选被加成 0.63 会错误放行）。
        """
        if self.rerank_score is not None:
            return float(self.rerank_score)
        if self.vector_score > 0:
            return float(self.vector_score)
        return float(self.bm25_norm) * 0.5

    def rank_key(self) -> tuple[float, float]:
        """排序键 = (证据分, 标签微调)，标签只在证据分相同时做 tie-break。

        第一个分量用 rerank_score（有重排）或 relevance（无重排），
        第二个分量是 tag_rank，量级 0.05 远小于证据分档位，绝不反超主依据。
        """
        if self.rerank_score is not None:
            return (float(self.rerank_score), self.tag_rank)
        return (self.relevance, self.tag_rank)


@dataclass
class RetrievalResult:
    candidates: list[Candidate] = field(default_factory=list)
    retrieval_ms: int = 0
    vector_hits: int = 0
    bm25_hits: int = 0
    fused: int = 0
    mode: str = "hybrid"

    @property
    def top_score(self) -> float:
        return max((c.relevance for c in self.candidates), default=0.0)


# --------------------------------------------------------------------- 语料读取
def load_chunk_records(db: Session, kb_ids: list[str]) -> list[ChunkRecord]:
    """取一个知识库里所有 ready 文档的 chunk（正文以关系库为准）。"""
    if not kb_ids:
        return []
    rows = (
        db.query(Chunk, Document.filename, Document.tags_json)
        .join(Document, Document.id == Chunk.doc_id)
        .filter(Chunk.kb_id.in_(kb_ids), Document.status == "ready")
        .order_by(Chunk.doc_id, Chunk.seq)
        .all()
    )
    return [
        ChunkRecord(
            chunk_id=chunk.id,
            kb_id=chunk.kb_id,
            doc_id=chunk.doc_id,
            doc_name=filename,
            content=chunk.content,
            content_type=chunk.content_type,
            page=chunk.page,
            seq=chunk.seq,
            char_start=chunk.char_start or 0,
            char_end=chunk.char_end or 0,
            tags_json=tags_json or "",
        )
        for chunk, filename, tags_json in rows
    ]


# ------------------------------------------------------------ BM25 索引（带缓存）
_lock = threading.Lock()
# key -> (built_at, fingerprint, index)
_bm25_cache: dict[tuple, tuple[float, tuple[int, str], BM25Index]] = {}


def _fingerprint(db: Session, kb_ids: list[str]) -> tuple[int, str]:
    """语料指纹 = (chunk 数, 最新 chunk 创建时间)。

    A 上传/删除/重建索引后 B 必须立刻看得到，不能等 TTL：
    - 新增/删除 → chunk 数变化；
    - 重建（reindex）→ 数量可能不变，但 created_at 变了。
    一次聚合查询，走 kb_id 索引，成本可忽略。
    """
    count, newest = (
        db.query(func.count(Chunk.id), func.max(Chunk.created_at))
        .filter(Chunk.kb_id.in_(kb_ids))
        .one()
    )
    return int(count or 0), str(newest or "")


def get_bm25_index(db: Session, kb_ids: list[str]) -> BM25Index:
    key = tuple(sorted(kb_ids))
    ttl = settings.bm25_cache_ttl_s
    now = time.time()
    current = _fingerprint(db, kb_ids)

    with _lock:
        cached = _bm25_cache.get(key)
        if cached and now - cached[0] < ttl and cached[1] == current:
            return cached[2]

    records = load_chunk_records(db, kb_ids)
    index = BM25Index([(r.chunk_id, r.content) for r in records])

    with _lock:
        _bm25_cache[key] = (now, current, index)
    return index


def invalidate_bm25_cache() -> None:
    """手动清空（脚本/测试用）。线上靠指纹自动失效，A 侧无需感知 B 的缓存。"""
    with _lock:
        _bm25_cache.clear()


# ------------------------------------------------------------------ 检索主流程
def retrieve(
    db: Session,
    question: str,
    kb_ids: list[str],
    *,
    top_k: int | None = None,
    use_hybrid: bool | None = None,
) -> RetrievalResult:
    """返回按 RRF（或纯向量）排序的候选，尚未截断到 rerank_top_n。"""
    started = time.perf_counter()
    top_k = top_k or settings.retrieval_top_k
    use_hybrid = settings.hybrid_enabled if use_hybrid is None else use_hybrid
    result = RetrievalResult(mode="hybrid" if use_hybrid else "vector")

    if not kb_ids:
        return result

    # --- 向量路 ---
    vector_scores: dict[str, float] = {}
    vector_docs: dict[str, tuple[str, dict]] = {}
    try:
        hits = get_store().query(embed_query(question), kb_ids=kb_ids, top_k=top_k)
    except Exception:  # 向量库故障不应该让整个问答 500：降级为纯 BM25
        logger.exception("vector recall failed, fallback to bm25 only")
        hits = []

    for hit in hits:
        vector_scores[hit.id] = hit.score
        vector_docs[hit.id] = (hit.document, hit.metadata)
    result.vector_hits = len(hits)

    # --- BM25 路 ---
    bm25_scores: dict[str, float] = {}
    if use_hybrid:
        try:
            bm25_scores = dict(get_bm25_index(db, kb_ids).search(question, top_k=top_k))
        except Exception:
            logger.exception("bm25 recall failed, fallback to vector only")
            result.mode = "vector"
    result.bm25_hits = len(bm25_scores)

    # --- 融合 ---
    vector_rank = [cid for cid, _ in sorted(vector_scores.items(), key=lambda kv: kv[1], reverse=True)]
    bm25_rank = [cid for cid, _ in sorted(bm25_scores.items(), key=lambda kv: kv[1], reverse=True)]

    if use_hybrid and bm25_rank:
        fused = rrf_fuse([vector_rank, bm25_rank], k=settings.rrf_k)
        ordered = order_by_rrf(fused)
    else:
        fused = {cid: score for cid, score in vector_scores.items()}
        ordered = vector_rank

    result.fused = len(ordered)

    # --- 回表补正文 ---
    records = {r.chunk_id: r for r in load_chunk_records(db, kb_ids)}
    max_bm25 = max(bm25_scores.values(), default=0.0)
    candidates: list[Candidate] = []
    for chunk_id in ordered:
        record = records.get(chunk_id)
        if record is None:
            # 关系库没有、向量库有：按契约视为脏数据，跳过（一致性脚本会报出来）
            logger.warning("orphan vector chunk=%s not in db, skipped", chunk_id)
            continue
        bm25 = bm25_scores.get(chunk_id, 0.0)
        candidates.append(
            Candidate(
                **record.__dict__,
                vector_score=vector_scores.get(chunk_id, 0.0),
                bm25_score=bm25,
                bm25_norm=(bm25 / max_bm25) if max_bm25 else 0.0,
                rrf_score=fused.get(chunk_id, 0.0),
            )
        )

    result.candidates = candidates
    result.retrieval_ms = int((time.perf_counter() - started) * 1000)
    return result
