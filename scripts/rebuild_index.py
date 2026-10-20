"""重建索引（A）：从 chunks 表重新生成向量，向量库损坏时救命。

    python scripts/rebuild_index.py                # 增量：只补缺失的向量（可中断续跑）
    python scripts/rebuild_index.py --full         # 全量：清空后重建
    python scripts/rebuild_index.py --doc doc_xxx  # 单文档

前提：关系库 chunks.content 是权威正文，本脚本不重新解析原文件。
若正文本身有问题，用 POST /api/docs/{id}/reindex 重新走解析链路。

特性：
- 幂等可续跑：已存在于向量库的 chunk 默认跳过，中断后重跑即可续；
- 节流：批间休眠，避免触发 embedding API 限流；
- 元数据增强：把 documents.tags_json（大模型自动打标）并入向量 metadata，
  供 B 检索路由、C 前端筛选。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.rag.embedder import embed_texts  # noqa: E402
from app.rag.indexer import build_metadata  # noqa: E402
from app.rag.vectorstore import get_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="从 chunks 表重建向量索引（可续跑）")
    parser.add_argument("--doc", help="只重建某个文档")
    parser.add_argument("--full", action="store_true", help="清空后全量重建")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--sleep", type=float, default=0.5, help="批间休眠秒数（防限流）")
    args = parser.parse_args()

    init_db()
    store = get_store()
    have = set() if args.full else store.ids()

    total = skipped = 0
    with session_scope() as db:
        query = db.query(Chunk, Document).join(Document, Chunk.doc_id == Document.id)
        if args.doc:
            query = query.filter(Chunk.doc_id == args.doc)
        rows = query.order_by(Chunk.doc_id, Chunk.seq).all()
        if not rows:
            print(json.dumps({"rebuilt": 0, "message": "没有可重建的 chunk"}, ensure_ascii=False))
            return 0

        # 文档级标签（大模型自动打标，见 scripts/auto_label.py）
        doc_tags: dict[str, dict] = {}
        for _, doc in rows:
            if doc.id not in doc_tags:
                raw = getattr(doc, "tags_json", None)
                doc_tags[doc.id] = json.loads(raw) if raw else {}

        if args.full:
            for doc_id in {doc.id for _, doc in rows}:
                store.delete_doc(doc_id)

        todo = [(chunk, doc) for chunk, doc in rows if chunk.id not in have]
        print(f"待重建 {len(todo)} / {len(rows)}（已有 {len(have)} 条跳过）")

        for start in range(0, len(todo), args.batch):
            batch = todo[start : start + args.batch]
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
                meta = build_metadata(doc, draft, chunk.id)
                meta.update(doc_tags.get(doc.id, {}))
                ids.append(chunk.id)
                metas.append(meta)
            store.upsert(ids=ids, vectors=vectors, documents=texts, metadatas=metas)
            total += len(ids)
            if start + args.batch < len(todo) and args.sleep > 0:
                time.sleep(args.sleep)

    skipped = len(rows) - total if rows else 0
    print(json.dumps(
        {"rebuilt": total, "skipped_existing": max(skipped, 0),
         "vectors": store.count(), "backend": type(store).__name__},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
