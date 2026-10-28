"""批量入库 / 解析体检（A 的离线脚本）。

先体检，再入库：
    python scripts/ingest.py --dir knowledge/raw --dry-run
    python scripts/ingest.py --dir knowledge/raw --kb 公共教材 --user dev

--dry-run 不碰数据库，只报告：字符数、页数、"例 N" 数量、chunk 数、公式占比。
Gate 0 的语料验收就用它：≥5 万汉字、随机 5 页无乱码、≥30 个"例 N"。

目标目录与归属可指定（A-01 要求）：
    python scripts/ingest.py --dir knowledge/raw --kb 考研数学 --user 张三 \
        --db .tmp/c-integration/app.db --upload-dir .tmp/c-integration/uploads \
        --chroma-dir .tmp/c-integration/chroma

目标路径经环境变量在导入 app 之前注入，因此与默认 data/ 完全隔离，可重复执行。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# --- 必须在导入 app.* 之前注入目标路径（session 的 engine 在导入时绑定路径）---
_parser = argparse.ArgumentParser(description="MathRAG 语料体检与批量入库")
_parser.add_argument("--dir", default="knowledge/raw", help="语料目录")
_parser.add_argument("--kb", default="公共教材", help="知识库名称（非 dry-run 时使用）")
_parser.add_argument("--user", default="dev", help="归属用户（用户名，存在则复用）")
_parser.add_argument("--db", default=None, help="目标 SQLite 路径（默认 data/app.db）")
_parser.add_argument("--upload-dir", default=None, help="目标上传目录（默认 data/uploads）")
_parser.add_argument("--chroma-dir", default=None, help="目标向量目录（默认 data/chroma）")
_parser.add_argument("--dry-run", action="store_true", help="只体检，不写数据库")
_args, _unknown = _parser.parse_known_args()

_ROOT = Path(__file__).resolve().parents[1]
if _args.db:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(_args.db).as_posix()}"
if _args.upload_dir:
    os.environ["UPLOAD_DIR"] = str(_args.upload_dir)
if _args.chroma_dir:
    os.environ["CHROMA_DIR"] = str(_args.chroma_dir)

sys.path.insert(0, str(_ROOT / "backend"))

from app.core.exceptions import AppError  # noqa: E402
from app.rag.splitter import split_pages  # noqa: E402
from app.services.parsing.loader import load_pages, stats  # noqa: E402

SUPPORTED = {".pdf", ".docx", ".md", ".txt"}


def inspect_file(path: Path, chunk_size: int | None = None) -> dict:
    pages = load_pages(path, path.suffix.lstrip(".").lower())
    drafts = split_pages(pages)
    info = stats(pages)
    tokens = [d.token_count for d in drafts] or [0]
    formula = sum(1 for d in drafts if d.has_formula)
    return {
        "file": path.name,
        "chars": info["chars"],
        "pages": info["page_count"],
        "examples": info["examples"],
        "examples_numbered": info["examples_numbered"],
        "chunks": len(drafts),
        "avg_tokens": round(sum(tokens) / len(tokens), 1),
        "max_tokens": max(tokens),
        "formula_ratio": round(formula / max(len(drafts), 1), 3),
        "types": {t: sum(1 for d in drafts if d.content_type == t) for t in
                  ("concept", "example", "exercise", "theory", "other")},
    }


def dry_run(root: Path) -> int:
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED)
    if not files:
        print(json.dumps({"error": f"{root} 下没有可解析文件"}, ensure_ascii=False))
        return 1

    reports, failures = [], []
    for path in files:
        try:
            reports.append(inspect_file(path))
        except AppError as exc:
            failures.append({"file": path.name, "code": exc.code, "error": exc.message})
        except Exception as exc:  # pragma: no cover
            failures.append({"file": path.name, "error": str(exc)})

    total_chars = sum(r["chars"] for r in reports)
    total_examples = sum(r["examples"] for r in reports)
    total_numbered = sum(r["examples_numbered"] for r in reports)
    verdict = {
        "files": len(files),
        "parsed": len(reports),
        "total_chars": total_chars,
        "total_examples": total_examples,
        "total_examples_numbered": total_numbered,
        # Gate 0：字符数 + 例题数（宽口径）+ 无解析失败
        "gate0_pass": total_chars >= 50000 and total_examples >= 30 and not failures,
    }
    print(json.dumps({"verdict": verdict, "files": reports, "failures": failures},
                     ensure_ascii=False, indent=2))
    return 0 if verdict["gate0_pass"] else 2


def ingest(root: Path, kb_name: str, username: str) -> int:
    from app.db.models import KnowledgeBase, User
    from app.db.session import ensure_dirs, init_db, session_scope
    from app.services import doc_service

    ensure_dirs()
    init_db()
    results = []

    with session_scope() as db:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username)
            db.add(user)
            db.commit()
            db.refresh(user)

        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user.id, KnowledgeBase.name == kb_name
        ).first()
        if kb is None:
            kb = KnowledgeBase(user_id=user.id, name=kb_name)
            db.add(kb)
            db.commit()
            db.refresh(kb)

        for path in sorted(p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED):
            try:
                doc, task = doc_service.create_document(
                    db, user, kb.id, path.name, path.read_bytes()
                )
                results.append({"file": path.name, "doc_id": doc.id, "task_id": task.id})
            except AppError as exc:
                results.append({"file": path.name, "code": exc.code, "error": exc.message})

    for item in results:
        if "doc_id" in item:
            doc_service.run_ingest(item["doc_id"])

    print(json.dumps({"kb": kb_name, "user": username, "results": results},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    root = Path(_args.dir)
    if not root.exists():
        print(json.dumps({"error": f"目录不存在：{root}"}, ensure_ascii=False))
        return 1
    return dry_run(root) if _args.dry_run else ingest(root, _args.kb, _args.user)


if __name__ == "__main__":
    raise SystemExit(main())
