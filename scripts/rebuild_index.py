"""重建索引（A）：从 chunks 表重新生成向量，向量库损坏时救命。

    python scripts/rebuild_index.py                # 增量：只补缺失向量（可中断续跑）
    python scripts/rebuild_index.py --full         # 全量：清空后重建（换 embedding 模型后必须）
    python scripts/rebuild_index.py --doc doc_xxx  # 单文档

逻辑在 app/rag/indexer.py::rebuild_vectors，本脚本只是 CLI 壳。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import init_db, session_scope  # noqa: E402
from app.rag.indexer import rebuild_vectors  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="从 chunks 表重建向量索引（可续跑）")
    parser.add_argument("--doc", help="只重建某个文档")
    parser.add_argument("--full", action="store_true", help="清空后全量重建")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--sleep", type=float, default=0.5, help="批间休眠秒数（防限流）")
    args = parser.parse_args()

    init_db()
    with session_scope() as db:
        result = rebuild_vectors(
            db, full=args.full, doc_id=args.doc, batch=args.batch, sleep=args.sleep
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
