"""B→C 契约的两个易漂移点：引用定位字段、无依据判定。

为什么单独一个文件：这两处都不是"能跑通"就能发现的，
前者是 C 点击引用时才发现跳不过去，后者是 C 把拒答当答案渲染。
"""

from __future__ import annotations

from app.rag.pipeline import NO_EVIDENCE_MARK, answer_declined, to_citations
from app.rag.retriever import Candidate


def _cand(**kw) -> Candidate:
    base = {
        "chunk_id": "ch_1",
        "kb_id": "kb_1",
        "doc_id": "doc_1",
        "doc_name": "函数.md",
        "content": "增函数：区间内任取 x1<x2 都有 f(x1)<f(x2)。",
        "content_type": "concept",
        "page": None,
        "seq": 7,
        "char_start": 1024,
        "char_end": 1200,
    }
    base.update(kw)
    return Candidate(**base)


def test_citation_exposes_locator_fields():
    """markdown 语料 page 恒为 None，C 只能靠 char_start/char_end 定位。"""
    cite = to_citations([_cand()])[0].as_dict()

    assert cite["page"] is None
    assert cite["seq"] == 7
    assert cite["char_start"] == 1024
    assert cite["char_end"] == 1200
    assert cite["char_end"] > cite["char_start"]


def test_citation_locator_defaults_are_zero_not_missing():
    """老数据（升级前入库）没有 char 区间，字段必须在而不是 None，避免 C 侧解构报错。"""
    cite = to_citations([_cand(char_start=0, char_end=0, seq=0)])[0].as_dict()

    assert cite["char_start"] == 0
    assert cite["char_end"] == 0
    assert cite["seq"] == 0


def test_declined_when_answer_starts_with_mark():
    assert answer_declined(NO_EVIDENCE_MARK)
    assert answer_declined(f"  \n{NO_EVIDENCE_MARK}：知识库里没有讲过这个定理。")


def test_not_declined_when_mark_only_in_tail_caveat():
    """实测洛必达那题：正文是真答案，末尾补了一句"未找到依据：资料未给出超纲内容"。

    用 in 判定会把这类好答案全误杀，所以只认开头。
    """
    answer = (
        "**结论**：洛必达法则只适用于 0/0 或 ∞/∞ 型未定式 [1][3]。\n\n"
        "**条件**：f 与 F 都趋于零 [1][2]；导数存在且 F'≠0 [1][2]……\n\n"
        "**未找到依据**：资料未给出该条超纲结论的依据 [1][3]。"
    )
    assert not answer_declined(answer)


def test_empty_answer_is_not_declined():
    """模型一个字没吐（异常中断）不算 declined，那是 error 路径的事。"""
    assert not answer_declined("")
    assert not answer_declined("   ")


def test_declined_mark_is_contract_with_prompt():
    """措辞变了这里就该红：prompt 改了却没同步判定逻辑，C 会静默拿不到拒答信号。"""
    from app.rag.prompt import REFUSAL_TEMPLATE

    assert REFUSAL_TEMPLATE.startswith(NO_EVIDENCE_MARK)
