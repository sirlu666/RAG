"""F2 回归 · 非流式 answer() 与流式一致的错误语义。

验证：
  - 首段前模型失败（error 无 done）→ answer() 抛 AppError，不返回成功空答案
  - 部分输出后失败 → 不伪装完整答案
  - 正常成功 → 返回完整 dict，无 partial
  - 拒答（refused）是正常路径，不抛错
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.core.exceptions import AppError
from app.rag.pipeline import RagPipeline


class _FailingLlm:
    """模拟模型：要么首段前抛 AppError，要么吐一段后抛。"""

    def __init__(self, *, fail_before: bool = True, partial_text: str = ""):
        self.fail_before = fail_before
        self.partial_text = partial_text

    async def stream_chat(self, messages, stats=None) -> AsyncIterator[str]:
        if not self.fail_before and self.partial_text:
            yield self.partial_text
        raise AppError(4001, "模型调用失败：HTTP 500")


class _OkLlm:
    async def stream_chat(self, messages, stats=None) -> AsyncIterator[str]:
        yield "由题意，"
        yield "答案是 42。"


def _pipe(db, llm):
    return RagPipeline(db, llm=llm)


def test_answer_propagates_model_error_before_first_token(seeded):
    """F2：首段前模型失败，answer() 应抛 AppError 而非返回空成功答案。"""
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            return await _pipe(db, _FailingLlm(fail_before=True)).answer(
                question="判断单调性", kb_ids=[seeded["kb_id"]]
            )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.code == 4001


def test_answer_propagates_error_after_partial_output(seeded):
    """F2：部分输出后失败，answer() 应抛错（不伪装完整答案）。"""
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            return await _pipe(db, _FailingLlm(fail_before=False, partial_text="前半段答案")).answer(
                question="判断单调性", kb_ids=[seeded["kb_id"]]
            )

    with pytest.raises(AppError):
        asyncio.run(_run())


def test_answer_success_returns_full_dict(seeded):
    """F2：正常成功返回完整 dict，无 error。"""
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            return await _pipe(db, _OkLlm()).answer(question="判断单调性", kb_ids=[seeded["kb_id"]])

    result = asyncio.run(_run())
    assert result["text"] == "由题意，答案是 42。"
    assert result["refused"] is False
    assert result.get("partial") is False


def test_answer_refusal_is_not_error(seeded):
    """F2：refused（拒答）是正常路径，不抛错，refused=True。"""
    from app.db.session import SessionLocal

    async def _run():
        with SessionLocal() as db:
            return await _pipe(db, _OkLlm()).answer(question="今天天气怎么样", kb_ids=[seeded["kb_id"]])

    result = asyncio.run(_run())
    assert result["refused"] is True
