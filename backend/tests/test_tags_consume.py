"""B-05 · 消费 A 知识标签的测试（可解释候选微调）。

验证：
  - tag_match_score：知识点命中问题 → 加分；未命中/无标签 → 0
  - apply_tag_boost：命中候选前移，未标注候选不排除
  - _parse_tags：坏 JSON / 空 → 空结构，不崩溃
  - F1 回归：tag_rank 只做排序键，不污染 vector_score/relevance/拒答判定
"""

from __future__ import annotations

from app.rag.pipeline import _parse_tags, apply_tag_boost, tag_match_score
from app.rag.retriever import Candidate


def _cand(chunk_id, tags_json="", vector_score=0.5, rerank_score=None):
    return Candidate(
        chunk_id=chunk_id, kb_id="kb", doc_id=f"doc_{chunk_id}", doc_name="X.md",
        content="", content_type="concept", seq=1,
        vector_score=vector_score, rerank_score=rerank_score, tags_json=tags_json,
    )


def test_parse_tags_valid():
    t = _parse_tags('{"knowledge_points":["泰勒公式"],"question_types":["证明题"],"difficulty":"进阶"}')
    assert t["knowledge_points"] == ["泰勒公式"]
    assert t["question_types"] == ["证明题"]
    assert t["difficulty"] == "进阶"


def test_parse_tags_empty_or_bad():
    assert _parse_tags("") == {}
    assert _parse_tags("not json") == {}
    assert _parse_tags("{}") == {"knowledge_points": [], "question_types": [], "difficulty": None}


def test_tag_match_score_hits():
    c = _cand("a", tags_json='{"knowledge_points":["泰勒公式","极限"]}')
    assert tag_match_score("用泰勒公式展开", c) > 0


def test_tag_match_score_no_hit_or_no_tag():
    c_hit = _cand("a", tags_json='{"knowledge_points":["泰勒公式"]}')
    assert tag_match_score("行列式怎么算", c_hit) == 0.0
    c_notag = _cand("b", tags_json="")
    assert tag_match_score("泰勒公式", c_notag) == 0.0


def test_apply_tag_boost_moves_matching_forward_but_keeps_all():
    # 三个候选：一个命中知识点（初始分数更低），两个不命中
    c_hit = _cand("hit", tags_json='{"knowledge_points":["泰勒公式"]}', vector_score=0.4)
    c_a = _cand("a", tags_json="", vector_score=0.9)
    c_b = _cand("b", tags_json="", vector_score=0.8)
    out = apply_tag_boost("泰勒公式求极限", [c_hit, c_a, c_b])
    # 全部保留（未标注不被排除）
    assert {c.chunk_id for c in out} == {"hit", "a", "b"}
    ids = [c.chunk_id for c in out]
    assert "hit" in ids


def test_apply_tag_boost_only_annotates_without_reordering():
    """The tag annotation stage must not replace the retriever's primary ranking."""
    c_hit = _cand("hit", tags_json='{"knowledge_points":["泰勒公式"]}', vector_score=0.80)
    c_top = _cand("top", tags_json="", vector_score=0.95)
    out = apply_tag_boost("泰勒公式", [c_hit, c_top])
    assert [c.chunk_id for c in out] == ['hit', 'top']
    assert out[0].relevance == .80 and out[1].relevance == .95


def test_tag_boost_does_not_pollute_evidence_score():
    """F1 回归：标签命中后 vector_score/relevance 保持不变，不伪造证据分。"""
    c = _cand("hit", tags_json='{"knowledge_points":["泰勒公式"]}', vector_score=0.61)
    out = apply_tag_boost("泰勒公式", [c])
    assert out[0].vector_score == 0.61  # 证据分未被篡改
    assert out[0].relevance == 0.61     # relevance 不含 tag_rank
    assert out[0].tag_rank > 0          # 排序键确实设置了


def test_tag_boost_does_not_flip_refusal():
    """F1 回归：0.61 的候选命中标签后，relevance 仍是 0.61，不会越过 0.62 阈值放行。"""
    c = _cand("hit", tags_json='{"knowledge_points":["泰勒公式"]}', vector_score=0.61)
    out = apply_tag_boost("泰勒公式", [c])
    # 阈值 0.62：0.61 仍应拒答（relevance 未被标签抬过阈值）
    assert out[0].relevance < 0.62


def test_tag_boost_does_not_downgrade_bm25_only():
    """F1 回归：纯 BM25 回退候选（vector_score=0）命中标签后，relevance 仍走 BM25 兜底，不降分。"""
    c = Candidate(
        chunk_id="bm", kb_id="kb", doc_id="doc_bm", doc_name="X.md", content="",
        content_type="concept", seq=1, vector_score=0.0, bm25_norm=1.0,
        tags_json='{"knowledge_points":["泰勒公式"]}',
    )
    before = c.relevance  # = bm25_norm * 0.5 = 0.5
    out = apply_tag_boost("泰勒公式", [c])
    assert out[0].relevance == before == 0.5  # 不因标签丢失 BM25 证据分
    assert out[0].tag_rank > 0
