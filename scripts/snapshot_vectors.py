"""导出当前 Chroma collection 的向量快照（gzip JSON），供仓库分发。

    python scripts/snapshot_vectors.py   # 输出 data/vectors/<collection>.json.gz

逻辑在 app/rag/indexer.py::snapshot_vectors，本脚本只是 CLI 壳。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from app.rag.indexer import snapshot_vectors  # noqa: E402


def main() -> int:
    out = settings.chroma_path / "vectors" / f"{settings.chroma_collection}_bge-m3.json.gz"
    print(__import__("json").dumps(snapshot_vectors(out), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
