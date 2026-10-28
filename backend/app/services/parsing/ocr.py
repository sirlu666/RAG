"""扫描版 PDF 的 OCR：文字识别 + 行合并 + 公式转 LaTeX。

分工：
- 文字：rapidocr_onnxruntime（CPU、离线、中文效果好，约 2–5s/页 @200dpi）；
- 公式：可插拔。pix2tex 本地模型，或 Mathpix 兼容的 HTTP 接口（准确率最高）；
  都没装时保留 OCR 原文并记录告警，绝不假装公式已经转好。

只做"页面图片 → 文本"，落盘与切片仍由 loader / splitter 负责。
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("mathrag.ocr")

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z0-9]")
MATH_CHARS = set("=+-*/^_(){}[]|<>≤≥≠≈∑∫∏√πθαβγλμσφωΔ∞∂∈∉⊂⊆∪∩→⇒⇔±×÷·′″％%")
PUNCT_HEAD = set("，。、；：？！）】》”’,.;:?!)]}%")
_formula_warned = False


@dataclass
class OcrLine:
    text: str
    score: float
    box: tuple[float, float, float, float]  # x0, y0, x1, y1

    @property
    def y_center(self) -> float:
        return (self.box[1] + self.box[3]) / 2

    @property
    def height(self) -> float:
        return max(1.0, self.box[3] - self.box[1])


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise AppError(2003, "OCR 需要 numpy，请先安装依赖") from exc
    return np


def _render_page(page, dpi: int):
    np = _require_numpy()
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return img


def _engine():
    if settings.ocr_engine != "rapid":
        raise AppError(2003, f"未支持的 OCR 引擎：{settings.ocr_engine}")
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:  # pragma: no cover
        raise AppError(2003, "服务器缺少 OCR 依赖（rapidocr_onnxruntime）") from exc
    return RapidOCR()


def _to_lines(result: Iterable) -> list[OcrLine]:
    lines: list[OcrLine] = []
    for item in result or []:
        box, text, score = item[0], item[1], item[2]
        if not str(text).strip():
            continue
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        lines.append(
            OcrLine(
                text=str(text).strip(),
                score=float(score) if str(score).replace(".", "", 1).isdigit() else 0.0,
                box=(min(xs), min(ys), max(xs), max(ys)),
            )
        )
    return lines


def _merge_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """把同一水平行的多个检测框合并成一行（教辅常见：一行被图/公式切成 2–3 段）。"""
    if not lines:
        return []
    ordered = sorted(lines, key=lambda l: (l.y_center, l.box[0]))
    rows: list[list[OcrLine]] = []
    for line in ordered:
        placed = False
        for row in rows:
            ref = row[0]
            tol = 0.6 * max(ref.height, line.height)
            if abs(line.y_center - ref.y_center) <= tol:
                row.append(line)
                placed = True
                break
        if not placed:
            rows.append([line])

    merged: list[OcrLine] = []
    for row in rows:
        row.sort(key=lambda l: l.box[0])
        text = ""
        for item in row:
            if not text:
                text = item.text
            elif item.text[:1] in PUNCT_HEAD:
                text += item.text
            elif CJK_RE.search(text[-1:]) or CJK_RE.search(item.text[:1]):
                text += item.text
            else:
                text += " " + item.text
        box = (
            min(i.box[0] for i in row),
            min(i.box[1] for i in row),
            max(i.box[2] for i in row),
            max(i.box[3] for i in row),
        )
        merged.append(
            OcrLine(text=text.strip(), score=sum(i.score for i in row) / len(row), box=box)
        )
    merged.sort(key=lambda l: (l.box[1], l.box[0]))
    return merged


def looks_like_formula(text: str) -> bool:
    """判定"是否是独立公式行"。

    只认几乎不含中文、符号密集、没有选项标记的整行公式。
    夹在中文里的行内公式（`设 P(A|B)=0.5，则…`）不做整行识别——pix2tex 是行级模型，
    拿混排行去识别只会得到垃圾 LaTeX，宁可保留 OCR 原文。
    """
    core = text.strip()
    if not (2 <= len(core) <= 80):
        return False
    if CJK_RE.search(core):
        return False
    if re.search(r"\([A-D]\)|（[A-D]）", core):  # 选择题选项行，不是公式
        return False
    math = sum(1 for ch in core if ch in MATH_CHARS)
    latin = len(LATIN_RE.findall(core))
    if math >= 2 and latin >= 1:
        return True
    # Text OCR can drop '=' and superscripts. Retain a conservative candidate
    # path for short variable/number expressions with one surviving operator.
    return (math >= 1 and latin >= 3 and bool(re.search(r'\d', core))
            and not re.search(r'[A-Za-z]{3,}', core))


def _formula_engine():
    """返回 callable(img) -> latex 或 None。"""
    global _formula_warned
    mode = settings.ocr_formula
    if mode == "none":
        return None
    if mode == 'rapid_latex':
        from app.services.parsing.formula import require_ready, recognize_array
        try:
            require_ready()
            return recognize_array
        except RuntimeError:
            logger.warning('本机 ONNX 公式环境未准备，将保留 OCR 原文')
            return None
    if mode in ("auto", "api") and settings.ocr_formula_api_url and settings.ocr_formula_api_key:
        return _api_formula
    if mode in ("auto", "pix2tex"):
        try:
            from PIL import Image
            from pix2tex.cli import LatexOCR

            model = LatexOCR()

            def _run(img) -> str:
                return model(Image.fromarray(img))

            return _run
        except Exception as exc:  # 模型没装/权重下载失败
            if mode == "pix2tex":
                logger.warning("pix2tex 不可用：%s", exc)
            if not _formula_warned:
                logger.warning("公式识别不可用，将保留 OCR 原文：%s", exc)
                _formula_warned = True
    return None


def _api_formula(img) -> str:
    """Mathpix 兼容接口：POST 图片，返回 latex。"""
    import io

    import httpx
    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format="PNG")
    resp = httpx.post(
        settings.ocr_formula_api_url,
        headers={"app_key": settings.ocr_formula_api_key, "app_id": "mathrag"},
        files={"file": ("formula.png", buffer.getvalue(), "image/png")},
        data={"formats": ["latex_styled"]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("latex_styled") or data.get("text") or ""


def _crop(img, box: tuple[float, float, float, float]):
    x0, y0, x1, y1 = (int(v) for v in box)
    h, w = img.shape[:2]
    return img[max(0, y0 - 3) : min(h, y1 + 3), max(0, x0 - 3) : min(w, x1 + 3)]


def _lines_to_text(img, lines, formula):
    texts = []
    for line in lines:
        if formula and looks_like_formula(line.text):
            try:
                latex = formula(_crop(img, line.box)).strip()
            except Exception:
                logger.warning('公式识别失败，保留该行 OCR 原文')
                latex = ''
            if latex:
                texts.append(f'$$\n{latex}\n$$')
                continue
        texts.append(line.text)
    return '\n'.join(texts)


def is_scanned_pdf(path: Path, sample: int = 5, min_chars: float = 50) -> bool:
    """快速判定：抽若干页看有没有文字层。"""
    import pymupdf

    with pymupdf.open(path) as doc:
        n = doc.page_count
        if n == 0:
            return True
        idxs = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})[:sample]
        total = sum(len(doc[i].get_text("text").strip()) for i in idxs)
    return total / max(len(idxs), 1) < min_chars


def ocr_pdf_pages(
    path: Path,
    dpi: int | None = None,
    pages: Iterable[int] | None = None,
) -> list[tuple[int, str]]:
    """把扫描版 PDF 转成 [(页码, 文本)]，页码从 1 开始。"""
    import pymupdf

    dpi = dpi or settings.ocr_dpi
    out: list[tuple[int, str]] = []

    if settings.ocr_engine == "vlm":
        from app.services.parsing.vlm import page_to_markdown

        with pymupdf.open(path) as doc:
            total = doc.page_count
            want = list(pages) if pages else list(range(1, total + 1))
            if settings.ocr_max_pages:
                want = want[: settings.ocr_max_pages]
            for page_no in want:
                if page_no < 1 or page_no > total:
                    continue
                img = _render_page(doc[page_no - 1], dpi)
                out.append((page_no, page_to_markdown(img, page_no)))
                logger.info("vlm page %d/%d", page_no, total)
        return out

    engine = _engine()
    formula = _formula_engine()

    with pymupdf.open(path) as doc:
        total = doc.page_count
        want = list(pages) if pages else list(range(1, total + 1))
        if settings.ocr_max_pages:
            want = want[: settings.ocr_max_pages]

        for page_no in want:
            if page_no < 1 or page_no > total:
                continue
            img = _render_page(doc[page_no - 1], dpi)
            result, _ = engine(img)
            lines = _merge_lines(_to_lines(result))
            out.append((page_no, _lines_to_text(img, lines, formula)))
            logger.info("ocr page %d/%d (%d lines)", page_no, total, len(lines))
    return out


def decode_image(raw: bytes, suffix: str):
    """Shared image validation for text OCR and explicit formula screenshots."""
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - project runtime dependency
        raise AppError(2003, "图片 OCR 需要 Pillow，请检查项目依赖") from exc

    try:
        with Image.open(BytesIO(raw)) as source:
            expected = {"png": {"PNG"}, "jpg": {"JPEG"}, "jpeg": {"JPEG"}}
            if source.format not in expected.get(suffix.lower().lstrip("."), set()):
                raise AppError(2003, "图片格式与文件扩展名不一致")
            if source.width * source.height > 25_000_000:
                raise AppError(2003, "图片分辨率过大，请缩小到 2500 万像素以内后重试")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except AppError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(2003, "图片无法读取，请选择有效的 PNG 或 JPEG 图片") from exc
    return image


def ocr_image_pages(path: Path) -> list[tuple[int, str]]:
    """识别单张 PNG/JPEG 图片，输出可沿用文档切片流程的第一页文字。"""
    if settings.ocr_engine != "rapid":
        raise AppError(2003, "单张图片目前使用本地 RapidOCR；请将 OCR_ENGINE 设为 rapid")
    np = _require_numpy()
    image = decode_image(path.read_bytes(), path.suffix)

    img = np.asarray(image)
    result, _ = _engine()(img)
    lines = _merge_lines(_to_lines(result))
    if not lines:
        raise AppError(2003, "图片中未识别到文字，请尝试更清晰、光线更好的图片")
    # Only independent formula lines are eligible; Chinese mixed text stays intact.
    formula = _formula_engine() if any(looks_like_formula(line.text) for line in lines) else None
    return [(1, _lines_to_text(img, lines, formula))]
