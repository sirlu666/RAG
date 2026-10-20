"""把 kaoyan-math-ai 仓库里张宇 30 讲（高数）与线性代数的 PaddleOCR 全书原稿
整理成可入库语料。清洗逻辑与 prepare_prob_ocr 相同。
产出：knowledge/raw/zhangyu_full_ocr/<书名前缀>__<讲名>.md
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_prob_ocr import clean_ocr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "knowledge/candidates/github/patrick-andstar_kaoyan-math-ai"
OUT = ROOT / "knowledge/raw/zhangyu_full_ocr"

BOOKS = {"张宇基础30讲": "张宇30讲原稿", "张宇-线性代数": "张宇线代原稿"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for book, prefix in BOOKS.items():
        src = SRC / book / "paddleocr/_final"
        if not src.exists():
            print(f"缺目录：{src}")
            continue
        for md in sorted(src.glob("*.md")):
            text = clean_ocr(md.read_text(encoding="utf-8-sig", errors="ignore"))
            if len(text) < 300:
                print(f"  跳过（过短）: {book}/{md.name}")
                continue
            stem = re.sub(r"^\d+-", "", md.stem)
            (OUT / f"{prefix}__{stem}.md").write_text(text, encoding="utf-8")
            written += 1
    print(f"写入 {written} 篇 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
