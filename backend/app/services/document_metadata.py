"""Document display names and manual categories; no file moves or embedding calls."""
import hashlib
import json
import re
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import AppError
from app.db.models import Document, DocumentCategory
from app.rag.retriever import invalidate_bm25_cache
from app.rag.vectorstore import get_store
from app.services.doc_service import _document_mutation, _utcnow


def metadata_of(doc, category):
    label = category.category if category else ''
    revision = category.revision if category else ''
    value = json.dumps([doc.filename, label, revision], ensure_ascii=False)
    return {'category': label, 'metadata_version': hashlib.sha256(value.encode('utf-8')).hexdigest()}


def update_metadata(db, doc, filename, category, version):
    filename, category = filename.strip(), category.strip()
    if not filename or len(filename) > 255 or re.search(r'[\\/:*?"<>|\x00-\x1f\x7f]', filename):
        raise AppError(1001, '名称不能为空，最多 255 字符，不能包含路径或特殊文件名字符')
    if Path(filename).suffix.lower() != '.' + doc.file_type:
        raise AppError(1001, '改名时请保留原文件扩展名')
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', filename.split('.')[0], re.I):
        raise AppError(1001, '请勿使用 Windows 保留文件名')
    if len(category) > 64 or any(ord(char) < 32 or ord(char) == 127 for char in category):
        raise AppError(1001, '分类最多 64 字符，不能包含控制字符')
    with _document_mutation(db, doc) as current:
        row = db.get(DocumentCategory, current.id)
        before = metadata_of(current, row)
        if before['metadata_version'] != version:
            raise AppError(1005, '名称或分类已更新，请关闭编辑并刷新文档列表后重试')
        renamed = filename != current.filename
        if not renamed and category == before['category']:
            return {'doc_id': current.id, 'filename': current.filename, **before, 'changed': False}
        if renamed and db.query(Document).filter(Document.kb_id == current.kb_id,
            Document.id != current.id, Document.filename == filename).first():
            raise AppError(1005, '同一知识库已有此名称，请使用其他名称；不会覆盖原资料')
        store = get_store() if renamed else None
        items = store.snapshot_doc(current.id) if renamed else []
        updated_items = [{**item, 'm': {**item['m'], 'doc_name': filename}} for item in items]
        try:
            with (store.replacing_doc(current.id, updated_items) if renamed else nullcontext()):
                current.filename = filename
                current.updated_at = _utcnow()
                if row is None:
                    row = DocumentCategory(doc_id=current.id)
                    db.add(row)
                row.category = category
                row.revision = uuid4().hex
                db.commit()
        except Exception:
            db.rollback()
            raise
        # Chunk counts/timestamps do not change, so explicitly drop cached document titles.
        invalidate_bm25_cache()
        db.refresh(current)
        db.refresh(row)
        return {'doc_id': current.id, 'filename': current.filename, **metadata_of(current, row), 'changed': True}
