"""把存量向量迁入 Chroma（零 API 调用）。

    python scripts/migrate_vectors.py                                   # 旧 JSON 库（local_store.json）
    python scripts/migrate_vectors.py data/chroma/vectors/math_chunks_bge-m3.json.gz
                                                                        # 仅已有配套关系库时使用；不能与新 ingest 的 ID 混用

逻辑在 app/rag/indexer.py::migrate_local_vectors，本脚本只是 CLI 壳。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.rag.indexer import migrate_local_vectors  # noqa: E402


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(migrate_local_vectors(source), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
