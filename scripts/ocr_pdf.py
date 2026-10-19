"""扫描版 PDF → markdown（OCR 预处理，A 的离线工具）。

只做"图片 → 文本"，不写数据库；产物交给 ingest.py 入库。

    # 先小样：每本只跑 3 页
    python scripts/ocr_pdf.py --input "C:/Users/Lch/Desktop/数据" --out knowledge/raw/kaoyan_math1 --pages 1-3

    # 确认质量后全量
    python scripts/ocr_pdf.py --input "C:/Users/Lch/Desktop/数据" --out knowledge/raw/kaoyan_math1

公式：OCR_FORMULA=auto 时会尝试 pix2tex / Mathpix 兼容接口；都没有就保留 OCR 原文并在报告里标注。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.parsing.loader import clean_pages  # noqa: E402
from app.services.parsing.ocr import is_scanned_pdf, ocr_pdf_pages  # noqa: E402


def parse_pages(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        elif part:
            pages.append(int(part))
    return sorted(set(pages))


def safe_stem(name: str) -> str:
    for token in ("【", "】", "（", "）", "·", "：", " ", "."):
        name = name.replace(token, "_")
    return name.strip("_")[:100]


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描版 PDF OCR → markdown")
    parser.add_argument("--input", required=True, help="PDF 文件或目录")
    parser.add_argument("--out", default="knowledge/raw/kaoyan_math1")
    parser.add_argument("--pages", help="只跑指定页，如 1-3,7（默认全部）")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="已有文字层的 PDF 也强制 OCR")
    args = parser.parse_args()

    src = Path(args.input)
    pdfs = [src] if src.is_file() else sorted(src.glob("*.pdf"))
    if not pdfs:
        print(json.dumps({"error": f"{src} 下没有 PDF"}, ensure_ascii=False))
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = parse_pages(args.pages)
    stamp = datetime.now().isoformat(timespec="seconds")
    report = []

    for pdf in pdfs:
        scanned = is_scanned_pdf(pdf)
        if not scanned and not args.force:
            report.append({"file": pdf.name, "skipped": "已有文字层，直接用 loader 解析"})
            continue

        try:
            result = clean_pages(ocr_pdf_pages(pdf, dpi=args.dpi, pages=pages))
        except Exception as exc:
            report.append({"file": pdf.name, "error": str(exc)})
            continue

        body = "\n\n".join(
            f"## 第 {page_no} 页\n\n{text}" for page_no, text in result if text.strip()
        )
        if not body.strip():
            report.append({"file": pdf.name, "error": "OCR 结果为空"})
            continue

        header = (
            f"# {pdf.stem}\n\n"
            f"> 来源：本地扫描件 `{pdf.name}`（OCR 转换，非出版社原版）\n"
            f"> 转换：mathrag OCR · dpi={args.dpi} · {stamp}\n\n"
        )
        target = out_dir / f"{safe_stem(pdf.stem)}.md"
        target.write_text(header + body, encoding="utf-8")
        report.append(
            {
                "file": pdf.name,
                "out": str(target),
                "pages": len(result),
                "chars": len(body),
                "formula_lines": body.count("$$") // 2,
                "engine": settings.ocr_engine,
                "formula_mode": settings.ocr_formula,
            }
        )

    print(json.dumps({"out": str(out_dir), "results": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
