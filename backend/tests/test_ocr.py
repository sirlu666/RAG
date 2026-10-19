"""OCR 版面处理的单元测试（不加载模型，纯文本/几何逻辑）。"""

from app.services.parsing.ocr import OcrLine, _merge_lines, looks_like_formula
from app.services.parsing.loader import _strip_repeated_prefix


def _line(text, x0, y0, x1, y1, score=0.9):
    return OcrLine(text=text, score=score, box=(x0, y0, x1, y1))


def test_merge_lines_same_row():
    lines = [
        _line("8.已知A发生且B不发生的概率为", 10, 100, 400, 130),
        _line("，在A发生或B不发生的条件下", 405, 102, 800, 132),
        _line("下一行内容", 10, 200, 300, 230),
    ]
    merged = _merge_lines(lines)
    assert len(merged) == 2
    assert "已知A发生" in merged[0].text and "条件下" in merged[0].text
    assert "，" in merged[0].text  # 标点前不加空格


def test_merge_lines_keeps_separate_rows():
    lines = [
        _line("第一行", 10, 10, 200, 40),
        _line("第二行", 10, 80, 200, 110),
    ]
    assert len(_merge_lines(lines)) == 2


def test_formula_detection_positive():
    assert looks_like_formula("P(A|B)=1")
    assert looks_like_formula(r"\int_0^1 x^2 dx = 1/3")


def test_formula_detection_negative():
    assert not looks_like_formula("设A，B为随机事件，则P(A)=0.5")
    assert not looks_like_formula("(A) 1 (B) 2 (C) 3 (D) 4")
    assert not looks_like_formula("")


def test_strip_repeated_prefix():
    pages = [
        (1, "微信公众号：某题本概率论1.随机事件\n正文一"),
        (2, "微信公众号：某题本概率论2.条件概率\n正文二"),
        (3, "微信公众号：某题本概率论3.独立性\n正文三"),
    ]
    cleaned = _strip_repeated_prefix(pages)
    assert cleaned[0][1].startswith("1.随机事件")
    assert "微信公众号" not in cleaned[1][1].split("\n")[0]


def test_caption_type():
    from app.rag.splitter import detect_type

    assert detect_type("图 1-1 函数图象") == "caption"
    assert detect_type("表 2-3 常见分布") == "caption"


def test_vlm_prompt_rules():
    from app.services.parsing.vlm import PROMPT

    assert "只转录" in PROMPT
    assert "$$" in PROMPT and "Markdown 表格" in PROMPT
    assert "[不清]" in PROMPT  # 不允许模型瞎猜


def test_vlm_guard_keeps_text():
    from app.services.parsing.vlm import _guard

    md = "## 第 1 页\n\n设 $f(x)=x^2$，求 $f'(x)$。\n\n$$\n\\int_0^1 x dx\n$$"
    assert _guard(md, 1) == md


def test_vlm_without_key_raises():
    import numpy as np
    import pytest

    from app.core.exceptions import AppError
    from app.services.parsing.vlm import page_to_markdown

    img = np.zeros((32, 32, 3), dtype=np.uint8)
    with pytest.raises(AppError) as exc:
        page_to_markdown(img, 1)
    assert exc.value.code == 2003
