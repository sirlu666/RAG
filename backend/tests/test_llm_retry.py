"""B-02 · 连接失败重试回归测试。

用 httpx.MockTransport 桩隔离网络，不访问真实 DeepSeek。
覆盖任务书 B-02 要求的六条路径：
  1. 首次连接失败后重试成功
  2. 持续连接失败到上限
  3. 429 后重试成功
  4. 401 不重试
  5. 首 token 超时
  6. 已有正文后中断不重试

通过 LlmClient(transport=...) 注入 MockTransport；用 monkeypatch 覆盖 settings
关闭 MOCK_LLM、设假 key，走真实重试路径。
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.rag import llm as llm_module


def _sse_chunk(text: str) -> str:
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _collect_stream(client, messages) -> list[str]:
    """同步收集一次 stream_chat 的全部 yield。"""
    async def _run():
        return [p async for p in client.stream_chat(messages, stats={})]
    return asyncio.run(_run())


@pytest.fixture(autouse=True)
def _force_real_path(monkeypatch):
    """所有测试强制走真实重试路径：关 mock、设假 key、重试上限 2。"""
    monkeypatch.setattr(settings, "mock_llm", False)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_max_retries", 2)


def test_first_connect_failure_then_success(monkeypatch):
    """首次连接抛 ConnectError，第二次成功 → 应重试并返回正文。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        body = _sse_chunk("你好") + _sse_done()
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    pieces = _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert pieces == ["你好"]
    assert calls["n"] == 2  # 连接失败重试了一次


def test_persistent_connect_failure_hits_limit(monkeypatch):
    """持续连接失败 → 重试到上限后抛 AppError(4001)。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception) as e:
        _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert "4001" in str(e.value) or e.value.code == 4001
    # 上限 = llm_max_retries(2)，即首次 + 2 次重试 = 3 次尝试
    assert calls["n"] == 3


def test_429_then_success(monkeypatch):
    """429 后重试成功。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, content=b'{"error":"rate limited"}')
        body = _sse_chunk("重试成功") + _sse_done()
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    pieces = _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert pieces == ["重试成功"]
    assert calls["n"] == 2


def test_401_no_retry(monkeypatch):
    """401 不重试，直接抛 AppError。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, content=b'{"error":"unauthorized"}')

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception):
        _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert calls["n"] == 1  # 401 不重试


def test_first_token_timeout(monkeypatch):
    """首 token 超时（wait_for 触发 TimeoutError）→ 可重试。"""
    monkeypatch.setattr(settings, "llm_first_token_timeout_s", 0.05)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            # 流打开后一直不吐 data，也不结束 → wait_for 触发首 token 超时
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  stream=_HangingStream())
        body = _sse_chunk("超时后重试成功") + _sse_done()
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    pieces = _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert pieces == ["超时后重试成功"]
    assert calls["n"] == 2


def test_no_retry_after_partial_output(monkeypatch):
    """已吐正文后中断 → 不重试（避免重复答案），抛 AppError。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # 吐一段正文后，流在读取中途抛 ReadError（模拟连接中断）
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              stream=_BrokenMidStream())

    client = llm_module.LlmClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception):
        _collect_stream(client, [{"role": "user", "content": "hi"}])
    assert calls["n"] == 1  # 已吐字，不重试


class _HangingStream(httpx.AsyncByteStream):
    """打开后永远不吐字节、也不结束（用于触发首 token 超时）。"""

    async def __aiter__(self):
        # 挂起直到被 wait_for 取消
        await asyncio.sleep(3600)
        yield b""  # pragma: no cover - 不会走到


class _BrokenMidStream(httpx.AsyncByteStream):
    """先吐一段正文，然后在读取中途抛 ReadError（模拟连接中断）。"""

    def __init__(self):
        self._sent = False

    async def __aiter__(self):
        if not self._sent:
            self._sent = True
            yield _sse_chunk("前半段").encode("utf-8")
        raise httpx.ReadError("connection dropped mid-stream")

