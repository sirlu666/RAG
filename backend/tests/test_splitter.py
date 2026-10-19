"""A 的单元测试：切片与清洗。

跑法：cd backend && python -m pytest -q
"""

from app.rag.splitter import ChunkDraft, detect_type, protect_math, restore_math, split_text
from app.services.parsing.loader import clean_text


def test_protect_and_restore_roundtrip():
    raw = "已知 $f(x)=x^2$，求 $$\\int_0^1 x\\,dx$$ 的值。"
    protected, formulas = protect_math(raw)
    assert "$" not in protected
    assert "@@MATH_0@@" in protected
    assert restore_math(protected, formulas) == raw


def test_formula_never_split():
    raw = "\n\n".join(
        f"例{i} 已知函数 $f(x)=x^{{{i}}}+2x$，讨论其单调性。解：先配方得 "
        f"$$f(x)=(x+1)^{{{i}}}-1$$ 再根据对称轴判断。"
        for i in range(1, 30)
    )
    chunks: list[ChunkDraft] = split_text(raw, max_tokens=80, overlap_tokens=20)
    assert len(chunks) > 5
    for chunk in chunks:
        assert "@@MATH" not in chunk.content
        assert chunk.content.count("$") % 2 == 0, chunk.content[:80]


def test_example_block_kept_whole():
    raw = "例 1 求函数 f(x)=x^2+2x 的单调区间。\n\n解：配方得 f(x)=(x+1)^2-1，对称轴为 x=-1。"
    chunks = split_text(raw, max_tokens=400)
    assert len(chunks) == 1
    assert "解：" in chunks[0].content
    assert chunks[0].content_type == "example"


def test_detect_type():
    assert detect_type("例 3 已知函数 f(x)") == "example"
    assert detect_type("定理 2（介值定理）") == "theory"
    assert detect_type("习题 1.1") == "exercise"


def test_chunk_size_bounded():
    raw = "函数在区间上的单调性可以通过导数符号判断。" * 400
    chunks = split_text(raw, max_tokens=100, overlap_tokens=20)
    assert chunks
    assert all(len(c.content) <= 400 for c in chunks)
    assert all(c.token_count <= 260 for c in chunks)


def test_clean_text_merges_hard_wrap():
    raw = "第一页内容\n\n已知该函数在给定区间上单调\n递增，且满足导数大于零。\n\n12\n"
    cleaned = clean_text(raw)
    assert "单调递增" in cleaned.replace("\n", "")
    assert "\n12\n" not in cleaned
