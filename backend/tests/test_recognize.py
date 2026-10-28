"""A-04 图片识别适配器测试：输入校验 + 失败路径（不加载真实 OCR 模型）。"""

import io

import pytest
from PIL import Image

from app.core.exceptions import AppError
from app.services.parsing.recognize import recognize_question_image, _validate


def _png_bytes(text="题目", size=(200, 100)):
    img = Image.new("RGB", size, color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_validate_rejects_unsupported_type():
    with pytest.raises(AppError) as e:
        _validate("q.gif", b"GIF89a")
    assert e.value.code == 2002


def test_validate_rejects_empty():
    with pytest.raises(AppError) as e:
        _validate("q.png", b"")
    assert e.value.code == 1001


def test_validate_rejects_oversize_bytes():
    raw = b"\x00" * (11 * 1024 * 1024)
    with pytest.raises(AppError) as e:
        _validate("q.png", raw)
    assert e.value.code == 2001


def test_validate_rejects_corrupt_image():
    with pytest.raises(AppError) as e:
        _validate("q.png", b"this is not an image")
    assert e.value.code == 2002


def test_recognize_corrupt_image_returns_failure():
    # 损坏图片在输入校验阶段就抛明确错误（不伪造结果）
    with pytest.raises(AppError) as e:
        recognize_question_image("q.png", b"not an image")
    assert e.value.code == 2002


def test_recognize_unsupported_type():
    # 直接调用也走 _validate，抛明确错误
    with pytest.raises(AppError) as e:
        recognize_question_image("q.gif", b"GIF89a")
    assert e.value.code == 2002


def test_recognize_empty_bytes():
    with pytest.raises(AppError) as e:
        recognize_question_image("q.png", b"")
    assert e.value.code == 1001


def test_result_shape_contract():
    """返回结构必须稳定：{text, latex, warnings}，warnings 恒为 list。"""
    # 用合法但无文字的纯白图 + rapid 引擎（无文字行 → 明确告警，不伪造）
    raw = _png_bytes()
    out = recognize_question_image("blank.png", raw)
    assert set(out.keys()) == {"text", "latex", "warnings"}
    assert isinstance(out["text"], str)
    assert isinstance(out["latex"], str)
    assert isinstance(out["warnings"], list)
