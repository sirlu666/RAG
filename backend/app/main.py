"""MathRAG 后端入口 —— A 的文档链路（/api/docs/*）+ B 的问答链路（/api/chat/stream）。

C 的路由（auth/kbs/conversations）不在本服务内装配，按契约接入。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import ok, register_exception_handlers
from app.db.session import ensure_dirs, init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

APP_NAME = "MathRAG API"
API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    version="0.2.0",
    description="基于 RAG 与大模型的数学答疑系统 · 契约见 docs/A-接口与边界.md",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# --- A：文档链路 ---
from app.api.doc import router as doc_router  # noqa: E402

app.include_router(doc_router)

# --- B：问答链路（conversations/messages 表在这里注册，create_all 才会建）---
from app.api.chat import router as chat_router  # noqa: E402
from app.db import chat_models as _chat_models  # noqa: E402,F401
from app.rag import reranker  # noqa: E402

app.include_router(chat_router)


@app.get(f"{API_PREFIX}/health", tags=["system"], summary="健康检查")
def health() -> dict:
    from sqlalchemy import text

    from app.db.session import SessionLocal
    from app.rag.vectorstore import get_store

    db_ok, vector_count = "down", 0
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = "up"
        vector_count = get_store().count()
    except Exception:
        pass

    return ok(
        {
            "app": "up",
            "env": settings.app_env,
            "db": db_ok,
            "vectors": vector_count,
            "embed_provider": settings.embed_provider,
            "vector_backend": settings.vector_backend,
            # B 追加：模型是否就绪（不含密钥本身）
            "llm": {
                "model": settings.deepseek_model,
                "configured": bool(settings.deepseek_api_key),
                "mock": settings.mock_llm,
            },
            "retrieval": {
                "hybrid": settings.hybrid_enabled,
                "rerank": reranker.is_enabled(),
                "rerank_provider": settings.rerank_provider,
                "top_k": settings.retrieval_top_k,
                "rerank_top_n": settings.rerank_top_n,
                "threshold": settings.relevance_threshold,
            },
        }
    )
