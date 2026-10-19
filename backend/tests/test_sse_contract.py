"""B5 · 契约测试：mock 流逐帧反序列化。

mock 文件是"可执行契约"（docs/01 §6）：字段改名、少字段、类型漂移都会在这里红。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.api.schemas import (
    SSE_EVENT_MODELS,
    CitationEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
)

MOCK = Path(__file__).resolve().parents[2] / "docs" / "api" / "mock" / "chat_stream.txt"


def parse_frames(text: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    event = None
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line.strip() == "":
            if event and data_lines:
                frames.append((event, json.loads("\n".join(data_lines))))
            event, data_lines = None, []
    if event and data_lines:
        frames.append((event, json.loads("\n".join(data_lines))))
    return frames


def test_mock_file_exists():
    assert MOCK.exists(), f"契约 mock 缺失：{MOCK}"


def test_every_mock_frame_matches_schema():
    frames = parse_frames(MOCK.read_text(encoding="utf-8"))
    assert frames, "mock 流为空"

    for name, payload in frames:
        model = SSE_EVENT_MODELS.get(name)
        assert model is not None, f"未知事件类型：{name}"
        model.model_validate(payload)  # 字段缺失/类型错误会直接抛


def test_event_order_is_contractual():
    names = [name for name, _ in parse_frames(MOCK.read_text(encoding="utf-8"))]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert names.count("citation") >= 1
    assert names.count("delta") >= 1
    # 引用必须先于正文：前端先渲染来源骨架
    assert max(i for i, n in enumerate(names) if n == "citation") < min(
        i for i, n in enumerate(names) if n == "delta"
    )


def test_each_event_model_requires_contract_fields():
    MetaEvent.model_validate(
        {"message_id": "m_1", "conversation_id": "c_1", "retrieval_ms": 12, "hits": 5}
    )
    CitationEvent.model_validate(
        {
            "index": 1,
            "chunk_id": "ch_1",
            "doc_id": "doc_1",
            "doc_name": "a.pdf",
            "page": 1,
            "snippet": "…",
            "score": 0.8,
            "content_type": "example",
        }
    )
    DeltaEvent.model_validate({"text": "x"})
    DoneEvent.model_validate(
        {
            "message_id": "m_1",
            "tokens_in": 10,
            "tokens_out": 20,
            "latency_ms": 100,
            "first_token_ms": 50,
            "confidence": 0.7,
        }
    )
    ErrorEvent.model_validate({"code": 4001, "message": "繁忙"})
