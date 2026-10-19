"""从中文维基教科书抓取数学语料（CC BY-SA），落地为 markdown。

    python scripts/fetch_wikibooks.py --prefix 高中数学/ --out knowledge/raw/wikibooks
    python scripts/fetch_wikibooks.py --prefix 高中数学/ 微积分学/ 线性代数/ --limit 80

为什么要这个脚本而不是手工复制：
- 语料要可复现：来源 URL、抓取时间、许可证全部写进 manifest.csv；
- wikitext 里的 <math> 要转成 $...$，否则入库后公式全丢；
- 模板/引用/文件/分类等噪声要清掉，不然切出来全是 "{{Infobox}}"。

许可证：维基教科书内容为 CC BY-SA。仅用于课程项目内部评测，manifest 保留署名与链接。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API = "https://zh.wikibooks.org/w/api.php"
UA = "MathRAG-course-project/1.0 (educational use; contact: team@local)"
SITE = "https://zh.wikibooks.org/wiki/"

TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}", re.S)
REF_RE = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
MEDIA_RE = re.compile(r"\[\[(?:File|Image|文件|图像|分类|Category):[^\]]*\]\]", re.I)
INTERLANG_RE = re.compile(r"\[\[[a-z]{2,3}:[^\]]*\]\]")
TAG_RE = re.compile(
    r"</?(?:div|span|p|br|center|small|big|font|table|tr|td|th|blockquote|u|s|sup|sub)[^>]*>",
    re.I,
)
MAGIC_RE = re.compile(r"__[A-Z]+__")


def _strip_templates(text: str) -> str:
    for _ in range(6):
        new = TEMPLATE_RE.sub("", text)
        if new == text:
            break
        text = new
    return text.replace("{{", "").replace("}}", "")


def _strip_tables(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("{|") or stripped.startswith("|}") or stripped.startswith("|-"):
            continue
        if stripped.startswith("!") or (stripped.startswith("|") and not stripped.startswith("|}")):
            cells = [c.strip() for c in stripped.lstrip("!|").split("!!")]
            if len(cells) == 1:
                cells = [c.strip() for c in stripped.lstrip("!|").split("||")]
            lines.append(" | ".join(c for c in cells if c))
            continue
        lines.append(line)
    return "\n".join(lines)


def wikitext_to_markdown(text: str) -> str:
    text = COMMENT_RE.sub("", text)
    text = REF_RE.sub("", text)
    text = MEDIA_RE.sub("", text)
    text = INTERLANG_RE.sub("", text)
    text = _strip_templates(text)
    text = _strip_tables(text)

    # 公式：块级 → $$...$$，行内 → $...$
    text = re.sub(
        r'<math\s+display\s*=\s*"?block"?\s*>(.*?)</math>',
        lambda m: f"\n\n$$\n{m.group(1).strip()}\n$$\n\n",
        text,
        flags=re.S,
    )
    text = re.sub(r"<math[^>]*>(.*?)</math>", r"$\1$", text, flags=re.S)

    text = TAG_RE.sub("", text)
    text = MAGIC_RE.sub("", text)

    # 列表必须先于标题处理：wikitext 的 # 是编号列表，标题是 =。
    text = re.sub(r"^\*+\s*", "- ", text, flags=re.M)
    text = re.sub(r"^#+\s*", "1. ", text, flags=re.M)

    # 标题：== X == → ## X（放在列表之后，避免被 # 规则吃掉）
    text = re.sub(
        r"^(={2,6})\s*(.+?)\s*\1\s*$",
        lambda m: "#" * (len(m.group(1)) - 1) + " " + m.group(2),
        text,
        flags=re.M,
    )

    # 链接与强调
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''(.+?)'''", r"**\1**", text, flags=re.S)
    text = re.sub(r"''(.+?)''", r"*\1*", text, flags=re.S)
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)

    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def api_get(client: httpx.Client, params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    for attempt in range(3):
        try:
            resp = client.get(API, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # 网络抖动重试
            if attempt == 2:
                raise SystemExit(f"请求维基教科书失败：{exc}")
            time.sleep(1.5 * (attempt + 1))
    return {}


def list_pages(client: httpx.Client, prefix: str, limit: int) -> list[str]:
    titles: list[str] = []
    cont: dict = {}
    while len(titles) < limit:
        data = api_get(
            client,
            {
                "action": "query",
                "list": "allpages",
                "apprefix": prefix,
                "apnamespace": 0,
                "aplimit": 50,
                **cont,
            },
        )
        titles.extend(p["title"] for p in data.get("query", {}).get("allpages", []))
        if "continue" not in data:
            break
        cont = data["continue"]
    return titles[:limit]


def fetch_wikitext(client: httpx.Client, titles: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for start in range(0, len(titles), 40):
        batch = titles[start : start + 40]
        data = api_get(
            client,
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": "|".join(batch),
                "redirects": 1,
            },
        )
        for page in data.get("query", {}).get("pages", []):
            if "missing" in page:
                continue
            try:
                out[page["title"]] = page["revisions"][0]["slots"]["main"]["content"]
            except (KeyError, IndexError):
                continue
        time.sleep(0.3)
    return out


def safe_name(title: str) -> str:
    name = title.replace("/", "__").replace("\\", "_").replace(":", "：")
    return re.sub(r'[<>:"|?*\s]+', "_", name)[:120] + ".md"


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取中文维基教科书数学语料")
    parser.add_argument("--prefix", nargs="+", default=["高中数学/"], help="页面前缀（可多个）")
    parser.add_argument("--out", default="knowledge/raw/wikibooks")
    parser.add_argument("--limit", type=int, default=60, help="每个前缀最多抓多少页")
    parser.add_argument("--max-chars", type=int, default=20000, help="单页最大保留字符数")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    written = []
    with httpx.Client(headers={"User-Agent": UA}) as client:
        for prefix in args.prefix:
            titles = [
                t for t in list_pages(client, prefix, args.limit)
                if t != prefix.rstrip("/") and not t.endswith("使用技巧")
            ]
            pages = fetch_wikitext(client, titles)
            for title, wikitext in pages.items():
                body = wikitext_to_markdown(wikitext)
                if len(body) < 200:
                    continue
                body = body[: args.max_chars]
                header = (
                    f"# {title}\n\n"
                    f"> 来源：{SITE}{title.replace(' ', '_')}（中文维基教科书，CC BY-SA）\n"
                    f"> 抓取时间：{now}\n\n"
                )
                path = out_dir / safe_name(title)
                path.write_text(header + body, encoding="utf-8")
                written.append(
                    {
                        "file": path.name,
                        "title": title,
                        "url": SITE + title.replace(" ", "_"),
                        "license": "CC BY-SA",
                        "retrieved_at": now,
                        "chars": len(body),
                    }
                )

    manifest = Path(args.out) / "manifest.csv"
    fields = ["file", "title", "url", "license", "retrieved_at", "chars"]
    rows: dict[str, dict] = {}
    if manifest.exists():
        with manifest.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("file"):
                    rows[row["file"]] = row  # 多次抓取要合并，不能覆盖上次的来源记录
    for item in written:
        rows[item["file"]] = item

    with manifest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({k: rows[key].get(k, "") for k in fields})

    print(
        json.dumps(
            {
                "pages": len(written),
                "total_chars": sum(w["chars"] for w in written),
                "out": str(out_dir),
                "manifest": str(manifest),
                "sample": [w["title"] for w in written[:8]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
