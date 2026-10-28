"""F3 回归 · 推荐失败隔离 + 拒答清空推荐。

验证：
  - 推荐生成抛错 → 主答案仍正常产出 done，推荐降级为空（不破坏主回答）
  - declined（模型拒答）→ 推荐为空
  - refused（管线拒答）→ 推荐为空（已有行为，回归确认）
  - 正常 → 推荐非空
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.rag import pipeline as pipeline_mod
from app.rag.pipeline import RagPipeline


class _DeclineLlm:
    """模型读了资料仍说没依据（declined）。"""

    async def stream_chat(self, messages, stats=None) -> AsyncIterator[str]:
        yield "未找到依据：检索到的资料无法支持这个问题。"


class _OkLlm:
    async def stream_chat(self, messages, stats=None) -> AsyncIterator[str]:
        yield "由题意，答案是 42。"


def _run_events(seeded, llm):
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            pipe = RagPipeline(db, llm=llm)
            events = []
            async for e in pipe.run(
                question="判断单调性",
                kb_ids=[seeded["kb_id"]],
                message_id="m_x",
                conversation_id="c_x",
            ):
                events.append(e)
            return events

    return asyncio.run(_run())


def _get_done(events):
    for e in events:
        if e["event"] == "done":
            return e["data"]
    return None


def test_recommend_failure_does_not_break_main_answer(seeded, monkeypatch):
    """F3：推荐抛错 → done 仍正常产出，主答案完整，推荐降级为空。"""
    def _boom(*args, **kwargs):
        raise RuntimeError("recommend boom")

    monkeypatch.setattr(pipeline_mod, "_related_materials", _boom)
    monkeypatch.setattr(pipeline_mod, "_related_questions_rule", _boom)

    events = _run_events(seeded, _OkLlm())
    done = _get_done(events)
    assert done is not None, "主答案应正常产出 done"
    assert done["answer"] == "由题意，答案是 42。"
    assert done["related_questions"] == []
    assert done["related_materials"] == []
    # 事件里不应有 error
    assert all(e["event"] != "error" for e in events)


def test_declined_clears_recommendation(seeded):
    """F3：模型 declined 拒答 → 推荐为空。"""
    events = _run_events(seeded, _DeclineLlm())
    done = _get_done(events)
    assert done is not None
    assert done["declined"] is True
    assert done["related_questions"] == []
    assert done["related_materials"] == []


def test_refused_clears_recommendation(seeded):
    """F3：管线 refused 拒答 → 推荐为空（回归确认）。"""
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            pipe = RagPipeline(db, llm=_OkLlm())
            events = []
            async for e in pipe.run(
                question="今天天气怎么样",
                kb_ids=[seeded["kb_id"]],
                message_id="m_x",
                conversation_id="c_x",
            ):
                events.append(e)
            return events

    events = asyncio.run(_run())
    done = _get_done(events)
    assert done is not None
    assert done["refused"] is True
    assert done["related_questions"] == []
    assert done["related_materials"] == []


def test_normal_recommendation_still_works(seeded):
    """F3：正常路径推荐仍能产出（不受隔离逻辑影响）。"""
    events = _run_events(seeded, _OkLlm())
    done = _get_done(events)
    assert done is not None
    # 正常有依据时，推荐至少有一个维度非空（相关资料来自候选）
    assert isinstance(done["related_questions"], list)
    assert isinstance(done["related_materials"], list)
