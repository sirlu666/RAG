"""索引读写（A 的职责）：关系库存正文，向量库存向量 + ChunkMetadata。

写入口径见 docs/A-接口与边界.md §4，字段只增不改。
"""

import logging

from types import SimpleNamespace
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.db.models import Chunk, Document, new_id
from app.rag.embedder import embed_texts
from app.rag.splitter import ChunkDraft
from app.rag.vectorstore import get_store

logger = logging.getLogger("mathrag.indexer")


def build_metadata(doc: Document, draft: ChunkDraft, chunk_id: str) -> dict:
    """Chroma 只接受 str/int/float/bool，None 字段必须省略。"""
    meta: dict = {
        "chunk_id": chunk_id,
        "user_id": doc.user_id,
        "kb_id": doc.kb_id,
        "doc_id": doc.id,
        "doc_name": doc.filename,
        "subject": "highschool_math",
        "content_type": draft.content_type,
        "seq": int(draft.seq),
        "has_formula": bool(draft.has_formula),
    }
    if draft.page is not None:
        meta["page"] = int(draft.page)
    return meta


def write_chunks(db: Session, doc: Document, drafts: list[ChunkDraft]) -> int:
    """把 chunk 写入关系库 + 向量库，返回条数。"""
    if not drafts:
        return 0

    texts = [d.content for d in drafts]
    vectors = embed_texts(texts)

    ids: list[str] = []
    metas: list[dict] = []
    rows: list[Chunk] = []

    for draft, vector in zip(drafts, vectors):
        chunk_id = new_id("ch")
        row = Chunk(
            id=chunk_id,
            doc_id=doc.id,
            kb_id=doc.kb_id,
            user_id=doc.user_id,
            seq=draft.seq,
            content=draft.content,
            content_type=draft.content_type,
            page=draft.page,
            char_start=draft.char_start,
            char_end=draft.char_end,
            token_count=draft.token_count,
            has_formula=draft.has_formula,
        )
        rows.append(row)
        ids.append(chunk_id)
        metas.append(build_metadata(doc, draft, chunk_id))

    db.add_all(rows)
    db.commit()

    try:
        get_store().upsert(ids=ids, vectors=vectors, documents=texts, metadatas=metas)
    except Exception as exc:
        # 向量写失败就回滚关系库记录，避免"关系库有、检索不到"的脏数据
        logger.exception("vector upsert failed doc=%s", doc.id)
        db.query(Chunk).filter(Chunk.doc_id == doc.id, Chunk.id.in_(ids)).delete(
            synchronize_session=False
        )
        db.commit()
        raise AppError(5000, "向量写入失败，请检查向量库配置") from exc

    logger.info("indexed doc=%s chunks=%d", doc.id, len(ids))
    return len(ids)


def delete_index(db: Session, doc_id: str) -> int:
    """先删向量再删记录：向量删失败会抛错，避免出现"库里还有、关系库没了"的孤儿数据。"""
    get_store().delete_doc(doc_id)
    removed = db.query(Chunk).filter(Chunk.doc_id == doc_id).delete(synchronize_session=False)
    db.commit()
    return int(removed or 0)


def count_chunks() -> int:
    return get_store().count()


# --------------------------------------------------------------------------
# 索引生命周期：重建 / 迁移（CLI 脚本只是这里的薄壳）
# --------------------------------------------------------------------------

def _doc_tags(doc: Document) -> dict:
    """文档级大模型标签（scripts/auto_label.py 产出），并入向量 metadata。"""
    raw = getattr(doc, "tags_json", None)
    if not raw:
        return {}
    try:
        import json

        return {k: v for k, v in json.loads(raw).items()}
    except Exception:
        return {}


def rebuild_vectors(
    db: Session,
    full: bool = False,
    doc_id: str | None = None,
    batch: int = 16,
    sleep: float = 0.0,
) -> dict:
    """从 chunks 表重建向量索引（幂等可续跑）。

    - 默认增量：只补向量库里缺失的 chunk，中断后重跑即可续；
    - full=True：先清空相关文档的向量再全量重建（换 embedding 模型后必须）；
    - 批间 sleep 用于规避 embedding API 限流；本地模型可设 0。
    """
    import time as _time

    store = get_store()
    have = set() if full else store.ids()

    query = db.query(Chunk, Document).join(Document, Chunk.doc_id == Document.id)
    if doc_id:
        query = query.filter(Chunk.doc_id == doc_id)
    rows = query.order_by(Chunk.doc_id, Chunk.seq).all()

    if full:
        for d_id in {doc.id for _, doc in rows}:
            store.delete_doc(d_id)

    todo = [(chunk, doc) for chunk, doc in rows if chunk.id not in have]
    rebuilt = 0
    for start in range(0, len(todo), batch):
        part = todo[start : start + batch]
        texts = [chunk.content for chunk, _ in part]
        vectors = embed_texts(texts)
        ids, metas = [], []
        for chunk, doc in part:
            draft = SimpleNamespace(
                seq=chunk.seq,
                content_type=chunk.content_type,
                has_formula=chunk.has_formula,
                page=chunk.page,
            )
            meta = build_metadata(doc, draft, chunk.id)
            meta.update(_doc_tags(doc))
            ids.append(chunk.id)
            metas.append(meta)
        store.upsert(ids=ids, vectors=vectors, documents=texts, metadatas=metas)
        rebuilt += len(ids)
        if sleep > 0 and start + batch < len(todo):
            _time.sleep(sleep)

    return {
        "rebuilt": rebuilt,
        "skipped_existing": max(len(rows) - rebuilt, 0),
        "vectors": store.count(),
        "backend": type(store).__name__,
    }


def migrate_local_vectors() -> dict:
    """把 LocalVectorStore 的存量向量整体迁入 Chroma（零 API 调用）。

    适用场景：从 provider=local/api 的旧 JSON 库切换到 Chroma 时，
    向量已经算好，直接搬运即可，无需重新 embedding。
    """
    import json

    from app.core.config import settings
    from app.rag.vectorstore import ChromaVectorStore

    local_path = settings.chroma_path / "local_store.json"
    if not local_path.exists():
        return {"migrated": 0, "message": "本地存量不存在，无需迁移"}

    items = json.loads(local_path.read_text(encoding="utf-8")).get("items", [])
    store = ChromaVectorStore()
    have = store.ids()
    todo = [it for it in items if it["id"] not in have]

    moved = 0
    for start in range(0, len(todo), 256):
        part = todo[start : start + 256]
        store.upsert(
            ids=[it["id"] for it in part],
            vectors=[it["v"] for it in part],
            documents=[it["d"] for it in part],
            metadatas=[it["m"] for it in part],
        )
        moved += len(part)

    return {"migrated": moved, "vectors": store.count()}
