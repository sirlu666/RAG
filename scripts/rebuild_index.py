"""重建索引（A）：从 chunks 表重新生成向量，向量库损坏时救命。

    python scripts/rebuild_index.py                # 全量
    python scripts/rebuild_index.py --doc doc_xxx  # 单文档

前提：关系库 chunks.content 是权威正文，本脚本不重新解析原文件。
若正文本身有问题，用 POST /api/docs/{id}/reindex 重新走解析链路。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.rag.embedder import embed_texts  # noqa: E402
from app.rag.indexer import build_metadata  # noqa: E402
from app.rag.vectorstore import get_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="从 chunks 表重建向量索引")
    parser.add_argument("--doc", help="只重建某个文档")
    parser.add_argument("--batch", type=int, default=64)
    args = parser.parse_args()

    init_db()
    store = get_store()
    total = 0

    with session_scope() as db:
        query = db.query(Chunk, Document).join(Document, Chunk.doc_id == Document.id)
        if args.doc:
            query = query.filter(Chunk.doc_id == args.doc)
        rows = query.order_by(Chunk.doc_id, Chunk.seq).all()
        if not rows:
            print(json.dumps({"rebuilt": 0, "message": "没有可重建的 chunk"}, ensure_ascii=False))
            return 0

        for doc_id in {doc.id for _, doc in rows}:
            store.delete_doc(doc_id)

        for start in range(0, len(rows), args.batch):
            batch = rows[start : start + args.batch]
            texts = [chunk.content for chunk, _ in batch]
            vectors = embed_texts(texts)
            ids, metas = [], []
            for chunk, doc in batch:
                draft = SimpleNamespace(
                    seq=chunk.seq,
                    content_type=chunk.content_type,
                    has_formula=chunk.has_formula,
                    page=chunk.page,
                )
                ids.append(chunk.id)
                metas.append(build_metadata(doc, draft, chunk.id))
            store.upsert(ids=ids, vectors=vectors, documents=texts, metadatas=metas)
            total += len(ids)

    print(json.dumps({"rebuilt": total, "vectors": store.count()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
