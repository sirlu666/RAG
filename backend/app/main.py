"""MathRAG 后端入口。

当前只挂载 A 负责的文档链路（/api/docs/*）。其余路由由 B/C 按契约补齐：
  B：/api/chat/stream（SSE）
  C：/api/auth/*、/api/kbs/*、/api/conversations/*
挂载方式见文件底部注释，接口口径见 docs/01 §5。
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
    description="基于 RAG 与大模型的数学答疑系统 · 契约见 docs/01-架构与接口契约.md",
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

# --- A：文档链路（已实现）---
from app.api.doc import router as doc_router  # noqa: E402

app.include_router(doc_router)

# --- B：问答链路（待 B 实现后取消注释）---
# from app.api.chat import router as chat_router
# app.include_router(chat_router)

# --- C：账号与知识库（待 C 实现后取消注释）---
# from app.api.auth import router as auth_router
# from app.api.kb import router as kb_router
# from app.api.conversations import router as conv_router
# app.include_router(auth_router)
# app.include_router(kb_router)
# app.include_router(conv_router)


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
        }
    )
