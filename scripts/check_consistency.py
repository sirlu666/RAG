"""一致性校验（A）：关系库 chunks 与向量库 id 是否对得上。

    python scripts/check_consistency.py

退出码：0 一致；1 有差异（各打印前 20 条）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Chunk  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.rag.vectorstore import get_store  # noqa: E402


def main() -> int:
    init_db()
    with session_scope() as db:
        db_ids = {row[0] for row in db.query(Chunk.id).all()}

    store = get_store()
    vector_ids = store.ids()

    missing_in_store = sorted(db_ids - vector_ids)
    orphan_in_store = sorted(vector_ids - db_ids)
    report = {
        "db_chunks": len(db_ids),
        "vector_chunks": len(vector_ids),
        "backend": type(store).__name__,
        "missing_in_store": missing_in_store[:20],
        "orphan_in_store": orphan_in_store[:20],
        "consistent": not missing_in_store and not orphan_in_store,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
