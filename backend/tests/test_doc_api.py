"""6 个文档接口的集成测试（含后台入库、越权、重复、覆盖、重建）。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

DOC = """# 第三章 函数与导数

## 3.1 函数的单调性

一般地，设函数 $f(x)$ 的定义域为 $I$，如果对于区间 $D$ 上的任意两个自变量 $x_1,x_2$，
当 $x_1<x_2$ 时都有 $f(x_1)<f(x_2)$，则称 $f(x)$ 在 $D$ 上单调递增。

例 1 判断函数 $f(x)=x^2+2x$ 在 $(-\\infty,-1]$ 上的单调性。

解：配方得
$$f(x)=x^2+2x=(x+1)^2-1$$
其图象是开口向上的抛物线，对称轴为 $x=-1$，故在 $(-\\infty,-1]$ 上单调递减。

定理 1（介值定理）若 $f$ 在 $[a,b]$ 上连续，则对任意介于 $f(a)$ 与 $f(b)$ 之间的数 $\\mu$，
存在 $\\xi\\in[a,b]$ 使 $f(\\xi)=\\mu$。

习题 1.1
求 $f(x)=x^3-3x$ 的单调区间，并说明理由。
"""

_counter = {"n": 0}


def unique_doc(tag: str) -> str:
    """每次生成不同内容，避免被 sha256 去重拦住（去重是跨文件名的）。"""
    _counter["n"] += 1
    return f"{DOC}\n\n补充说明 {tag}-{_counter['n']}：本例用于测试，内容唯一。\n"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def upload(client, filename, content, kb_id=None, overwrite=False, user=None):
    data = {}
    if kb_id:
        data["kb_id"] = kb_id
    if overwrite:
        data["overwrite"] = "true"
    headers = {"Authorization": f"Bearer dev:{user}"} if user else {}
    return client.post(
        "/api/docs/upload",
        files={"file": (filename, content.encode("utf-8"), "text/markdown")},
        data=data,
        headers=headers,
    )


def upload_ok(client, filename, tag="x", **kwargs):
    body = upload(client, filename, unique_doc(tag), **kwargs).json()
    assert body["code"] == 0, body
    return body["data"]["doc_id"]


def test_upload_ready_and_preview(client):
    doc_id = upload_ok(client, "demo.md", "ready")

    status = client.get(f"/api/docs/{doc_id}/status").json()["data"]
    assert status["status"] == "ready", status
    assert status["progress"] == 100
    assert status["chunk_count"] >= 3

    preview = client.get(f"/api/docs/{doc_id}/preview?page=1&size=10").json()["data"]
    assert preview["total"] == status["chunk_count"]
    assert preview["items"]
    for item in preview["items"]:
        assert "@@MATH" not in item["content"]
        assert item["content"].count("$") % 2 == 0
    types = {item["content_type"] for item in preview["items"]}
    assert "example" in types and "theory" in types


def test_list_and_duplicate(client):
    content = unique_doc("dup")
    doc_id = upload(client, "dup1.md", content).json()["data"]["doc_id"]
    docs = client.get("/api/docs").json()["data"]
    assert any(d["id"] == doc_id and d["status"] == "ready" for d in docs)

    # 同内容、换文件名：仍判为重复（避免重复向量）
    duplicated = upload(client, "dup2.md", content).json()
    assert duplicated["code"] == 1005
    assert duplicated["data"] is None


def test_unsupported_type(client):
    bad = client.post(
        "/api/docs/upload", files={"file": ("a.csv", b"a,b\n1,2", "text/csv")}
    ).json()
    assert bad["code"] == 2002


def test_overwrite_replaces_old(client):
    first = upload_ok(client, "ver.md", "v1")
    second = upload(client, "ver.md", unique_doc("v2"), overwrite=True).json()
    assert second["code"] == 0
    new_id = second["data"]["doc_id"]
    assert new_id != first
    ids = {d["id"] for d in client.get("/api/docs").json()["data"]}
    assert first not in ids and new_id in ids


def test_reindex_idempotent(client):
    doc_id = upload_ok(client, "re.md", "re")
    before = client.get(f"/api/docs/{doc_id}/status").json()["data"]["chunk_count"]
    assert client.post(f"/api/docs/{doc_id}/reindex").json()["code"] == 0
    after = client.get(f"/api/docs/{doc_id}/status").json()["data"]
    assert after["status"] == "ready"
    assert after["chunk_count"] == before


def test_isolation_between_users(client):
    doc_id = upload_ok(client, "private.md", "private")
    other = client.get(
        f"/api/docs/{doc_id}/status", headers={"Authorization": "Bearer dev:other"}
    )
    assert other.status_code == 403
    assert other.json()["code"] == 1003

    others = client.get("/api/docs", headers={"Authorization": "Bearer dev:other"}).json()
    assert all(d["id"] != doc_id for d in others["data"])


def test_delete_cleans_up(client):
    doc_id = upload_ok(client, "del.md", "del")
    assert client.delete(f"/api/docs/{doc_id}").json()["code"] == 0
    assert client.get(f"/api/docs/{doc_id}/status").json()["code"] == 1004
    assert all(d["id"] != doc_id for d in client.get("/api/docs").json()["data"])


def test_overwrite_failure_keeps_old(client):
    """A-03 回归：覆盖上传一个解析后内容过少的新文件，旧文档必须原样可用。

    任务书复现的缺陷：原版先删旧文档再解析新文件，新文件 rejected 后旧文档已 404。
    修复后：新文档失败，旧文档仍 ready、正文/向量可查。
    """
    first = upload_ok(client, "keep.md", "keep-v1")
    # 新文件内容仅一个字符 → 解析后 <50 字 → rejected
    resp = upload(client, "keep.md", "x", overwrite=True).json()
    assert resp["code"] == 0, resp
    new_id = resp["data"]["doc_id"]

    # 新文档最终 rejected
    status = client.get(f"/api/docs/{new_id}/status").json()["data"]
    assert status["status"] == "rejected", status

    # 旧文档必须仍在且 ready
    old = client.get(f"/api/docs/{first}/status").json()
    assert old["code"] == 0, old
    assert old["data"]["status"] == "ready"
    assert old["data"]["chunk_count"] >= 3

    # 旧文档仍可预览（正文/向量未丢）
    preview = client.get(f"/api/docs/{first}/preview?page=1&size=10").json()["data"]
    assert preview["total"] >= 3
