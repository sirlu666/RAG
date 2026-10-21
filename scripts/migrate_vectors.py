"""把 LocalVectorStore（local_store.json）里的存量向量迁移进 Chroma。

背景：切换 VECTOR_BACKEND=chroma 时，之前算好的向量无需重新调用
embedding API——直接从 JSON 存量搬运（id/向量/正文/metadata 原样保留）。

逻辑在 app/rag/indexer.py::migrate_local_vectors，本脚本只是 CLI 壳。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.rag.indexer import migrate_local_vectors  # noqa: E402


def main() -> int:
    print(json.dumps(migrate_local_vectors(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
