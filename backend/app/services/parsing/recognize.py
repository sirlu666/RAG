"""图片题目识别适配器（A-04）：给 B 复用 A 的 OCR/公式能力。

不创建知识库文档、不修改用户资料、不落索引。只做「图片字节 → 文本 + 可选 LaTeX」。
B 调用约定：recognize_question_image(filename, raw) -> {text, latex, warnings}。

输入校验沿用项目约定（类型/大小/像素限制）；识别失败如实返回 warnings，不伪造答案。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("mathrag.recognize")

# 图片输入限制：沿用 upload 的大小限制 + 像素上限，防超大图拖垮 CPU OCR
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_PIXELS = 4096 * 4096  # 约 16MP，超过拒绝
SUPPORTED_IMAGE_SUFFIX = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}


@dataclass
class RecognizeResult:
    text: str
    latex: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"text": self.text, "latex": self.latex, "warnings": self.warnings}


def _validate(filename: str, raw: bytes) -> None:
    """输入校验：类型 / 大小 / 像素。不合法抛 AppError（明确失败类型）。"""
    from pathlib import Path

    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIX:
        raise AppError(2002, f"不支持的图片类型：{suffix or '未知'}（支持 png/jpg/jpeg/bmp/webp/tiff）")
    if not raw:
        raise AppError(1001, "图片内容为空")
    if len(raw) > MAX_IMAGE_BYTES:
        raise AppError(2001, f"图片过大（上限 10MB）")
    _check_pixels(raw)


def _check_pixels(raw: bytes) -> None:
    """像素上限校验；图片本身损坏会在这里抛错（明确失败，不伪造结果）。"""
    from io import BytesIO

    from PIL import Image

    try:
        with Image.open(BytesIO(raw)) as im:
            w, h = im.size
    except Exception as exc:
        raise AppError(2002, f"图片无法解析（可能已损坏）：{exc}") from exc
    if w * h > MAX_PIXELS:
        raise AppError(2001, f"图片像素过大（{w}x{h}，上限 {MAX_PIXELS}）")


def _decode_to_ndarray(raw: bytes):
    """图片字节 → RGB ndarray。rapidocr 也接受 bytes，这里解码是为了 VLM 路径复用。"""
    from io import BytesIO

    import numpy as np
    from PIL import Image

    with Image.open(BytesIO(raw)) as im:
        im = im.convert("RGB")
        return np.asarray(im)


def recognize_question_image(filename: str, raw: bytes) -> dict:
    """识别一张题目图片，返回 {text, latex, warnings}。

    - text：识别出的正文（文字 + 独立公式的 LaTeX 已并入正文位置）；
    - latex：可选，独立公式行的 LaTeX 拼接（$...$ 分隔）；
    - warnings：低质量/识别失败/公式未转换等告警，如实返回。
    """
    _validate(filename, raw)

    warnings: list[str] = []

    # VLM 引擎（若配置）：整图转录，公式/结构更好
    if settings.ocr_engine == "vlm":
        try:
            md = _recognize_vlm(raw)
            return _split_text_latex(md, warnings)
        except AppError as exc:
            # VLM 失败不降级伪造，如实告警（B 可据此决定是否重试）
            warnings.append(f"VLM 识别失败：{exc.message}")
            return RecognizeResult(text="", latex="", warnings=warnings).to_dict()

    # rapid 引擎（默认 CPU 离线）
    try:
        text, latex_lines, warns = _recognize_rapid(raw)
        warnings.extend(warns)
    except AppError:
        raise
    except Exception as exc:  # 引擎缺失/其他异常
        logger.exception("recognize failed")
        return RecognizeResult(text="", latex="", warnings=[f"识别失败：{exc}"]).to_dict()

    if not text.strip() and not latex_lines:
        warnings.append("未能识别出有效文字（可能图片过暗/过糊或非文字内容）")

    return RecognizeResult(text=text, latex="\n".join(latex_lines), warnings=warnings).to_dict()


def _recognize_rapid(raw: bytes) -> tuple[str, list[str], list[str]]:
    """rapidocr 离线识别：复用行合并 + 公式判定 + 公式转 LaTeX。"""
    from app.services.parsing.ocr import (
        _engine,
        _formula_engine,
        _merge_lines,
        _to_lines,
        _crop,
        looks_like_formula,
    )

    engine = _engine()  # rapidocr 实例（接受 bytes）
    formula = _formula_engine()
    warnings: list[str] = []

    result, _ = engine(raw)
    lines = _merge_lines(_to_lines(result))

    if not lines:
        return "", [], ["未检测到文字行"]

    img = _decode_to_ndarray(raw)
    text_parts: list[str] = []
    latex_lines: list[str] = []

    for line in lines:
        if formula and looks_like_formula(line.text):
            try:
                latex = formula(_crop(img, line.box)).strip()
            except Exception:
                latex = ""
            if latex:
                latex_lines.append(f"$${latex}$$")
                # 公式在原位置保留占位，保持正文与公式顺序
                text_parts.append(f"$${latex}$$")
                continue
            else:
                warnings.append("存在独立公式但未能转换为 LaTeX，已保留原文")
        text_parts.append(line.text)

    return "\n".join(text_parts), latex_lines, warnings


def _recognize_vlm(raw: bytes) -> str:
    """VLM 整图转录（若配置）。复用 services/parsing/vlm.py。"""
    from app.services.parsing.vlm import page_to_markdown

    img = _decode_to_ndarray(raw)
    return page_to_markdown(img, None)


def _split_text_latex(md: str, warnings: list[str]) -> dict:
    """把 VLM 输出的 Markdown 拆成 {text, latex}：独立公式抽到 latex，正文保留。"""
    import re

    latex_blocks = re.findall(r"\$\$(.+?)\$\$", md, flags=re.S)
    latex = "\n".join(f"$${b.strip()}$$" for b in latex_blocks)
    # 正文保留（含行内公式），独立公式位留空行
    text = re.sub(r"\$\$.*?\$\$", "", md, flags=re.S).strip()
    return RecognizeResult(text=text, latex=latex, warnings=warnings).to_dict()
