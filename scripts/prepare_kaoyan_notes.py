"""把 patrick-andstar/kaoyan-math-ai 的张宇笔记整理成可入库语料。

源：knowledge/candidates/github/patrick-andstar_kaoyan-math-ai
产出：knowledge/raw/zhangyu_notes/ 下的扁平 md（<书名>__<讲名>.md）

取舍规则：
- 只取 张宇基础30讲 / 张宇-线性代数 / 张宇-概率论与数理统计 三个目录；
- 每讲优先取 `*-标准笔记.md`（正稿），没有才取同名草稿；
- 排除 .claude/.agents/工具/电子资源/test* 等非正文。
清洗规则与 prepare_obsidian_math 相同（frontmatter/callout/双链/标签）。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_obsidian_math import _clean  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "knowledge/candidates/github/patrick-andstar_kaoyan-math-ai"
OUT = ROOT / "knowledge/raw/zhangyu_notes"

BOOKS = ["张宇基础30讲", "张宇-线性代数", "张宇-概率论与数理统计"]


def main() -> int:
    if not SRC.exists():
        print(f"源目录不存在：{SRC}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    written = 0
    for book in BOOKS:
        book_dir = SRC / book
        if not book_dir.exists():
            print(f"缺目录：{book}")
            continue
        # 书目根目录下直接的 md（如 "N-第N讲-行列式.md"）
        for p in sorted(book_dir.glob("*.md")):
            if p.stem.startswith("test"):
                continue
            text = _clean(p.read_text(encoding="utf-8-sig", errors="ignore"))
            if len(text) < 200:
                continue
            (OUT / f"{book}__{p.stem}.md").write_text(text, encoding="utf-8")
            written += 1
        for lecture in sorted(p for p in book_dir.iterdir() if p.is_dir()):
            mds = list(lecture.glob("*.md"))
            if not mds:
                continue
            std = [p for p in mds if p.stem.endswith("-标准笔记")]
            pick = std[0] if std else mds[0]
            raw = pick.read_text(encoding="utf-8-sig", errors="ignore")
            text = _clean(raw)
            if len(text) < 200:
                print(f"  跳过（过短）: {lecture.name}")
                continue
            title = re.sub(r"^\d+-", "", lecture.name)
            out_name = f"{book}__{title}.md"
            (OUT / out_name).write_text(text, encoding="utf-8")
            written += 1

    print(f"写入 {written} 篇 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
