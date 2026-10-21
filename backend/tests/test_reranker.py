"""B7 · Rerank 单元测试：provider 分派、降级、本地/API 两条路径。

用 monkeypatch 隔离真实模型加载与网络，不依赖本地模型文件或外部 API。
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.rag import reranker
from app.rag.retriever import Candidate


def _cands(n: int = 5) -> list[Candidate]:
    out = []
    for i in range(n):
        out.append(
            Candidate(
                chunk_id=f"ch_{i}",
                kb_id="kb_1",
                doc_id=f"doc_{i}",
                doc_name=f"d{i}.md",
                content=f"第 {i} 条内容：增函数与单调性。",
                content_type="concept",
                vector_score=0.9 - i * 0.1,
                rrf_score=1.0 - i * 0.1,
            )
        )
    return out


def test_is_enabled_by_provider(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "local")
    assert reranker.is_enabled() is True

    monkeypatch.setattr(settings, "rerank_provider", "api")
    monkeypatch.setattr(settings, "rerank_api_base", "")
    assert reranker.is_enabled() is False

    monkeypatch.setattr(settings, "rerank_api_base", "https://x")
    monkeypatch.setattr(settings, "rerank_api_key", "k")
    assert reranker.is_enabled() is True

    monkeypatch.setattr(settings, "rerank_provider", "none")
    assert reranker.is_enabled() is False


def test_none_provider_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "none")
    cands = _cands()
    out = reranker.rerank("增函数", cands, top_n=3)
    # 保持原顺序、原对象，不排序不评分
    assert [c.chunk_id for c in out] == ["ch_0", "ch_1", "ch_2"]
    assert all(c.rerank_score is None for c in out)


def test_empty_candidates_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "local")
    assert reranker.rerank("x", [], top_n=3) == []


def test_local_rerank_scores_and_orders(monkeypatch):
    """本地路径：伪造 scores，验证按分降序、只取 top_n、分数写回。"""
    monkeypatch.setattr(settings, "rerank_provider", "local")
    monkeypatch.setattr(reranker, "_rerank_local", lambda q, cands: [0.1, 0.9, 0.5, 0.3, 0.8])

    cands = _cands()
    out = reranker.rerank("增函数", cands, top_n=3)
    assert [c.chunk_id for c in out] == ["ch_1", "ch_4", "ch_2"]
    assert [round(c.rerank_score, 1) for c in out] == [0.9, 0.8, 0.5]


def test_local_rerank_failure_falls_back(monkeypatch):
    """本地模型加载/推理失败 → 退回融合顺序，不抛异常。"""
    monkeypatch.setattr(settings, "rerank_provider", "local")

    def boom(q, cands):
        raise RuntimeError("模型文件缺失")

    monkeypatch.setattr(reranker, "_rerank_local", boom)
    cands = _cands()
    out = reranker.rerank("增函数", cands, top_n=3)
    assert [c.chunk_id for c in out] == ["ch_0", "ch_1", "ch_2"]


def test_api_rerank_maps_index_to_score(monkeypatch):
    """API 路径：伪造返回 [(index, score)]，验证 index 映射与排序。"""
    monkeypatch.setattr(settings, "rerank_provider", "api")
    monkeypatch.setattr(settings, "rerank_api_base", "https://x")
    monkeypatch.setattr(settings, "rerank_api_key", "k")
    monkeypatch.setattr(reranker, "_rerank_api", lambda q, cands: [(2, 0.9), (0, 0.7), (3, 0.5)])

    cands = _cands()
    out = reranker.rerank("增函数", cands, top_n=3)
    assert [c.chunk_id for c in out] == ["ch_2", "ch_0", "ch_3"]
    assert [round(c.rerank_score, 1) for c in out] == [0.9, 0.7, 0.5]


def test_api_rerank_failure_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "api")
    monkeypatch.setattr(settings, "rerank_api_base", "https://x")
    monkeypatch.setattr(settings, "rerank_api_key", "k")

    def boom(q, cands):
        raise RuntimeError("network down")

    monkeypatch.setattr(reranker, "_rerank_api", boom)
    cands = _cands()
    out = reranker.rerank("增函数", cands, top_n=3)
    assert [c.chunk_id for c in out] == ["ch_0", "ch_1", "ch_2"]
