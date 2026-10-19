"""文档接口（6 个）—— A 的职责范围。

契约见 docs/A-接口与边界.md §3：
  POST   /api/docs/upload
  GET    /api/docs?kb_id=
  GET    /api/docs/{doc_id}/status
  GET    /api/docs/{doc_id}/preview
  DELETE /api/docs/{doc_id}
  POST   /api/docs/{doc_id}/reindex
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import DocOut, DocStatusOut, PreviewOut, ReindexOut, UploadOut
from app.api._dev_user import dev_current_user
from app.core.exceptions import AppError, ok
from app.db.models import User
from app.db.session import get_db
from app.services import doc_service

router = APIRouter(tags=["document"])


@router.post("/api/docs/upload", summary="上传文档并触发解析")
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="pdf/docx/md/txt"),
    kb_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    raw = await file.read()
    doc, task = doc_service.create_document(db, user, kb_id, file.filename or "未命名", raw)
    background.add_task(doc_service.run_ingest, doc.id)
    payload = UploadOut(doc_id=doc.id, task_id=task.id, status=doc.status)
    return ok(payload.model_dump())


@router.get("/api/docs", summary="文档列表")
def list_documents(
    kb_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    docs = doc_service.list_documents(db, user, kb_id)
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
        ).model_dump()
        for d in docs
    ]
    return ok(items)


@router.get("/api/docs/{doc_id}/status", summary="解析进度（前端 1.5s 轮询）")
def document_status(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    return ok(DocStatusOut(**doc_service.status_of(db, doc)).model_dump())


@router.get("/api/docs/{doc_id}/preview", summary="分页预览切出来的 chunk")
def preview_document(
    doc_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    if doc.status != "ready":
        raise AppError(2003, "文档尚未解析完成，无法预览")
    return ok(PreviewOut(**doc_service.preview(db, doc, page, size)).model_dump())


@router.delete("/api/docs/{doc_id}", summary="删除文档并清理向量")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    doc_service.delete_document(db, doc)
    return ok({"doc_id": doc_id, "deleted": True})


@router.post("/api/docs/{doc_id}/reindex", summary="重建索引")
def reindex_document(
    doc_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(dev_current_user),
):
    doc = doc_service.get_document(db, user, doc_id)
    task = doc_service.reindex(db, doc)
    background.add_task(doc_service.run_ingest, doc.id)
    return ok(ReindexOut(doc_id=doc.id, task_id=task.id, status="pending").model_dump())
