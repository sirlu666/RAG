"""B7 · Rerank（可选）。

默认 **no-op**：没配 RERANK_API_BASE / RERANK_API_KEY 时直接按 RRF 顺序截断 Top-N，
不影响链路可用性；配置后调用 OpenAI 风格的 `/rerank`（如 SiliconFlow 的 bge-reranker-v2-m3）。

诚实边界：未配置 reranker 时，答辩里的消融只能报"纯向量 / +BM25"两档，不能声称做了 Rerank。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.rag.retriever import Candidate

logger = logging.getLogger("mathrag.reranker")


def is_enabled() -> bool:
    return bool(settings.rerank_api_base and settings.rerank_api_key)


def rerank(question: str, candidates: list[Candidate], top_n: int | None = None) -> list[Candidate]:
    top_n = top_n or settings.rerank_top_n
    if not candidates:
        return []
    if not is_enabled():
        return candidates[:top_n]

    base = settings.rerank_api_base.rstrip("/")
    payload = {
        "model": settings.rerank_model,
        "query": question,
        "documents": [c.content[:2000] for c in candidates],
        "top_n": min(top_n, len(candidates)),
        "return_documents": False,
    }
    headers = {"Authorization": f"Bearer {settings.rerank_api_key}"}

    try:
        with httpx.Client(timeout=settings.rerank_timeout_s) as client:
            resp = client.post(f"{base}/rerank", json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        results = resp.json().get("results", [])
    except Exception:
        # Rerank 失败不阻断问答：退回融合顺序，并在日志里留痕
        logger.exception("rerank failed, fallback to fusion order")
        return candidates[:top_n]

    picked: list[Candidate] = []
    for item in results:
        idx = item.get("index")
        if idx is None or not (0 <= idx < len(candidates)):
            continue
        cand = candidates[idx]
        cand.rerank_score = float(item.get("relevance_score", 0.0))
        picked.append(cand)

    if not picked:
        return candidates[:top_n]
    picked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
    return picked[:top_n]
