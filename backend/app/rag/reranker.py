"""B7 · Rerank（重排）。

三种 provider（由 `RERANK_PROVIDER` 控制）：
- `local`（默认）：本地 bge-reranker-v2-m3，断网可用、零外部依赖。复用 sentence-transformers，
  与 embedding 的本地模型同一套依赖。模型目录 `RERANK_LOCAL_MODEL`。
- `api`：OpenAI 兼容 `/rerank`（如 SiliconFlow 的 bge-reranker-v2-m3），需 `RERANK_API_BASE/KEY`。
- `none`：no-op，按 RRF 顺序截断 Top-N。

无论哪种 provider，失败都**降级**回融合顺序，不阻断问答；区别是 `local`/`api` 失败会在日志留痕。

诚实边界：provider=none 时，答辩里的消融只能报"纯向量 / +BM25"两档，不能声称做了 Rerank。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import resolve, settings
from app.rag.retriever import Candidate

logger = logging.getLogger("mathrag.reranker")


def is_enabled() -> bool:
    """Rerank 是否真正生效（none 或 api 未配 key 都算未生效）。"""
    if settings.rerank_provider == "local":
        return True
    if settings.rerank_provider == "api":
        return bool(settings.rerank_api_base and settings.rerank_api_key)
    return False


# --------------------------------------------------------------------------
# 本地重排
# --------------------------------------------------------------------------

class _LocalReranker:
    """本地 bge-reranker-v2-m3，单例懒加载，CPU 推理。"""

    _model = None

    def _load(self):
        if _LocalReranker._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "本地 rerank 需要 sentence-transformers：pip install sentence-transformers"
                ) from exc
            path = resolve(settings.rerank_local_model)
            logger.info("加载本地 rerank 模型：%s", path)
            _LocalReranker._model = CrossEncoder(str(path))
        return _LocalReranker._model

    def scores(self, question: str, documents: list[str]) -> list[float]:
        model = self._load()
        pairs = [(question, doc) for doc in documents]
        return [float(v) for v in model.predict(pairs)]


_local = _LocalReranker()


def _rerank_local(question: str, candidates: list[Candidate]) -> list[float]:
    docs = [c.content[:2000] for c in candidates]
    return _local.scores(question, docs)


# --------------------------------------------------------------------------
# API 重排（OpenAI 兼容）
# --------------------------------------------------------------------------

def _rerank_api(question: str, candidates: list[Candidate]) -> list[tuple[int, float]]:
    """返回 [(index, score)]，index 对应 candidates 的下标。"""
    base = settings.rerank_api_base.rstrip("/")
    payload = {
        "model": settings.rerank_model,
        "query": question,
        "documents": [c.content[:2000] for c in candidates],
        "top_n": len(candidates),
        "return_documents": False,
    }
    headers = {"Authorization": f"Bearer {settings.rerank_api_key}"}
    with httpx.Client(timeout=settings.rerank_timeout_s) as client:
        resp = client.post(f"{base}/rerank", json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    out = []
    for item in resp.json().get("results", []):
        idx = item.get("index")
        if idx is None or not (0 <= idx < len(candidates)):
            continue
        out.append((idx, float(item.get("relevance_score", 0.0))))
    return out


# --------------------------------------------------------------------------
# 统一入口
# --------------------------------------------------------------------------

def rerank(question: str, candidates: list[Candidate], top_n: int | None = None) -> list[Candidate]:
    top_n = top_n or settings.rerank_top_n
    if not candidates:
        return []
    if not is_enabled():
        return candidates[:top_n]

    try:
        if settings.rerank_provider == "api":
            scored = _rerank_api(question, candidates)
            for idx, score in scored:
                candidates[idx].rerank_score = score
        else:  # local
            scores = _rerank_local(question, candidates)
            for cand, score in zip(candidates, scores):
                cand.rerank_score = score
    except Exception:
        # Rerank 失败不阻断问答：退回融合顺序，并在日志里留痕
        logger.exception("rerank failed, fallback to fusion order")
        return candidates[:top_n]

    scored_cands = [c for c in candidates if c.rerank_score is not None]
    if not scored_cands:
        return candidates[:top_n]
    scored_cands.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
    return scored_cands[:top_n]
