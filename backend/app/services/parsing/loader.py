"""多格式解析：PDF（文字层，缺失时走 OCR）/ DOCX / MD / TXT。

扫描件策略：`OCR_ENABLE=true` 时自动调用 OCR 管线（见 services/parsing/ocr.py），
不做"识别个大概就入库"这种假装成功的处理。
"""

import logging
import os
import re
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("mathrag.loader")

HEADING = re.compile(r"^\s*(第[一二三四五六七八九十百]+[章节讲]|[0-9]+(\.[0-9]+)*\s+\S|例\s*\d+|习题)")
PAGE_NO_LINE = re.compile(r"^\s*[-—–\s]*\d{1,4}[-—–\s]*$")
SENTENCE_TAIL = "。！？；：，、）】》”’.!?:;)]}"


def clean_text(text: str) -> str:
    """去页码行、合并被 PDF 硬换行切断的中文句子、压缩空行。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    text = text.replace("\f", "\n")

    lines = [ln.rstrip() for ln in text.split("\n")]
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if PAGE_NO_LINE.match(stripped):
            continue
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue

        if out and out[-1] and not HEADING.match(stripped):
            prev = out[-1]
            prev_tail = prev[-1]
            starts_cjk = bool(re.match(r"[\u4e00-\u9fff（(《“]", stripped))
            if (
                len(prev) > 10
                and prev_tail not in SENTENCE_TAIL
                and starts_cjk
                and not HEADING.match(prev.strip())
            ):
                out[-1] = prev + stripped
                continue
        out.append(stripped)

    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _load_pdf(path: Path) -> list[tuple[int, str]]:
    try:
        import pymupdf as fitz  # PyMuPDF ≥1.24 推荐入口
    except ImportError:  # pragma: no cover
        try:
            import fitz
        except ImportError as exc:
            raise AppError(2003, "服务器缺少 PDF 解析依赖（PyMuPDF）") from exc

    pages: list[tuple[int, str]] = []
    with fitz.open(path) as doc:
        for idx, page in enumerate(doc, start=1):
            pages.append((idx, clean_text(page.get_text("text"))))
    return pages


def _load_docx(path: Path) -> list[tuple[int, str]]:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise AppError(2003, "服务器缺少 DOCX 解析依赖（python-docx）") from exc

    document = docx.Document(str(path))
    parts: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return [(None, clean_text("\n".join(parts)))]


def _load_text(path: Path) -> list[tuple[int, str]]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "gb18030"):
        try:
            return [(None, clean_text(raw.decode(encoding)))]
        except UnicodeDecodeError:
            continue
    raise AppError(2003, "文本编码无法识别，请转成 UTF-8 后重试")


def _strip_running_heads(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """页眉页脚：在 ≥60% 页面的首/尾两行重复出现的短行，判为噪声。"""
    if len(pages) < 3:
        return pages
    counter: dict[str, int] = {}
    for _, text in pages:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines[:2] + lines[-2:]:
            if len(line) <= 40:
                counter[line] = counter.get(line, 0) + 1

    threshold = max(2, int(len(pages) * 0.6))
    noise = {line for line, count in counter.items() if count >= threshold}
    if not noise:
        return pages

    cleaned: list[tuple[int, str]] = []
    for page_no, text in pages:
        kept = [ln for ln in text.split("\n") if ln.strip() not in noise]
        cleaned.append((page_no, "\n".join(kept)))
    return cleaned


def _strip_repeated_prefix(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """OCR 常把页眉与正文识别成同一行，按"首行公共前缀"剥掉页眉。

    例：`微信公众号：一研题本基础篇·概率论1.随机事件与概率` → `1.随机事件与概率`
    """
    if len(pages) < 3:
        return pages
    firsts = []
    for _, text in pages:
        for line in text.split("\n"):
            if line.strip():
                firsts.append(line.strip())
                break
    if len(firsts) < 3:
        return pages

    prefix = os.path.commonprefix(firsts).strip()
    if len(prefix) < 6:
        return pages

    cleaned: list[tuple[int, str]] = []
    for page_no, text in pages:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.strip():
                if line.strip().startswith(prefix):
                    lines[i] = line.strip()[len(prefix):].strip()
                break
        cleaned.append((page_no, "\n".join(lines)))
    return cleaned


def load_pages(path: Path, file_type: str) -> list[tuple[int, str]]:
    """返回 [(页码或 None, 文本)]。

    PDF 先读文字层；文字层缺失（扫描件）且开启 OCR 时，自动走 OCR 管线。
    """
    if not path.exists():
        raise AppError(1004, "文件不存在")

    if file_type == "pdf":
        pages = _strip_running_heads(_load_pdf(path))
        total = sum(len(text) for _, text in pages)
        avg = total / max(len(pages), 1)

        if pages and avg < 50:
            if not settings.ocr_enable:
                raise AppError(2003, "该文档没有文字层，请上传文字版")
            from app.services.parsing.ocr import ocr_pdf_pages

            logger.info("检测到扫描件，启动 OCR：%s（%d 页）", path.name, len(pages))
            pages = _strip_repeated_prefix(
                _strip_running_heads([(p, clean_text(t)) for p, t in ocr_pdf_pages(path)])
            )
            total = sum(len(text) for _, text in pages)
            if total / max(len(pages), 1) < 20:
                raise AppError(2003, "OCR 后仍无有效文字，请检查扫描清晰度或改用文字版")
        return pages
    if file_type == "docx":
        return _load_docx(path)
    if file_type in ("md", "txt"):
        return _load_text(path)
    raise AppError(2002, f"不支持的文件类型：{file_type}")


def stats(pages: list[tuple[int | None, str]]) -> dict:
    """语料体检指标。例题计数分两种口径：
    - examples_numbered：教材体例的"例 1 / 例 2"，用于核对编号连续性；
    - examples：更宽的"例 N / 例题 / 例："，用于判断语料里有没有可检索的例题。
    """
    chars = sum(len(text) for _, text in pages)
    page_count = len([p for p, _ in pages if p is not None]) or None
    numbered = sum(len(re.findall(r"例\s*\d+", text)) for _, text in pages)
    total_examples = sum(
        len(re.findall(r"(?:例\s*\d+|例题|例\s*[:：])", text)) for _, text in pages
    )
    return {
        "chars": chars,
        "page_count": page_count,
        "examples": total_examples,
        "examples_numbered": numbered,
    }
