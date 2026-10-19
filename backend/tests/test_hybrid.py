"""B6/B3 单测：BM25 命中、RRF 排序、引用编号校验、Few-shot 选题。"""

from __future__ import annotations

from app.rag.hybrid import BM25Index, order_by_rrf, rrf_fuse
from app.rag.pipeline import sanitize_citations
from app.rag.prompt import select_few_shot

DOCS = [
    ("ch_1", "增函数的定义：当 x1<x2 时，都有 f(x1)<f(x2)，则 f(x) 在区间上单调递增。"),
    ("ch_2", "求根公式 x=(-b±√(b^2-4ac))/(2a)，判别式决定实根个数。"),
    ("ch_3", "等差数列的通项公式为 a_n=a_1+(n-1)d。"),
]


def test_bm25_prefers_exact_term():
    index = BM25Index(DOCS)
    hits = index.search("求根公式 判别式", top_k=3)
    assert hits, "BM25 应有命中"
    assert hits[0][0] == "ch_2"


def test_bm25_returns_empty_for_unrelated_query():
    index = BM25Index(DOCS)
    assert index.search("完全无关的量子力学", top_k=3) == []


def test_rrf_rewards_items_in_both_lists():
    fused = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60)
    ordered = order_by_rrf(fused)
    assert set(ordered[:2]) == {"a", "b"}
    # 两路都靠前的一定排在只在单路出现的前面
    assert ordered.index("a") < ordered.index("c")


def test_rrf_is_scale_free():
    # 单路内部的具体分值不参与融合，只跟名次有关
    fused_a = rrf_fuse([["x", "y"]], k=60)
    fused_b = rrf_fuse([["x", "y", "z"]], k=60)
    assert fused_a["x"] == fused_b["x"] > fused_a["y"]


def test_sanitize_citations_drops_out_of_range():
    text = "结论见[1]，另见[7]，还有[0]。"
    assert sanitize_citations(text, allowed=5) == "结论见[1]，另见，还有。"


def test_select_few_shot_routes_by_topic():
    assert select_few_shot("解方程 x^2-5x+6=0") == "equation"
    assert select_few_shot("判断函数的单调性") == "function"
    assert select_few_shot("证明 x^2+1>2x") == "proof"
    assert select_few_shot("今天天气怎么样") is None
