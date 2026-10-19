"""A 的接口出入参模型（只覆盖 6 个文档接口）。

新增字段只能追加，禁止改名（见 docs/A-接口与边界.md）。
"""

from pydantic import BaseModel


class UploadOut(BaseModel):
    doc_id: str
    task_id: str
    status: str


class DocOut(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_type: str
    size_bytes: int
    page_count: int | None = None
    status: str
    chunk_count: int
    error_msg: str | None = None
    created_at: str


class DocStatusOut(BaseModel):
    doc_id: str
    status: str
    progress: int
    stage: str
    error: str | None = None
    chunk_count: int


class ChunkItemOut(BaseModel):
    id: str
    seq: int
    content: str
    content_type: str
    page: int | None = None
    has_formula: bool
    token_count: int


class PreviewOut(BaseModel):
    doc_id: str
    total: int
    page: int
    size: int
    items: list[ChunkItemOut]


class ReindexOut(BaseModel):
    doc_id: str
    task_id: str
    status: str
