"""B4 端到端：SSE 事件序列、越权、拒答、非流式、消息落库。"""

from __future__ import annotations

import json

from app.core.config import settings
from app.db.chat_models import Message


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    event, data = None, []
    for line in raw.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif not line.strip() and event and data:
            frames.append((event, json.loads("\n".join(data))))
            event, data = None, []
    if event and data:
        frames.append((event, json.loads("\n".join(data))))
    return frames


def stream_chat(client, headers, payload) -> tuple[int, str]:
    with client.stream("POST", "/api/chat/stream", json=payload, headers=headers) as resp:
        return resp.status_code, "".join(resp.iter_text())


def test_stream_emits_contract_events(client, seeded, alice_headers):
    status, raw = stream_chat(
        client,
        alice_headers,
        {
            "kb_ids": [seeded["kb_id"]],
            "question": "判断函数 f(x)=x^2+2x 的单调性",
        },
    )
    assert status == 200

    frames = parse_sse(raw)
    names = [name for name, _ in frames]

    assert names[0] == "meta", f"首帧必须是 meta，实际 {names[:3]}"
    assert names[-1] == "done"
    assert "citation" in names, "命中语料时必须给引用"
    assert "delta" in names

    meta = frames[0][1]
    assert meta["hits"] >= 1
    assert meta["conversation_id"].startswith("c_")

    citations = [data for name, data in frames if name == "citation"]
    assert citations[0]["index"] == 1
    assert citations[0]["doc_id"] == seeded["doc_id"], "C 跳转原文依赖 doc_id"
    assert citations[0]["doc_name"] == "人教A版必修一.pdf"
    # 语料只有 3 条，命中哪条由检索决定；断言页码可回溯到种子数据
    assert citations[0]["page"] in {132, 134, 156}
    assert citations[0]["content_type"] in {"concept", "example", "theory"}

    answer = "".join(data["text"] for name, data in frames if name == "delta")
    assert answer.strip()

    done = frames[-1][1]
    for key in ("message_id", "tokens_in", "tokens_out", "latency_ms", "first_token_ms", "confidence"):
        assert key in done


def test_stream_persists_messages(client, seeded, alice_headers):
    status, raw = stream_chat(
        client, alice_headers, {"kb_ids": [seeded["kb_id"]], "question": "增函数的定义是什么"}
    )
    assert status == 200
    frames = parse_sse(raw)
    conversation_id = frames[0][1]["conversation_id"]

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
    assert [r.role for r in rows] == ["user", "assistant"]
    assert rows[0].content == "增函数的定义是什么"
    assert json.loads(rows[1].citations)


def test_cross_user_kb_is_forbidden(client, seeded, bob_headers):
    status, raw = stream_chat(
        client, bob_headers, {"kb_ids": [seeded["kb_id"]], "question": "增函数的定义"}
    )
    assert status == 403
    body = json.loads(raw)
    assert body["code"] == 1003
    assert body["data"] is None


def test_unknown_conversation_returns_404(client, seeded, alice_headers):
    status, raw = stream_chat(
        client,
        alice_headers,
        {"kb_ids": [seeded["kb_id"]], "question": "增函数", "conversation_id": "c_missing"},
    )
    assert status == 404
    assert json.loads(raw)["code"] == 1004


def test_refuses_when_below_threshold(client, seeded, alice_headers, monkeypatch):
    monkeypatch.setattr(settings, "relevance_threshold", 0.99)
    status, raw = stream_chat(
        client, alice_headers, {"kb_ids": [seeded["kb_id"]], "question": "请证明黎曼猜想"}
    )
    assert status == 200

    frames = parse_sse(raw)
    names = [name for name, _ in frames]
    assert "citation" not in names, "拒答不应给引用"
    answer = "".join(data["text"] for name, data in frames if name == "delta")
    assert "未找到依据" in answer
    assert frames[-1][1]["refused"] is True


def test_non_stream_mode_returns_envelope(client, seeded, alice_headers):
    status, raw = stream_chat(
        client,
        alice_headers,
        {"kb_ids": [seeded["kb_id"]], "question": "增函数", "stream": False},
    )
    assert status == 200
    body = json.loads(raw)
    assert body["code"] == 0
    assert body["data"]["answer"]
    assert body["data"]["citations"]


def test_empty_question_is_rejected(client, seeded, alice_headers):
    status, raw = stream_chat(client, alice_headers, {"kb_ids": [seeded["kb_id"]], "question": ""})
    assert status == 400
    assert json.loads(raw)["code"] == 1001
