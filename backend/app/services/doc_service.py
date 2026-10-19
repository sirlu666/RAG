"""文档生命周期：上传 → 解析 → 切片 → 向量化 → 可检索；以及删除 / 重建。

并发约定：同一时刻只允许一个入库任务（单写锁），避免 SQLite 写锁与向量库并发写。
"""

import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models import Document, IngestTask, KnowledgeBase, User, new_id
from app.db.session import session_scope
from app.rag.indexer import delete_index, write_chunks
from app.rag.splitter import split_pages
from app.services.parsing.loader import load_pages

logger = logging.getLogger("mathrag.doc")

ALLOWED_SUFFIX = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".txt": "txt"}
_INGEST_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_default_kb(db: Session, user: User) -> KnowledgeBase:
    """临时兜底：知识库创建属于 C 的 /api/kbs。这里只为 A 单独联调时能用。"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user.id).first()
    if kb is None:
        kb = KnowledgeBase(user_id=user.id, name="默认知识库")
        db.add(kb)
        db.commit()
        db.refresh(kb)
    return kb


def _resolve_kb(db: Session, user: User, kb_id: str | None) -> KnowledgeBase:
    if not kb_id:
        return _ensure_default_kb(db, user)
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise AppError(1004, "知识库不存在")
    if kb.user_id != user.id:
        raise AppError(1003, "无权访问该知识库")
    return kb


def get_document(db: Session, user: User, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError(1004, "文档不存在")
    if doc.user_id != user.id:
        raise AppError(1003, "无权访问该文档")
    return doc


def _latest_task(db: Session, doc_id: str) -> IngestTask | None:
    return (
        db.query(IngestTask)
        .filter(IngestTask.doc_id == doc_id)
        .order_by(IngestTask.created_at.desc())
        .first()
    )


def create_document(
    db: Session, user: User, kb_id: str | None, filename: str, raw: bytes
) -> tuple[Document, IngestTask]:
    suffix = Path(filename).suffix.lower()
    file_type = ALLOWED_SUFFIX.get(suffix)
    if file_type is None:
        raise AppError(2002, f"不支持的文件类型：{suffix or '未知'}（支持 pdf/docx/md/txt）")
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(2001, f"文件过大（上限 {settings.max_upload_mb}MB）")
    if not raw:
        raise AppError(1001, "文件为空")

    kb = _resolve_kb(db, user, kb_id)
    content_hash = hashlib.sha256(raw).hexdigest()
    duplicated = (
        db.query(Document)
        .filter(
            Document.kb_id == kb.id,
            Document.content_hash == content_hash,
            Document.status.in_(("pending", "parsing", "embedding", "ready")),
        )
        .first()
    )
    if duplicated is not None:
        raise AppError(1005, f"该文件已在知识库中（{duplicated.filename}）")

    doc_id = new_id("doc")
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    stored_path = settings.upload_path / f"{doc_id}{suffix}"
    stored_path.write_bytes(raw)

    doc = Document(
        id=doc_id,
        kb_id=kb.id,
        user_id=user.id,
        filename=filename,
        stored_path=str(stored_path),
        file_type=file_type,
        size_bytes=len(raw),
        status="pending",
        content_hash=content_hash,
    )
    task = IngestTask(id=new_id("task"), doc_id=doc_id, status="pending", progress=0, stage="parse")
    db.add_all([doc, task])
    db.commit()
    db.refresh(doc)
    db.refresh(task)
    return doc, task


def _set_progress(
    db: Session, doc: Document, task: IngestTask, status: str, progress: int, stage: str,
    error: str | None = None,
) -> None:
    doc.status = status
    doc.updated_at = _utcnow()
    if error:
        doc.error_msg = error[:500]
    task.status = "done" if status == "ready" else status
    task.progress = progress
    task.stage = stage
    task.error_msg = error[:500] if error else None
    if status in ("ready", "failed", "rejected"):
        task.finished_at = _utcnow()
    db.commit()


def run_ingest(doc_id: str) -> None:
    """后台任务入口（BackgroundTasks 调用）。自己开 session。"""
    with session_scope() as db:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        task = _latest_task(db, doc_id)
        if task is None:
            return
        task.started_at = _utcnow()
        _set_progress(db, doc, task, "parsing", 10, "parse")

    with _INGEST_LOCK:
        with session_scope() as db:
            doc = db.get(Document, doc_id)
            task = _latest_task(db, doc_id)
            if doc is None or task is None:
                return
            try:
                pages = load_pages(Path(doc.stored_path), doc.file_type)
                chars = sum(len(text) for _, text in pages)
                if chars < 50:
                    raise AppError(2003, "解析后内容过少，请确认是可复制的文字版")
                page_count = len([p for p, _ in pages if p is not None]) or None
                doc.page_count = page_count
                _set_progress(db, doc, task, "parsing", 40, "split")

                drafts = split_pages(pages)
                if not drafts:
                    raise AppError(2003, "解析后没有得到有效内容片段")
                _set_progress(db, doc, task, "embedding", 55, "embed")

                delete_index(db, doc.id)  # 幂等：重跑不会产生重复 chunk
                count = write_chunks(db, doc, drafts)

                doc.chunk_count = count
                _set_progress(db, doc, task, "ready", 100, "index")
                logger.info("ingest done doc=%s chunks=%d chars=%d", doc.id, count, chars)
            except AppError as exc:
                rejected = exc.code == 2003
                _set_progress(
                    db, doc, task,
                    "rejected" if rejected else "failed",
                    100 if rejected else task.progress,
                    task.stage,
                    exc.message,
                )
                logger.warning("ingest rejected doc=%s: %s", doc_id, exc.message)
            except Exception as exc:  # pragma: no cover
                logger.exception("ingest failed doc=%s", doc_id)
                _set_progress(db, doc, task, "failed", task.progress, task.stage, f"解析失败：{exc}")


def list_documents(db: Session, user: User, kb_id: str | None) -> list[Document]:
    query = db.query(Document).filter(Document.user_id == user.id)
    if kb_id:
        query = query.filter(Document.kb_id == kb_id)
    return query.order_by(Document.created_at.desc()).all()


def status_of(db: Session, doc: Document) -> dict:
    task = _latest_task(db, doc.id)
    return {
        "doc_id": doc.id,
        "status": doc.status,
        "progress": task.progress if task else (100 if doc.status == "ready" else 0),
        "stage": task.stage if task else "parse",
        "error": doc.error_msg,
        "chunk_count": doc.chunk_count,
    }


def preview(db: Session, doc: Document, page: int, size: int) -> dict:
    from app.db.models import Chunk

    total = db.query(Chunk).filter(Chunk.doc_id == doc.id).count()
    rows = (
        db.query(Chunk)
        .filter(Chunk.doc_id == doc.id)
        .order_by(Chunk.seq)
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return {
        "doc_id": doc.id,
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": row.id,
                "seq": row.seq,
                "content": row.content,
                "content_type": row.content_type,
                "page": row.page,
                "has_formula": row.has_formula,
                "token_count": row.token_count,
            }
            for row in rows
        ],
    }


def delete_document(db: Session, doc: Document) -> None:
    delete_index(db, doc.id)
    db.query(IngestTask).filter(IngestTask.doc_id == doc.id).delete(synchronize_session=False)
    db.delete(doc)
    db.commit()
    Path(doc.stored_path).unlink(missing_ok=True)


def reindex(db: Session, doc: Document) -> IngestTask:
    delete_index(db, doc.id)
    doc.chunk_count = 0
    doc.error_msg = None
    task = IngestTask(id=new_id("task"), doc_id=doc.id, status="pending", progress=0, stage="parse")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
