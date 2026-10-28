"""Version-checked text edits with precomputed embeddings and retained recovery files."""
import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import AppError
from app.core.config import settings
from app.db.models import Chunk, Document, DocumentOcrText, IngestTask, new_id
from sqlalchemy.orm import object_session
from app.rag.embedder import embed_texts
from app.rag.indexer import build_metadata
from app.rag.retriever import invalidate_bm25_cache
from app.rag.vectorstore import get_store
from app.services.doc_service import _document_mutation, _utcnow, minimum_content_chars, split_document_pages
from app.services.parsing.loader import clean_text, load_pages

MAX_CHARACTERS = 200_000
IMAGE_TYPES = ('png', 'jpg', 'jpeg')


def read_text(doc: Document) -> dict:
    if doc.file_type in IMAGE_TYPES:
        replacement_info(doc)  # Verify that the original image has not changed externally.
        db = object_session(doc)
        if doc.status != 'ready':
            raise AppError(1005, '请等待图片处理就绪后再校对')
        chunks = db.query(Chunk).filter_by(doc_id=doc.id).order_by(Chunk.seq).all()
        correction = db.get(DocumentOcrText, doc.id)
        text = (correction.content if correction and correction.source_hash == doc.content_hash
                else '\n\n'.join(chunk.content for chunk in chunks))
        if len(text) > MAX_CHARACTERS:
            raise AppError(2001, '在线校对最多支持 20 万字符')
        revision = json.dumps([doc.content_hash, text, [chunk.id for chunk in chunks]], ensure_ascii=False)
        return {'doc_id': doc.id, 'filename': doc.filename, 'content': text,
                'version': hashlib.sha256(revision.encode('utf-8')).hexdigest()}
    if doc.file_type not in ('txt', 'md'):
        raise AppError(2002, '仅 TXT 和 Markdown 支持正文编辑')
    path = Path(doc.stored_path)
    if path.stat().st_size > MAX_CHARACTERS * 4:
        raise AppError(2001, '在线编辑最多支持 20 万字符，请用文件新版本替换')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != doc.content_hash:
        raise AppError(1005, '服务器文件已被外部修改，请先核对资料版本')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise AppError(2003, '在线编辑需要 UTF-8 文件，请转换编码后上传新版本')
    if len(text) > MAX_CHARACTERS:
        raise AppError(2001, '在线编辑最多支持 20 万字符')
    return {'doc_id': doc.id, 'filename': doc.filename, 'content': text, 'version': doc.content_hash}


def update_text(db, doc, content: str, version: str) -> dict:
    with _document_mutation(db, doc) as current:
        old = read_text(current)
        if old['version'] != version:
            raise AppError(1005, '资料已更新，请先重新打开编辑器，再合并你的修改')
        if current.file_type in IMAGE_TYPES:
            if content == old['content']:
                return {'doc_id': current.id, 'version': version, 'changed': False}
            result = _save_pages(db, current, Path(current.stored_path).read_bytes(),
                                 version, [(1, clean_text(content))], ocr_content=content)
            result['version'] = read_text(current)['version']
            return result
        raw = content.encode('utf-8')
        return _save_pages(db, current, raw, version, [(None, clean_text(content))])


def recognize_formula(db, doc, filename, raw, version):
    """Return an unsaved local-model suggestion for an owner-supplied screenshot."""
    from app.services.parsing.ocr import decode_image, _require_numpy
    from app.services.parsing.formula import recognize_array
    if not raw or len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(2001, f'公式截图不能为空，最多 {settings.max_upload_mb}MB')
    if settings.ocr_formula != 'rapid_latex':
        raise AppError(2003, '本机公式识别尚未启用，请检查本机公式环境')
    with _document_mutation(db, doc) as current:
        if current.file_type not in IMAGE_TYPES:
            raise AppError(2002, '当前仅支持在图片校对中识别公式截图')
        if read_text(current)['version'] != version:
            raise AppError(1005, '资料已更新，请先复制修改，再重新读取正文核对版本')
        image = decode_image(raw, Path(filename).suffix)
        try:
            latex = recognize_array(_require_numpy().asarray(image)).strip()
        except Exception as exc:
            raise AppError(2003, '本机公式识别失败，正文保持不变；请检查公式环境或尝试更清晰的单条公式截图') from exc
        if not latex:
            raise AppError(2003, '未识别到公式，正文保持不变')
        return {'doc_id': current.id, 'latex': latex, 'version': version}


def replacement_info(doc):
    if doc.file_type not in ('pdf', 'docx', 'md', 'txt', 'png', 'jpg', 'jpeg'):
        raise AppError(2002, '当前文件类型尚不支持替换')
    raw = Path(doc.stored_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != doc.content_hash:
        raise AppError(1005, '服务器文件已被外部修改，请先核对资料版本')
    return {'doc_id': doc.id, 'filename': doc.filename, 'file_type': doc.file_type,
            'version': doc.content_hash, 'max_upload_mb': settings.max_upload_mb}


def replace_file(db, doc, filename, raw, version):
    if not raw:
        raise AppError(1001, '新文件不能为空，旧版保留')
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise AppError(2001, f'新文件最多 {settings.max_upload_mb}MB，旧版保留')
    if Path(filename).suffix.lower() != '.' + doc.file_type:
        raise AppError(2002, '请选择与原资料相同格式的新文件，不支持通过替换转换格式')
    with _document_mutation(db, doc) as current:
        old = replacement_info(current)
        if old['version'] != version:
            raise AppError(1005, '资料已有新版本，请重新打开替换面板核对后再试')
        if hashlib.sha256(raw).hexdigest() == version:
            return {'doc_id': current.id, 'version': version, 'changed': False}
        candidate = Path(current.stored_path).parent / ('.replacement-' + uuid4().hex + '.' + current.file_type)
        try:
            candidate.write_bytes(raw)
            try:
                pages = load_pages(candidate, current.file_type)
            except AppError:
                raise
            except Exception as exc:
                raise AppError(2003, '新文件无法解析，旧版保留；请检查文件是否损坏或加密') from exc
            return _save_pages(db, current, raw, version, pages)
        finally:
            candidate.unlink(missing_ok=True)


def _save_pages(db, current, raw, version, pages, *, ocr_content=None):
    digest = hashlib.sha256(raw).hexdigest()
    if digest == version and ocr_content is None:
        return {'doc_id': current.id, 'version': version, 'changed': False}
    minimum_chars = minimum_content_chars(current.file_type)
    if sum(len(text) for _, text in pages) < minimum_chars:
        raise AppError(2003, f'处理后正文至少需要 {minimum_chars} 个字符，原资料保留')
    duplicate = db.query(Document).filter(Document.kb_id == current.kb_id,
        Document.id != current.id, Document.content_hash == digest,
        Document.status.in_(('pending', 'parsing', 'embedding', 'ready'))).first()
    if duplicate:
        raise AppError(1005, '此内容已存在于同一知识库，原资料保留')
    drafts = split_document_pages(pages, current.file_type)
    if not drafts:
        raise AppError(2003, '未得到有效片段，原资料保留')
    vectors = embed_texts([draft.content for draft in drafts])
    if len(vectors) != len(drafts):
        raise AppError(5000, '向量数量不匹配，原资料保留')
    rows, items = [], []
    for draft, vector in zip(drafts, vectors):
        chunk_id = new_id('ch')
        rows.append(Chunk(id=chunk_id, doc_id=current.id, kb_id=current.kb_id,
            user_id=current.user_id, seq=draft.seq, content=draft.content,
            content_type=draft.content_type, page=draft.page, char_start=draft.char_start,
            char_end=draft.char_end, token_count=draft.token_count, has_formula=draft.has_formula))
        items.append({'id': chunk_id, 'v': list(map(float, vector)), 'd': draft.content,
                      'm': build_metadata(current, draft, chunk_id)})

    path = Path(current.stored_path)
    recovery = path.parent / '.versions' / current.id / uuid4().hex
    recovery.mkdir(parents=True)
    backup = recovery / path.name
    shutil.copy2(path, backup)
    store = get_store()
    old_chunks = db.query(Chunk).filter_by(doc_id=current.id).all()
    snapshot = {'doc_id': current.id, 'version': version, 'filename': current.filename,
        'vectors': store.snapshot_doc(current.id),
        'chunks': [{column.name: getattr(row, column.name) for column in Chunk.__table__.columns}
                   for row in old_chunks]}
    correction = db.get(DocumentOcrText, current.id)
    snapshot['ocr_text'] = ({'source_hash': correction.source_hash, 'content': correction.content}
                            if correction else None)
    (recovery / 'index.json').write_text(json.dumps(snapshot, ensure_ascii=False, default=str), encoding='utf-8')
    staged = recovery / 'new-content.tmp'
    staged.write_bytes(raw)
    replaced = False
    try:
        with store.replacing_doc(current.id, items):
            if ocr_content is None:
                staged.replace(path)
                replaced = True
                if correction:
                    db.delete(correction)
            else:
                if correction is None:
                    correction = DocumentOcrText(doc_id=current.id)
                    db.add(correction)
                correction.source_hash = digest
                correction.content = ocr_content
            db.query(Chunk).filter_by(doc_id=current.id).delete(synchronize_session=False)
            db.add_all(rows)
            current.content_hash = digest
            current.size_bytes = len(raw)
            current.chunk_count = len(rows)
            current.page_count = len([page for page, _ in pages if page is not None]) or None
            current.status = 'ready'
            current.error_msg = None
            current.tags_json = None
            current.difficulty = None
            current.updated_at = _utcnow()
            db.add(IngestTask(doc_id=current.id, status='done', progress=100, stage='index',
                              started_at=_utcnow(), finished_at=_utcnow()))
            db.commit()
    except Exception:
        db.rollback()
        if replaced:
            shutil.copy2(backup, path)
        raise
    invalidate_bm25_cache()
    staged.unlink(missing_ok=True)
    return {'doc_id': current.id, 'version': digest, 'changed': True, 'chunk_count': len(rows)}
