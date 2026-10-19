"""接口出入参模型。

分工：本文件由 B 主笔（聊天/SSE），A 只维护文档相关模型，C 只读不改。
新增字段只能追加，禁止改名（见 docs/01 §3、§5）。
"""

from pydantic import BaseModel, Field


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


# TODO(B)：在这里追加 SSE 事件模型（meta / citation / delta / done / error），
# 并用 tests/test_sse_contract.py 对 docs/api/mock/chat_stream.txt 做逐帧校验。


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
