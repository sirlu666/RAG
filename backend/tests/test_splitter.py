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


def test_heading_goes_with_next_block():
    raw = "## 3.1 函数的单调性\n\n设函数 f(x) 在区间 D 上连续，若对任意 x1<x2 都有 f(x1)<f(x2)，则称 f 在 D 上单调递增。"
    chunks = split_text(raw, max_tokens=600)
    assert len(chunks) == 1
    assert "3.1 函数的单调性" in chunks[0].content
    assert "单调递增" in chunks[0].content


def test_consecutive_paragraphs_grouped():
    raw = "\n\n".join(f"这是第 {i} 段关于函数性质的说明，内容足够长以便参与合并判断。" for i in range(1, 6))
    chunks = split_text(raw, max_tokens=600)
    assert len(chunks) <= 2


def test_exercise_type():
    raw = "习题 1.1\n求函数 f(x)=x^3-3x 的单调区间，并说明理由。"
    chunks = split_text(raw, max_tokens=600)
    assert chunks and chunks[0].content_type == "exercise"


def test_running_heads_removed():
    from app.services.parsing.loader import _strip_running_heads

    pages = [(i, f"人教版必修一\n第{i}页正文内容，讲函数的单调性定义。\n第 {i} 页") for i in range(1, 6)]
    cleaned = _strip_running_heads(pages)
    assert all("人教版必修一" not in text for _, text in cleaned)
    assert all("正文内容" in text for _, text in cleaned)
