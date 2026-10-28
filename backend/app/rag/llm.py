"""B1 · 大模型客户端封装（DeepSeek / OpenAI 兼容协议）。

职责边界：只管"把 messages 变成 token 流"，不认识检索、不 import FastAPI。
- 流式：`stream_chat()` 逐段 yield 文本，统计首 token 耗时与 usage；
- 重试：首 token 超时、429/5xx、连接错误 → 退避重试；**已经吐出内容后不再重试**
  （前端已经收到半截，重试会造成重复文本）；
- 统计：优先用服务端返回的 usage，缺失时按字符数估算。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("mathrag.llm")

Message = dict[str, str]


class _Retryable(Exception):
    """可重试的失败（打开流之前，或首 token 之前）。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def estimate_tokens(text: str) -> int:
    """粗略估算：中文约 1 字 = 1 token，英文约 4 字符 = 1 token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk + other / 3.5) + 1


class LlmClient:
    """DeepSeek 封装。`stats` 是调用方传入的 dict，用于回传用量与耗时。

    `transport` 仅测试注入用（httpx.MockTransport 桩），生产恒为 None。
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model = settings.deepseek_model
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self._transport = transport

    # ------------------------------------------------------------------ 流式
    async def stream_chat(
        self,
        messages: list[Message],
        *,
        stats: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        stats = stats if stats is not None else {}

        if settings.mock_llm:
            async for piece in self._mock_stream(messages, stats):
                yield piece
            return

        if not settings.deepseek_api_key:
            raise AppError(4001, "未配置 DEEPSEEK_API_KEY，无法调用大模型")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": settings.llm_max_tokens if max_tokens is None else max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        attempt = 0
        while True:
            yielded = False
            try:
                async for piece in self._stream_once(payload, stats):
                    yielded = True
                    yield piece
                return
            except _Retryable as exc:
                if yielded:
                    # 已经给前端吐过字，不能重试（会重复），直接报错
                    raise AppError(4001, f"模型服务中断：{exc.reason}") from exc
                attempt += 1
                if attempt > settings.llm_max_retries:
                    raise AppError(4001, "模型服务繁忙，请稍后重试") from exc
                backoff = 0.5 * (2 ** (attempt - 1))
                logger.warning("llm retry %d/%d in %.1fs: %s", attempt, settings.llm_max_retries, backoff, exc.reason)
                await asyncio.sleep(backoff)

    async def _stream_once(self, payload: dict, stats: dict) -> AsyncIterator[str]:
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(settings.llm_timeout_s, connect=5.0)
        started = time.perf_counter()

        client = httpx.AsyncClient(timeout=timeout, transport=self._transport)
        try:
            try:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions", headers=headers, json=payload
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "ignore")[:300]
                        # 4xx 里只有 429 值得重试；401/403 等不重试
                        if resp.status_code == 429 or resp.status_code >= 500:
                            raise _Retryable(f"HTTP {resp.status_code}: {body}")
                        raise AppError(4001, f"模型调用失败：HTTP {resp.status_code}")
                    async for piece in self._read_stream(resp, stats, started):
                        yield piece
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                    httpx.ReadError, httpx.RemoteProtocolError, httpx.WriteError) as exc:
                # 打开流阶段（尚未产生任何正文）的连接/传输层失败 → 可重试
                raise _Retryable(f"网络错误：{type(exc).__name__}") from exc
        finally:
            await client.aclose()

        stats.setdefault("model", self.model)

    @staticmethod
    async def _read_stream(
        resp: httpx.Response, stats: dict, started: float
    ) -> AsyncIterator[str]:
        """解析 SSE：首个正文 token 之前用较短超时，超时交给上层重试。"""
        lines = resp.aiter_lines()
        first_content = True
        truncated = False
        while True:
            try:
                if first_content:
                    line = await asyncio.wait_for(
                        lines.__anext__(), settings.llm_first_token_timeout_s
                    )
                else:
                    line = await lines.__anext__()
            except StopAsyncIteration:
                break
            except TimeoutError as exc:
                raise _Retryable("首 token 超时") from exc
            except httpx.ReadTimeout as exc:
                # 读流阶段超时：首 token 前可重试；已吐字则由上层 yielded 标志拦下不重试
                raise _Retryable("读流超时") from exc

            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            usage = chunk.get("usage")
            if usage:
                stats["usage"] = usage

            choices = chunk.get("choices") or []
            if not choices:
                continue
            if choices[0].get('finish_reason'):
                stats['finish_reason'] = choices[0]['finish_reason']
                truncated = choices[0]['finish_reason'] == 'length'
            text = (choices[0].get("delta") or {}).get("content") or ""
            if not text:
                continue
            if first_content:
                stats["first_token_ms"] = int((time.perf_counter() - started) * 1000)
                first_content = False
            yield text

        if truncated:
            raise AppError(4001, '模型回答达到长度上限，内容不完整，请缩短问题后重试')

    # ---------------------------------------------------------------- 非流式
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """评估脚本用：一次拿完整答案 + usage。"""
        if settings.mock_llm:
            text = "".join([p async for p in self._mock_stream(messages, {})])
            return {"content": text, "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

        if not settings.deepseek_api_key:
            raise AppError(4001, "未配置 DEEPSEEK_API_KEY，无法调用大模型")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": settings.llm_max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_s, connect=5.0)) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        if resp.status_code != 200:
            raise AppError(4001, f"模型调用失败：HTTP {resp.status_code}")
        body = resp.json()
        return {
            "content": body["choices"][0]["message"]["content"],
            "usage": body.get("usage", {}),
            "model": body.get("model", self.model),
        }

    # ------------------------------------------------------------------ mock
    async def _mock_stream(self, messages: list[Message], stats: dict) -> AsyncIterator[str]:
        """MOCK_LLM=1 时的模板回答：只为跑通 SSE 链路，不代表生成质量。"""
        stats.setdefault("model", "mock")
        stats.setdefault("first_token_ms", 1)
        prompt = "\n".join(m["content"] for m in messages)
        has_ctx = "【资料1】" in prompt
        cite = "[1]" if has_ctx else ""
        text = (
            f"（MOCK 模式）依据资料{cite}，本题的关键是把条件转化为可计算的式子。\n\n"
            "$$f(x)=x^{2}+2x=(x+1)^{2}-1$$\n\n"
            f"因此结论成立{cite}。"
            if has_ctx
            else "未找到依据：知识库中没有与问题相关的内容。"
        )
        for i in range(0, len(text), 8):
            await asyncio.sleep(0)
            yield text[i : i + 8]
        stats.setdefault("usage", {})


_client: LlmClient | None = None


def get_llm() -> LlmClient:
    global _client
    if _client is None:
        _client = LlmClient()
    return _client


def reset_llm() -> None:
    """测试用：配置变更后重建客户端。"""
    global _client
    _client = None
