"""把 BlandAlpha/obsidian_math（GPL-3.0）整理成可入库语料。

源：knowledge/candidates/github/BlandAlpha_obsidian_math（Obsidian 笔记）
产出：knowledge/raw/obsidian_math/ 下的扁平 md（<章节>__<文件名>.md）

清洗规则（只动 Obsidian 语法，不碰数学内容）：
- 跳过 frontmatter 为 `属性: 目录` 的索引页与 <100 字的空页；
- [[链接#小节]] / [[链接|别名]] → 纯文本；
- > [!example] 等标注框 → **例** / **注** 等前缀，保留内容；
- 行内标签 #必考 删除（# 后带空格的 Markdown 标题不受影响）；
- $...$ / $$...$$ 公式原样保留。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "knowledge/candidates/github/BlandAlpha_obsidian_math"
OUT = ROOT / "knowledge/raw/obsidian_math"

CALLOUTS = {
    "example": "**例**",
    "note": "**注**",
    "important": "**重要**",
    "warning": "**注意**",
    "caution": "**注意**",
    "tip": "**提示**",
    "abstract": "**摘要**",
    "quote": "",
    "info": "**说明**",
    "question": "**问**",
    "failure": "",
    "bug": "",
}

WIKILINK = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]")
TAG = re.compile(r"(?<![\w$#])#[^\s#{}()\[\]]+")
CALLOUT = re.compile(r"^>\s*\[!\w+\][-\w]*\s*")


def _clean(text: str) -> str:
    # 1. frontmatter
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if m:
        text = text[m.end():]

    # 2. wikilinks：[[目标#小节|别名]] → 别名 / 目标·小节
    def link(m_: re.Match) -> str:
        target, alias = m_.group(1), m_.group(2)
        target = target.split("#")[0].strip()
        label = alias.strip() if alias and alias.strip() else target
        return label

    text = WIKILINK.sub(link, text)

    # 3. callouts
    lines = []
    for line in text.split("\n"):
        m_ = CALLOUT.match(line)
        if m_:
            name = re.search(r"\[!(\w+)\]", line)
            prefix = CALLOUTS.get(name.group(1).lower() if name else "", "") if name else ""
            rest = line[m_.end():].strip()
            lines.append(f"{prefix} {rest}".strip())
        else:
            lines.append(line)
    text = "\n".join(lines)

    # 4. 行内标签（不影响 "# " 标题）
    text = TAG.sub("", text)

    # 5. 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def main() -> int:
    if not SRC.exists():
        print(f"源目录不存在：{SRC}（先 git clone --depth 1 https://github.com/BlandAlpha/obsidian_math ）")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    written = skipped_dir = skipped_small = 0
    for md in sorted(SRC.rglob("*.md")):
        rel = md.relative_to(SRC)
        parts = [p for p in rel.parts[:-1] if not p.startswith((".", "assets"))]
        raw = md.read_text(encoding="utf-8")
        if re.match(r"^---\n(.*?)\n---", raw, flags=re.S) and "属性: 目录" in raw[:200]:
            skipped_dir += 1
            continue
        text = _clean(raw)
        if len(text) < 100:
            skipped_small += 1
            continue
        stem = "__".join(parts + [md.stem])
        (OUT / f"{stem}.md").write_text(text, encoding="utf-8")
        written += 1

    print(f"写入 {written} 篇 → {OUT}")
    print(f"跳过：索引页 {skipped_dir}，过短 {skipped_small}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
