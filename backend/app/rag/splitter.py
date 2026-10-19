"""公式保护切片 + 例题完整性分组。

四步（口径见 docs/A-接口与边界.md §5）：
1. 公式替换为 @@MATH_i@@，保证切点永不落在公式内部；
2. 按空行/标题切块，短标题作为下一块的前缀（不单独成 chunk）；
3. 把"例 N + 解/证明/答案 + 点评"合并成一个语义单元，一道例题不被拆开；
4. 单元超长时按句末递归切，带 overlap；最后还原公式。
"""

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.core.config import settings

MATH_PATTERNS = [
    re.compile(r"\$\$[\s\S]*?\$\$"),
    re.compile(r"\\\[[\s\S]*?\\\]"),
    re.compile(r"\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\}"),
    re.compile(r"(?<!\$)\$(?!\$)[^$\n]{1,300}?\$(?!\$)"),
]

HEADING_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百]+[章节讲]|[0-9]+(\.[0-9]+)+\s*\S|[0-9]+\s*[、.．]\s*\S)"
)
UNIT_START_RE = re.compile(r"^\s*(例题?|例\s*\d+|【例】|习题|练习|随堂练习|课后练习|练一练)")
CONTINUATION_RE = re.compile(r"^\s*(解|证明|分析|答案|点评|注|说明|∴|所以)\s*[:：]?")

TYPE_RULES = [
    ("exercise", re.compile(r"^\s*(习题|练习|随堂练习|课后练习|练一练)")),
    ("example", re.compile(r"^\s*(例题?|例\s*\d+|【例】)")),
    ("theory", re.compile(r"^\s*(定理|定义|性质|推论|引理|公理|公式)")),
]

SENTENCE_END = "。！？；\n"


@dataclass
class ChunkDraft:
    content: str
    content_type: str = "other"
    page: int | None = None
    char_start: int = 0
    char_end: int = 0
    has_formula: bool = False
    token_count: int = 0
    seq: int = 0
    extra: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """中文约 1.6 字/token，英文按 4 字符/token 近似。只用于切片控制。"""
    if not text:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    other = len(text) - cjk
    return max(1, int(cjk / 1.6 + other / 4))


def protect_math(text: str) -> tuple[str, list[str]]:
    formulas: list[str] = []

    def _sub(m: re.Match) -> str:
        formulas.append(m.group(0))
        return f"@@MATH_{len(formulas) - 1}@@"

    protected = text
    for pattern in MATH_PATTERNS:
        protected = pattern.sub(_sub, protected)
    return protected, formulas


def restore_math(text: str, formulas: list[str]) -> str:
    if not formulas:
        return text
    return re.sub(r"@@MATH_(\d+)@@", lambda m: formulas[int(m.group(1))], text)


def detect_type(block: str) -> str:
    head = block.strip()[:40]
    for name, pattern in TYPE_RULES:
        if pattern.match(head):
            return name
    # 只认"开头就是在解题"的块，避免正文里出现"证明"二字就被判成例题
    if re.match(r"^\s*(证明|推导|求解|解\s*[:：])", block.strip()):
        return "example"
    return "concept"


def _split_blocks(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    buf: list[str] = []

    for line in lines:
        stripped = line.strip()
        if HEADING_RE.match(stripped) and buf and len("\n".join(buf).strip()) > 60:
            blocks.append("\n".join(buf).strip())
            buf = [line]
            continue
        if not stripped:
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
            continue
        buf.append(line)
    if buf:
        blocks.append("\n".join(buf).strip())
    return [b for b in blocks if b]


def _group_units(blocks: list[str], max_tokens: int) -> list[tuple[str, str]]:
    """把块合并成"语义单元"：短标题做前缀，例题连同解答与点评。"""
    units: list[tuple[str, str]] = []
    cur: list[str] = []
    cur_type = "other"
    pending_heading = ""

    def flush() -> None:
        nonlocal cur
        if cur:
            units.append((cur_type, "\n\n".join(cur)))
            cur = []

    for block in blocks:
        if len(block) < 40 and HEADING_RE.match(block):
            pending_heading = block
            continue
        if pending_heading:
            block = f"{pending_heading}\n{block}"
            pending_heading = ""

        block_type = detect_type(block)

        if not cur:
            cur, cur_type = [block], block_type
            continue
        if UNIT_START_RE.match(block):
            flush()
            cur, cur_type = [block], block_type
            continue
        if CONTINUATION_RE.match(block) and cur_type in ("example", "exercise"):
            cur.append(block)
            continue
        fits = estimate_tokens("\n\n".join(cur + [block])) <= int(max_tokens * 0.85)
        # 例题/习题的解答里常夹着只含公式的段落（会被判成 concept），必须并回去
        if fits and (
            block_type == cur_type
            or (cur_type == "example" and block_type in ("concept", "other"))
        ):
            cur.append(block)
            continue
        flush()
        cur, cur_type = [block], block_type

    flush()
    if pending_heading:
        units.append(("concept", pending_heading))
    return units


def _hard_split(block: str, max_chars: int, overlap: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    pieces: list[str] = []
    start, n = 0, len(block)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = block[start:end]
            cut = max(window.rfind(ch) for ch in SENTENCE_END)
            if cut > max_chars * 0.6:
                end = start + cut + 1
        pieces.append(block[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


def split_text(
    text: str,
    page: int | None = None,
    start_seq: int = 0,
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[ChunkDraft]:
    max_tokens = max_tokens or settings.chunk_size
    overlap_tokens = overlap_tokens or settings.chunk_overlap
    max_chars = int(max_tokens * 1.6)
    overlap_chars = int(overlap_tokens * 1.6)

    protected, formulas = protect_math(text)
    drafts: list[ChunkDraft] = []
    cursor = 0
    seq = start_seq

    for unit_type, unit in _group_units(_split_blocks(protected), max_tokens):
        for piece in _hard_split(unit, max_chars, overlap_chars):
            content = restore_math(piece, formulas).strip()
            if len(content) < 20:
                cursor += len(piece)
                continue
            probe = content[:30]
            idx = text.find(probe, cursor) if len(probe) >= 20 else -1
            char_start = idx if idx >= 0 else cursor
            drafts.append(
                ChunkDraft(
                    content=content,
                    content_type=unit_type,
                    page=page,
                    char_start=char_start,
                    char_end=char_start + len(content),
                    has_formula=bool(re.search(r"\$|\\begin\{", content)),
                    token_count=estimate_tokens(content),
                    seq=seq,
                )
            )
            seq += 1
            cursor = char_start + len(content)

    return drafts


def split_pages(pages: Iterable[tuple[int | None, str]]) -> list[ChunkDraft]:
    """按页切片，页码随 chunk 保留（前端引用可跳转）。"""
    all_drafts: list[ChunkDraft] = []
    for page_no, text in pages:
        drafts = split_text(text, page=page_no, start_seq=len(all_drafts))
        all_drafts.extend(drafts)
    return all_drafts
