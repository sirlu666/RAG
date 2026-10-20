"""把 LocalVectorStore（local_store.json）里的存量向量迁移进 Chroma。

背景：切换 VECTOR_BACKEND=chroma 时，之前算好的向量无需重新调用
embedding API——直接从 JSON 存量搬运（id/向量/正文/metadata 原样保留）。

    python scripts/migrate_vectors.py            # 迁移所有缺失的条目
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from app.rag.vectorstore import ChromaVectorStore  # noqa: E402

LOCAL = settings.chroma_path / "local_store.json"


def main() -> int:
    if not LOCAL.exists():
        print(f"找不到本地存量：{LOCAL}")
        return 1
    items = json.loads(LOCAL.read_text(encoding="utf-8")).get("items", [])
    if not items:
        print("本地存量为空，无迁移对象")
        return 1

    store = ChromaVectorStore()
    have = store.ids()
    todo = [it for it in items if it["id"] not in have]
    print(f"存量 {len(items)}，Chroma 已有 {len(have)}，待迁移 {len(todo)}")

    batch = 256
    moved = 0
    for start in range(0, len(todo), batch):
        chunk = todo[start : start + batch]
        store.upsert(
            ids=[it["id"] for it in chunk],
            vectors=[it["v"] for it in chunk],
            documents=[it["d"] for it in chunk],
            metadatas=[it["m"] for it in chunk],
        )
        moved += len(chunk)
        print(f"  已迁 {moved}/{len(todo)}")

    print(f"完成：Chroma 现有 {store.count()} 条向量")
    return 0


if __name__ == "__main__":
    sys.exit(main())
