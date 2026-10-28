"""A 的接口出入参模型（只覆盖 6 个文档接口）。

新增字段只能追加，禁止改名（见 docs/A-接口与边界.md）。
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
    category: str = ''
    metadata_version: str = ''
    knowledge_points: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)
    difficulty: str | None = None


class DocListResponse(BaseModel):
    code: int
    message: str
    data: list[DocOut]
    request_id: str


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


# ===================== B：问答链路出入参（契约见 docs/01 §6） =====================


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    kb_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    stream: bool = True


class MetaEvent(BaseModel):
    message_id: str
    conversation_id: str
    retrieval_ms: int
    hits: int


class CitationEvent(BaseModel):
    index: int
    chunk_id: str
    doc_id: str  # C 跳转原文用：GET /api/docs/{doc_id}/preview 定位片段
    doc_name: str
    page: int | None = None
    snippet: str
    score: float
    content_type: str
    # 原文定位：PDF 用 page；markdown/网页类语料 page 恒为 null，改用字符区间。
    # 两者都给出，C 按 content_type 选一种即可。
    seq: int = 0
    char_start: int = 0
    char_end: int = 0


class DeltaEvent(BaseModel):
    text: str


class DoneEvent(BaseModel):
    message_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    first_token_ms: int
    confidence: float
    # 以下为追加字段（只加不改），前端可忽略
    model: str | None = None
    refused: bool = False
    # 模型读了资料仍声明"未找到依据"（refused 是管线在调模型前拒答，两者不同）
    declined: bool = False
    answer: str | None = None
    citations: list[dict] | None = None


class ErrorEvent(BaseModel):
    code: int
    message: str


SSE_EVENT_MODELS = {
    "meta": MetaEvent,
    "citation": CitationEvent,
    "delta": DeltaEvent,
    "done": DoneEvent,
    "error": ErrorEvent,
}
