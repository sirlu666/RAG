"""文档接口（6 个）—— A 的职责范围。

契约见 docs/A-接口与边界.md §3：
  POST   /api/docs/upload
  GET    /api/docs?kb_id=
  GET    /api/docs/{doc_id}/status
  GET    /api/docs/{doc_id}/preview
  DELETE /api/docs/{doc_id}
  POST   /api/docs/{doc_id}/reindex
"""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.schemas import DocListResponse, DocOut, DocStatusOut, PreviewOut, ReindexOut, UploadOut
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import AppError, ok
from app.db.models import User, DocumentCategory
from app.db.session import get_db
from app.services import doc_service
from app.services import document_text
from app.services import document_metadata
from app.services import document_tags

router = APIRouter(tags=["document"])


class TextEdit(BaseModel):
    content: str = Field(max_length=document_text.MAX_CHARACTERS)
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


class MetadataEdit(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    category: str = Field(max_length=64)
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.get('/api/docs/{doc_id}/replacement', summary='读取文件替换条件及版本')
def get_replacement_info(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(document_text.replacement_info(doc_service.get_document(db, user, doc_id)))


@router.post('/api/docs/{doc_id}/replacement', summary='备份并用同格式新文件更新资料及索引')
def replace_document_file(doc_id: str, file: UploadFile = File(...),
    version: str = Form(pattern=r'^[a-f0-9]{64}$'),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = doc_service.get_document(db, user, doc_id)
    raw = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    return ok(document_text.replace_file(db, doc, file.filename or '', raw, version))


@router.get('/api/docs/{doc_id}/metadata', summary='读取文档名称、分类和最新版本')
def get_document_metadata(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = doc_service.get_document(db, user, doc_id)
    return ok({'doc_id': doc.id, 'filename': doc.filename,
               **document_metadata.metadata_of(doc, db.get(DocumentCategory, doc.id))})


@router.patch('/api/docs/{doc_id}/metadata', summary='修改文档名称和手动分类')
def edit_document_metadata(doc_id: str, body: MetadataEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(document_metadata.update_metadata(db, doc_service.get_document(db, user, doc_id),
              body.filename, body.category, body.version))


@router.get('/api/docs/{doc_id}/text', summary='读取 TXT/Markdown 正文或图片校对文字与版本')
def get_document_text(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(document_text.read_text(doc_service.get_document(db, user, doc_id)))


@router.put('/api/docs/{doc_id}/text', summary='备份并更新正文及索引')
def edit_document_text(doc_id: str, body: TextEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(document_text.update_text(db, doc_service.get_document(db, user, doc_id), body.content, body.version))


@router.post('/api/docs/{doc_id}/formula', summary='本机识别单条公式截图，返回未保存的 LaTeX 建议')
def recognize_document_formula(doc_id: str, file: UploadFile = File(...),
    version: str = Form(pattern=r'^[a-f0-9]{64}$'),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = doc_service.get_document(db, user, doc_id)
    raw = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    return ok(document_text.recognize_formula(db, doc, file.filename or '', raw, version))


@router.post("/api/docs/upload", summary="上传文档并触发解析")
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="pdf/docx/md/txt/png/jpg/jpeg"),
    kb_id: str | None = Form(default=None),
    overwrite: bool = Form(default=False, description="同库同名文件覆盖（版本更新）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raw = await file.read()
    doc, task = doc_service.create_document(
        db, user, kb_id, file.filename or "未命名", raw, overwrite=overwrite
    )
    background.add_task(doc_service.run_ingest, doc.id)
    payload = UploadOut(doc_id=doc.id, task_id=task.id, status=doc.status)
    return ok(payload.model_dump())


@router.get("/api/docs", summary="文档列表及手动分类、已有自动标签", response_model=DocListResponse)
def list_documents(
    kb_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    docs = doc_service.list_documents(db, user, kb_id)
    categories = {row.doc_id: row for row in db.query(DocumentCategory).filter(
        DocumentCategory.doc_id.in_([doc.id for doc in docs])).all()} if docs else {}
    items = [
        DocOut(
            id=d.id,
            kb_id=d.kb_id,
            filename=d.filename,
            file_type=d.file_type,
            size_bytes=d.size_bytes,
            page_count=d.page_count,
            status=d.status,
            chunk_count=d.chunk_count,
            error_msg=d.error_msg,
            created_at=d.created_at.isoformat(),
            **document_metadata.metadata_of(d, categories.get(d.id)),
            **document_tags.tags_of(d),
        ).model_dump()
        for d in docs
    ]
    return ok(items)


@router.get("/api/docs/{doc_id}/status", summary="解析进度（前端 1.5s 轮询）")
def document_status(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    return ok(DocStatusOut(**doc_service.status_of(db, doc)).model_dump())


@router.get("/api/docs/{doc_id}/preview", summary="分页预览切出来的 chunk")
def preview_document(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = doc_service.get_readable_document(db, user, doc_id)
    if doc.status != "ready":
        raise AppError(2003, "文档尚未解析完成，无法预览")
    return ok(PreviewOut(**doc_service.preview(db, doc, page, size)).model_dump())


@router.get(
    "/api/docs/{doc_id}/file",
    summary="查看或下载原始文件",
    response_class=FileResponse,
    responses={200: {"content": {
        "application/pdf": {},
        "image/png": {},
        "image/jpeg": {},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
        "text/markdown": {},
        "text/plain": {},
    }}},
)
def original_document_file(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = doc_service.get_readable_document(db, user, doc_id)
    if doc.status != "ready":
        raise AppError(2003, "文档尚未解析完成，无法查看原文件")
    path = Path(doc.stored_path)
    upload_root = settings.upload_path.resolve()
    if path.is_symlink() or path.resolve().parent != upload_root or not path.is_file():
        raise AppError(5000, "原文件暂时无法读取，请检查文件存储状态")
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    file_type = doc.file_type.lower()
    if file_type not in media_types:
        raise AppError(2002, "不支持查看此文件类型")
    return FileResponse(
        path,
        media_type=media_types[file_type],
        filename=doc.filename,
        content_disposition_type="inline" if file_type in ("pdf", "png", "jpg", "jpeg") else "attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/api/docs/{doc_id}", summary="删除文档并清理向量")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    doc_service.delete_document(db, doc)
    return ok({"doc_id": doc_id, "deleted": True})


@router.post("/api/docs/{doc_id}/reindex", summary="重建索引")
def reindex_document(
    doc_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    task = doc_service.reindex(db, doc)
    background.add_task(doc_service.run_ingest, doc.id)
    return ok(ReindexOut(doc_id=doc.id, task_id=task.id, status="pending").model_dump())
