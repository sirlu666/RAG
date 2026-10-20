"""把 kaoyan-math-ai 仓库里张宇概率论的 PaddleOCR 全书原稿整理成可入库语料。

源：张宇-概率论与数理统计/paddleocr/_final/*.md（作者对整本 PDF 的 OCR，
含完整例题与 LaTeX 公式，比"标准笔记"多约一倍内容）
产出：knowledge/raw/zhangyu_prob_ocr/<讲名>.md

清洗（复用 prepare_obsidian_math._clean，另加）：
- 剥 `<!-- page: N -->` 页标记与 `![[...]]` 图片嵌入；
- 剥作者自己的 QA 标注 `%% ... %%`；
- 文件名加"原稿"后缀，避免与已入库的标准笔记同名冲突。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_obsidian_math import _clean  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "knowledge/candidates/github/patrick-andstar_kaoyan-math-ai/张宇-概率论与数理统计/paddleocr/_final"
OUT = ROOT / "knowledge/raw/zhangyu_prob_ocr"

PAGE_MARK = re.compile(r"<!--\s*page:\s*\d+\s*-->")
IMG_EMBED = re.compile(r"!\[\[[^\]]*\]\]")
QA_MARK = re.compile(r"\s*%%[^%]*%%")


def clean_ocr(text: str) -> str:
    text = _clean(text)          # frontmatter / wikilink / callout / 标签
    text = IMG_EMBED.sub("", text)
    text = QA_MARK.sub("", text)
    text = PAGE_MARK.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main() -> int:
    if not SRC.exists():
        print(f"源目录不存在：{SRC}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    written = 0
    for md in sorted(SRC.glob("*.md")):
        text = clean_ocr(md.read_text(encoding="utf-8-sig", errors="ignore"))
        if len(text) < 300:
            print(f"  跳过（过短）: {md.name}")
            continue
        stem = re.sub(r"^\d+-", "", md.stem)  # 01-第1讲-xxx → 第1讲-xxx
        (OUT / f"张宇-概率论原稿__{stem}.md").write_text(text, encoding="utf-8")
        written += 1

    print(f"写入 {written} 篇 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
