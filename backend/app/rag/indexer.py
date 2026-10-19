"""索引读写（A 的职责）：关系库存正文，向量库存向量 + ChunkMetadata。

写入口径见 docs/A-接口与边界.md §4，字段只增不改。
"""

import logging

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
