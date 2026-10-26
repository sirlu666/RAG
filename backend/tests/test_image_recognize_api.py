"""B-03 · 图片识别接口测试（不加载真实 OCR 模型，只测接口契约与失败路径）。

真实 OCR 识别由 A 的 test_recognize.py 覆盖（需 rapidocr，本机 3.13 装不上）。
这里测 B 侧接口层：路由存在、鉴权依赖、非法输入的错误码、响应结构。

错误码 → HTTP 映射（沿用 A 的 exceptions.HTTP_BY_CODE）：
  1001 空内容 → 400；2001 过大 → 413；2002 类型非法 → 415；2003 缺 OCR 依赖 → 422。
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes() -> bytes:
    img = Image.new("RGB", (200, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_recognize_endpoint_exists(client: TestClient):
    """POST /api/chat/image/recognize 路由已挂载，非法后缀在识别前被拦截。"""
    resp = client.post(
        "/api/chat/image/recognize",
        files={"file": ("q.gif", b"GIF89a", "image/png")},
        headers={"Authorization": "Bearer dev"},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == 2002  # 不支持的类型（按文件后缀判定）


def test_recognize_rejects_unsupported_type(client: TestClient):
    resp = client.post(
        "/api/chat/image/recognize",
        files={"file": ("q.gif", b"GIF89a", "image/png")},
        headers={"Authorization": "Bearer dev"},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == 2002


def test_recognize_rejects_empty_file(client: TestClient):
    resp = client.post(
        "/api/chat/image/recognize",
        files={"file": ("q.png", b"", "image/png")},
        headers={"Authorization": "Bearer dev"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


def test_recognize_oversize_file(client: TestClient):
    raw = b"\x00" * (11 * 1024 * 1024)
    resp = client.post(
        "/api/chat/image/recognize",
        files={"file": ("q.png", raw, "image/png")},
        headers={"Authorization": "Bearer dev"},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == 2001


def test_recognize_missing_ocr_reports_clear_error(client: TestClient):
    """rapidocr 缺失时明确报 2003，不静默伪造答案。"""
    resp = client.post(
        "/api/chat/image/recognize",
        files={"file": ("blank.png", _png_bytes(), "image/png")},
        headers={"Authorization": "Bearer dev"},
    )
    # 本机 3.13 装不上 rapidocr → 2003（缺依赖）；若已装则 200 且返回 {text,latex,warnings}
    if resp.status_code == 200:
        body = resp.json()
        assert body["code"] == 0
        assert set(body["data"].keys()) == {"text", "latex", "warnings"}
    else:
        assert resp.json()["code"] == 2003
