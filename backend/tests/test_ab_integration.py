"""A → B 的真实联调：走 A 的上传接口入库，再用 B 的问答接口检索。

为什么不能只用手工造 chunk 的夹具：那样验证不到 A 的解析/切片/写库是否与 B 的口径一致。
这里全程只用 A 的 6 个接口 + B 的 /api/chat/stream，不碰数据库内部。
"""

from __future__ import annotations

import json

from app.core.config import settings

DOC_EQUATION = """# 一元二次方程

## 求根公式

对 $ax^2+bx+c=0\\ (a\\neq 0)$，判别式 $\\Delta=b^2-4ac$。

例 1 解方程 $x^2-5x+6=0$。

解：因式分解得 $(x-2)(x-3)=0$，所以 $x_1=2$，$x_2=3$。
"""

DOC_DERIVATIVE = """# 导数与单调性

若在区间上 $f'(x)>0$，则函数在该区间单调递增；若 $f'(x)<0$，则单调递减。

例 2 求 $f(x)=x^3-3x$ 的单调区间。

解：$f'(x)=3x^2-3=3(x-1)(x+1)$。令 $f'(x)>0$，得 $x<-1$ 或 $x>1$。
"""


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


def upload(client, headers, filename: str, content: str, kb_id: str | None = None) -> dict:
    data = {"kb_id": kb_id} if kb_id else {}
    resp = client.post(
        "/api/docs/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        data=data,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def wait_ready(client, headers, doc_id: str) -> dict:
    """A 用 BackgroundTasks，TestClient 会等后台任务跑完；这里仍按契约轮询一次。"""
    body = client.get(f"/api/docs/{doc_id}/status", headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]


def chat(client, headers, kb_id: str, question: str) -> list[tuple[str, dict]]:
    resp = client.post(
        "/api/chat/stream",
        json={"kb_ids": [kb_id], "question": question},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return parse_sse(resp.text)


def test_upload_through_a_then_answer_through_b(client, monkeypatch):
    monkeypatch.setattr(settings, "relevance_threshold", 0.0)
    headers = {"Authorization": "Bearer dev"}

    # ---------- 1) A：上传并入库 ----------
    uploaded = upload(client, headers, "方程.md", DOC_EQUATION)
    doc_id = uploaded["doc_id"]
    status = wait_ready(client, headers, doc_id)
    assert status["status"] == "ready", status
    assert status["chunk_count"] >= 1

    docs = client.get("/api/docs", headers=headers).json()["data"]
    kb_id = next(d["kb_id"] for d in docs if d["id"] == doc_id)

    # ---------- 2) B：检索 A 写的 chunk ----------
    frames = chat(client, headers, kb_id, "解方程 x^2-5x+6=0")
    names = [n for n, _ in frames]
    assert names[0] == "meta" and names[-1] == "done"
    assert "citation" in names, f"应命中 A 入库的 chunk，实际事件：{names}"

    top = next(d for n, d in frames if n == "citation")
    assert top["doc_id"] == doc_id, "C 用 doc_id 调 A 的 preview 跳转原文"
    assert top["doc_name"] == "方程.md"
    assert top["page"] is None  # markdown 没有页码，契约允许省略
    # A 的切片保证"题干 + 解"在同一条 chunk
    assert "解" in top["snippet"]
    assert frames[0][1]["hits"] >= 1

    # ---------- 3) A 再传一篇 → B 必须立刻看得到（BM25 指纹失效）----------
    second = upload(client, headers, "导数.md", DOC_DERIVATIVE, kb_id=kb_id)
    assert wait_ready(client, headers, second["doc_id"])["status"] == "ready"

    frames2 = chat(client, headers, kb_id, "求 f(x)=x^3-3x 的单调区间")
    cites2 = [d["doc_name"] for n, d in frames2 if n == "citation"]
    assert "导数.md" in cites2, f"新入库的文档没进检索：{cites2}"

    # ---------- 4) A 删除文档 → B 不得再召回 ----------
    assert client.delete(f"/api/docs/{doc_id}", headers=headers).json()["code"] == 0

    frames3 = chat(client, headers, kb_id, "因式分解求 x^2-5x+6=0 的根")
    cites3 = [d["doc_name"] for n, d in frames3 if n == "citation"]
    assert "方程.md" not in cites3, f"删除后仍召回：{cites3}"


def test_bm25_index_sees_new_chunks_without_restart(client, seeded):
    """A 入库后 B 必须立刻可检索：BM25 缓存靠语料指纹失效，而不是等 TTL 或重启。"""
    from app.db.models import Chunk
    from app.db.session import SessionLocal
    from app.rag.retriever import get_bm25_index

    content = "洛必达法则：当分子分母同时趋于零或无穷时，可对二者分别求导后再取极限。"
    with SessionLocal() as db:
        before = get_bm25_index(db, [seeded["kb_id"]])
        assert before.search("洛必达法则", top_k=3) == [], "语料里本来没有这条"

        chunk = Chunk(
            doc_id=seeded["doc_id"],
            kb_id=seeded["kb_id"],
            user_id=seeded["alice"],
            seq=99,
            content=content,
            content_type="theory",
            token_count=40,
        )
        db.add(chunk)
        db.commit()
        chunk_id = chunk.id

        after = get_bm25_index(db, [seeded["kb_id"]])
        hits = after.search("洛必达法则", top_k=3)
        assert hits and hits[0][0] == chunk_id, "索引没有感知到新 chunk"

        db.delete(chunk)
        db.commit()
