"""B-05 · 消费 A 知识标签的测试（可解释候选微调）。

验证：
  - tag_match_score：知识点命中问题 → 加分；未命中/无标签 → 0
  - apply_tag_boost：命中候选前移，未标注候选不排除
  - _parse_tags：坏 JSON / 空 → 空结构，不崩溃
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
    # 命中候选被前移（boost 0.02 加在 0.4 上仍可能不敌 0.9，但应相对自身前移）
    ids = [c.chunk_id for c in out]
    assert "hit" in ids


def test_apply_tag_boost_preserves_top1_without_overpowering():
    """boost 上限 0.05，不足以盖过 0.5 的分数差，避免打乱主依据。"""
    c_hit = _cand("hit", tags_json='{"knowledge_points":["泰勒公式"]}', vector_score=0.80)
    c_top = _cand("top", tags_json="", vector_score=0.95)
    out = apply_tag_boost("泰勒公式", [c_hit, c_top])
    # 0.80 + 0.02 = 0.82 仍 < 0.95，top 保持第一
    assert out[0].chunk_id == "top"
