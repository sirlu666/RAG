"""公式保护切片。

核心思路（见 docs/A-接口与边界.md §5）：
1. 先把公式替换成占位符 @@MATH_i@@，保证切分点永远不会落在公式内部；
2. 按空行/标题切成语义块，识别"例/习题/定义/定理"，让一道例题不被拆散；
3. 块超长时按句末递归切，带 overlap；
4. 最后还原占位符。
"""

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.core.config import settings

MATH_PATTERNS = [
    re.compile(r"\$\$[\s\S]*?\$\$"),          # $$...$$
    re.compile(r"\\\[[\s\S]*?\\\]"),          # \[...\]
    re.compile(r"\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\}"),  # 环境
    re.compile(r"(?<!\$)\$(?!\$)[^$\n]{1,300}?\$(?!\$)"),  # $...$
]

BLOCK_TYPE_RULES = [
    ("example", re.compile(r"^\s*(例题?|例\s*\d+|【例】)")),
    ("exercise", re.compile(r"^\s*(习题|练习|随堂练习|课后练习|练一练)")),
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
    """中文约 1.6 字/token，英文按空格词近似。只用于切片控制，不追求精确。"""
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
    for name, pattern in BLOCK_TYPE_RULES:
        if pattern.match(head):
            return name
    if re.search(r"(证明|推导|求解|解[:：])", block[:120]):
        return "example"
    return "concept"


def _split_blocks(text: str) -> list[str]:
    """按空行与常见标题行切块，保留标题与正文的从属关系。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    buf: list[str] = []

    heading_re = re.compile(r"^\s*(第[一二三四五六七八九十百]+[章节讲]|[0-9]+(\.[0-9]+)*\s+\S|例\s*\d+|习题)")

    for line in lines:
        stripped = line.strip()
        if heading_re.match(stripped) and buf and len("".join(buf).strip()) > 80:
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


def _hard_split(block: str, max_chars: int, overlap: int) -> list[str]:
    """在句末切；找不到句末时按窗口硬切。"""
    if len(block) <= max_chars:
        return [block]

    pieces: list[str] = []
    start = 0
    n = len(block)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = block[start:end]
            cut = max(window.rfind(ch) for ch in SENTENCE_END)
            if cut > max_chars * 0.5:
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
    """把一页（或整篇）文本切成 chunk 草案。"""
    max_tokens = max_tokens or settings.chunk_size
    overlap_tokens = overlap_tokens or settings.chunk_overlap
    max_chars = int(max_tokens * 1.6)
    overlap_chars = int(overlap_tokens * 1.6)

    protected, formulas = protect_math(text)
    drafts: list[ChunkDraft] = []
    cursor = 0
    seq = start_seq

    for block in _split_blocks(protected):
        block_type = detect_type(restore_math(block, formulas))
        for piece in _hard_split(block, max_chars, overlap_chars):
            content = restore_math(piece, formulas).strip()
            if len(content) < 20:
                cursor += len(piece)
                continue
            idx = text.find(content[:30], cursor) if len(content) >= 30 else -1
            char_start = idx if idx >= 0 else cursor
            drafts.append(
                ChunkDraft(
                    content=content,
                    content_type=block_type,
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
    """按页切片，页码随 chunk 一起保留（引用可跳转）。"""
    all_drafts: list[ChunkDraft] = []
    for page_no, text in pages:
        drafts = split_text(text, page=page_no, start_seq=len(all_drafts))
        all_drafts.extend(drafts)
    return all_drafts
