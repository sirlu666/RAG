"""文档生命周期：上传 → 解析 → 切片 → 向量化 → 可检索；以及删除 / 重建。

并发约定：同一时刻只允许一个入库任务（单写锁），避免 SQLite 写锁与向量库并发写。
"""

import hashlib
import logging
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models import Document, DocumentCategory, DocumentOcrText, IngestTask, KnowledgeBase, PublishedKnowledgeBase, User, new_id
from app.db.session import session_scope
from app.rag.indexer import delete_index, write_chunks
from app.rag.splitter import split_pages
from app.services.parsing.loader import load_pages

logger = logging.getLogger("mathrag.doc")

ALLOWED_SUFFIX = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".txt": "txt",
                  ".png": "png", ".jpg": "jpg", ".jpeg": "jpeg"}
_INGEST_LOCK = threading.Lock()


def minimum_content_chars(file_type: str) -> int:
    return 5 if file_type in ('png', 'jpg', 'jpeg') else 50


def split_document_pages(pages, file_type):
    # Keep ordinary document chunks at their existing 20-character threshold.
    return split_pages(pages, min_chars=min(20, minimum_content_chars(file_type)))


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


def _stale_chunk_ids(db: Session, doc_id: str) -> set[str]:
    """返回某文档当前已有的 chunk id 集合（用于两阶段提交时清理旧 chunk）。"""
    from app.db.models import Chunk

    return {c.id for c in db.query(Chunk.id).filter(Chunk.doc_id == doc_id).all()}


def _delete_chunk_ids(db: Session, ids: set[str]) -> None:
    """删除指定 chunk（关系库 + 向量库）。向量删除失败会抛错，避免孤儿。"""
    from app.db.models import Chunk
    from app.rag.vectorstore import get_store

    if not ids:
        return
    store = get_store()
    store.delete_ids(list(ids))
    db.query(Chunk).filter(Chunk.id.in_(ids)).delete(synchronize_session=False)
    # Commit with the ready state; a cleanup failure must not publish half a version.


def _commit_superseded(db: Session, new_doc: Document) -> None:
    """新文档 ready 后，物理删除被它替换的同名旧文档。"""
    olds = (
        db.query(Document)
        .filter(
            Document.kb_id == new_doc.kb_id,
            Document.filename == new_doc.filename,
            Document.status == "superseded",
            Document.id != new_doc.id,
        )
        .all()
    )
    for old in olds:
        _delete_document_locked(db, old)


def _rollback_superseded(db: Session, new_doc: Document) -> None:
    """新文档入库失败，恢复被软标记的旧文档为 ready。"""
    db.query(Document).filter(
        Document.kb_id == new_doc.kb_id,
        Document.filename == new_doc.filename,
        Document.status == "superseded",
    ).update({"status": "ready"}, synchronize_session=False)
    db.commit()


def get_document(db: Session, user: User, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError(1004, "文档不存在")
    if doc.user_id != user.id:
        raise AppError(1003, "无权访问该文档")
    return doc


def get_readable_document(db: Session, user: User, doc_id: str) -> Document:
    """Logged-in source reading may use public KBs; mutations still require ownership."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError(1004, '文档不存在')
    if doc.user_id != user.id and db.get(PublishedKnowledgeBase, doc.kb_id) is None:
        raise AppError(1003, '无权访问该文档')
    return doc


def _latest_task(db: Session, doc_id: str) -> IngestTask | None:
    return (
        db.query(IngestTask)
        .filter(IngestTask.doc_id == doc_id)
        .order_by(IngestTask.created_at.desc())
        .first()
    )


def create_document(
    db: Session,
    user: User,
    kb_id: str | None,
    filename: str,
    raw: bytes,
    overwrite: bool = False,
) -> tuple[Document, IngestTask]:
    suffix = Path(filename).suffix.lower()
    file_type = ALLOWED_SUFFIX.get(suffix)
    if file_type is None:
        raise AppError(2002, f"不支持的文件类型：{suffix or '未知'}（支持 pdf/docx/md/txt/png/jpg/jpeg）")
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

    # Only mutate old versions after all duplicate/busy checks have succeeded.
    if overwrite:
        olds = db.query(Document).filter(Document.kb_id == kb.id, Document.filename == filename).all()
        if any(old.status in ('pending', 'parsing', 'embedding', 'superseded') for old in olds):
            raise AppError(1005, '同名文档正在入库中，请稍后再覆盖')
        for old in olds:
            old.status = 'superseded'

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
    # An existing published version remains readable while its rebuild runs/fails.
    if doc.status != 'ready' or status == 'ready':
        doc.status = status
    doc.updated_at = _utcnow()
    doc.error_msg = error[:500] if error else None
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
        if doc.file_type == "pdf" and settings.ocr_enable:
            try:
                from app.services.parsing.ocr import is_scanned_pdf

                if is_scanned_pdf(Path(doc.stored_path)):
                    _set_progress(db, doc, task, "parsing", 15, "ocr")
            except Exception as exc:  # 探测失败不影响主流程，loader 会再判定
                logger.debug("scan detect failed: %s", exc)

    with _INGEST_LOCK:
        with session_scope() as db:
            doc = db.get(Document, doc_id)
            task = _latest_task(db, doc_id)
            if doc is None or task is None:
                return
            from app.rag.vectorstore import get_store
            old_fields = {name: getattr(doc, name) for name in ('page_count', 'chunk_count')}
            stale_ids = _stale_chunk_ids(db, doc.id)
            old_vectors = get_store().snapshot_doc(doc.id) if stale_ids else []
            cleanup_started = False
            try:
                correction = db.get(DocumentOcrText, doc.id)
                if correction and correction.source_hash == doc.content_hash:
                    pages = [(1, correction.content)]
                else:
                    pages = load_pages(Path(doc.stored_path), doc.file_type)
                chars = sum(len(text) for _, text in pages)
                minimum_chars = minimum_content_chars(doc.file_type)
                if chars < minimum_chars:
                    raise AppError(2003, "解析后内容过少，请确认是可复制的文字版")
                page_count = len([p for p, _ in pages if p is not None]) or None
                doc.page_count = page_count
                _set_progress(db, doc, task, "parsing", 40, "split")

                drafts = split_document_pages(pages, doc.file_type)
                if not drafts:
                    raise AppError(2003, "解析后没有得到有效内容片段")
                _set_progress(db, doc, task, "embedding", 55, "embed")

                # 两阶段提交：先记录旧 chunk，写新 chunk 成功后再删旧 chunk。
                # 这样解析/切片/向量化任一失败，旧索引都原样保留。
                count = write_chunks(db, doc, drafts)
                cleanup_started = True
                _delete_chunk_ids(db, stale_ids)

                doc.chunk_count = count
                _set_progress(db, doc, task, "ready", 100, "index")
                logger.info("ingest done doc=%s chunks=%d chars=%d", doc.id, count, chars)
            except AppError as exc:
                _rollback_rebuild(db, doc, stale_ids, old_vectors, old_fields, cleanup_started)
                rejected = exc.code == 2003
                _set_progress(
                    db, doc, task,
                    "rejected" if rejected else "failed",
                    100 if rejected else task.progress,
                    task.stage,
                    exc.message,
                )
                _rollback_superseded(db, doc)
                logger.warning("ingest rejected doc=%s: %s", doc_id, exc.message)
            except Exception as exc:  # pragma: no cover
                logger.exception("ingest failed doc=%s", doc_id)
                _rollback_rebuild(db, doc, stale_ids, old_vectors, old_fields, cleanup_started)
                _set_progress(db, doc, task, "failed", task.progress, task.stage, f"解析失败：{exc}")
                _rollback_superseded(db, doc)
            else:
                # Publication already committed. A later old-file cleanup failure must
                # never roll back/delete the newly published, usable index.
                try:
                    _commit_superseded(db, doc)
                except Exception:
                    db.rollback()
                    logger.exception('new version ready but old version cleanup failed doc=%s', doc_id)
                    doc.error_msg = '新版本已就绪，但旧版本清理失败，请检查后台日志后重试清理'
                    db.commit()


def _rollback_rebuild(db, doc, stale_ids, old_vectors, old_fields, cleanup_started):
    """Remove this attempt's new chunks and restore old vectors after failed cleanup."""
    from app.rag.vectorstore import get_store
    db.rollback()
    new_ids = _stale_chunk_ids(db, doc.id) - stale_ids
    store = get_store()
    if cleanup_started and old_vectors:
        store.upsert(ids=[it['id'] for it in old_vectors], vectors=[it['v'] for it in old_vectors],
                     documents=[it['d'] for it in old_vectors], metadatas=[it['m'] for it in old_vectors])
    _delete_chunk_ids(db, new_ids)
    for name, value in old_fields.items():
        setattr(doc, name, value)


def doc_tags_out(doc: Document) -> dict:
    """从 tags_json 解析出接口展示用标签（knowledge_points/question_types/difficulty）。

    未标注返回空数组 / null，符合 C 前端消费约定。
    """
    import json

    if not doc.tags_json:
        return {"knowledge_points": [], "question_types": [], "difficulty": None}
    try:
        tags = json.loads(doc.tags_json)
    except Exception:
        return {"knowledge_points": [], "question_types": [], "difficulty": None}
    difficulty = tags.get("difficulty")
    if difficulty not in ("基础", "进阶", "困难"):
        difficulty = None
    return {
        "knowledge_points": tags.get("knowledge_points") or [],
        "question_types": tags.get("question_types") or [],
        "difficulty": difficulty,
    }


def list_documents(db: Session, user: User, kb_id: str | None) -> list[Document]:
    query = db.query(Document).filter(Document.user_id == user.id)
    if kb_id:
        query = query.filter(Document.kb_id == kb_id)
    # superseded 是覆盖中的过渡态（旧文档待新文档 ready 后清理），对调用方不可见
    query = query.filter(Document.status != "superseded")
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


@contextmanager
def _document_mutation(db: Session, doc: Document):
    # Share the single-process ingestion lock; never wait behind a long embedding job.
    if not _INGEST_LOCK.acquire(blocking=False):
        raise AppError(1005, "资料正在入库，请等待处理结束后刷新重试")
    try:
        doc_id = doc.id
        db.expire_all()
        current = db.get(Document, doc_id)
        if current is None:
            raise AppError(1004, "文档不存在")
        task = _latest_task(db, current.id)
        if (current.status in ("pending", "parsing", "embedding", "superseded")
                or (task and task.status in ("pending", "parsing", "embedding"))):
            raise AppError(1005, "该文档正在处理，暂时不能删除或重建索引")
        yield current
    finally:
        _INGEST_LOCK.release()


def delete_document(db: Session, doc: Document) -> None:
    with _document_mutation(db, doc) as current:
        _delete_document_locked(db, current)


def _delete_document_locked(db: Session, current: Document) -> None:
    """Caller holds the ingest lock, including superseded-version cleanup."""
    delete_index(db, current.id)
    db.query(IngestTask).filter(IngestTask.doc_id == current.id).delete(synchronize_session=False)
    db.query(DocumentCategory).filter_by(doc_id=current.id).delete(synchronize_session=False)
    db.query(DocumentOcrText).filter_by(doc_id=current.id).delete(synchronize_session=False)
    stored_path = Path(current.stored_path)
    db.delete(current)
    db.commit()
    stored_path.unlink(missing_ok=True)
    versions = stored_path.parent / '.versions'
    backup_dir = versions / current.id
    if backup_dir.exists():
        # Only this document's generated recovery directory, never follow a linked target.
        if backup_dir.is_symlink() or backup_dir.resolve().parent != versions.resolve():
            raise AppError(5000, '旧版备份路径异常，未清理，请检查备份目录')
        shutil.rmtree(backup_dir.resolve())

def reindex(db: Session, doc: Document) -> IngestTask:
    # Keep the published index readable until a replacement has succeeded.
    with _document_mutation(db, doc) as current:
        current.error_msg = None
        task = IngestTask(id=new_id("task"), doc_id=current.id, status="pending", progress=0, stage="parse")
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
