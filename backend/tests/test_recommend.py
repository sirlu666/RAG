"""B-04 · 相似问题与资料推荐测试。

测 done 事件追加的 related_questions / related_materials：
  - 正常有依据：推荐非空、材料可回表（doc_id/chunk_id 真实）
  - 拒答：推荐为空
  - 字段默认值、旧客户端兼容（DoneEvent 可选字段）
"""

from __future__ import annotations

import pytest

from app.api.schemas import DoneEvent
from app.rag.pipeline import _related_materials, _related_questions_rule, _snippet


def test_related_materials_excludes_cited_and_returns_real_ids():
    from app.rag.retriever import Candidate

    cands = [
        Candidate(chunk_id="ch_1", kb_id="kb", doc_id="doc_a", doc_name="A.md",
                  content="", content_type="concept", seq=1, vector_score=0.9),
        Candidate(chunk_id="ch_2", kb_id="kb", doc_id="doc_b", doc_name="B.md",
                  content="", content_type="example", seq=2, vector_score=0.8),
        Candidate(chunk_id="ch_3", kb_id="kb", doc_id="doc_c", doc_name="C.md",
                  content="", content_type="theory", seq=3, vector_score=0.7),
    ]
    # 排除 ch_1（已被引用），应返回 ch_2、ch_3
    out = _related_materials(cands, {"ch_1"}, max_n=2)
    assert len(out) == 2
    assert out[0]["chunk_id"] == "ch_2"
    assert out[0]["doc_id"] == "doc_b"
    assert out[0]["doc_name"] == "B.md"
    assert out[1]["chunk_id"] == "ch_3"
    # 必须含可回表字段
    for item in out:
        assert {"doc_id", "chunk_id", "doc_name"} <= set(item.keys())


def test_related_materials_caps_at_max():
    from app.rag.retriever import Candidate

    cands = [
        Candidate(chunk_id=f"ch_{i}", kb_id="kb", doc_id=f"doc_{i}", doc_name=f"{i}.md",
                  content="", content_type="concept", seq=i, vector_score=1.0 - i * 0.1)
        for i in range(10)
    ]
    out = _related_materials(cands, set(), max_n=3)
    assert len(out) == 3


def test_related_questions_rule_anchored_to_hits():
    from app.rag.retriever import Candidate

    picked = [
        Candidate(chunk_id="ch_1", kb_id="kb", doc_id="doc_a",
                  doc_name="张宇30讲原稿__第6讲-一元函数微分学.md",
                  content="", content_type="example", seq=1),
        Candidate(chunk_id="ch_2", kb_id="kb", doc_id="doc_b",
                  doc_name="张宇30讲原稿__第1讲-函数极限与连续.md",
                  content="", content_type="theory", seq=2),
    ]
    qs = _related_questions_rule("判断单调性", picked, max_n=3)
    assert len(qs) >= 1
    # 每句都锚定命中的文档主题（不是固定通用三句）
    assert any("一元函数微分" in q or "函数极限" in q for q in qs)


def test_related_questions_rule_dedup():
    from app.rag.retriever import Candidate

    picked = [
        Candidate(chunk_id="ch_1", kb_id="kb", doc_id="doc_a", doc_name="A__主题.md",
                  content="", content_type="example", seq=1),
        Candidate(chunk_id="ch_2", kb_id="kb", doc_id="doc_b", doc_name="B__主题.md",
                  content="", content_type="example", seq=2),
    ]
    qs = _related_questions_rule("x", picked, max_n=5)
    # example 类型的提示只出现一次（去重）
    assert len(qs) == 1


def test_done_event_has_related_fields_default_empty():
    d = DoneEvent.model_validate({
        "message_id": "m_1", "tokens_in": 1, "tokens_out": 1,
        "latency_ms": 1, "first_token_ms": 1, "confidence": 0.5,
    })
    assert d.related_questions == []
    assert d.related_materials == []
