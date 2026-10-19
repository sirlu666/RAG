"""MathRAG 后端入口。

P0 阶段只保证：服务能起、/docs 能开、/api/health 能通。
各模块的路由在 P1 逐步挂载（见 docs/02-开发流程与里程碑.md）。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ROOT_DIR, settings

APP_NAME = "MathRAG API"
API_PREFIX = "/api"


def _ensure_dirs() -> None:
    """启动时确保数据目录存在（docker 首次启动时卷是空的）。"""
    for d in (settings.chroma_dir, settings.upload_dir):
        Path(ROOT_DIR / d if not Path(d).is_absolute() else d).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_dirs()
    yield


app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    description="基于 RAG 与大模型的数学答疑系统 · 接口契约见 docs/01-架构与接口契约.md",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- P1 起逐个取消注释挂载 ---
# from app.api import auth, chat, doc, kb, feedback
# app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
# app.include_router(kb.router, prefix=f"{API_PREFIX}/kbs", tags=["knowledge-base"])
# app.include_router(doc.router, prefix=f"{API_PREFIX}/docs", tags=["document"])
# app.include_router(chat.router, prefix=f"{API_PREFIX}/chat", tags=["chat"])
# app.include_router(feedback.router, prefix=f"{API_PREFIX}/feedback", tags=["feedback"])


@app.get(f"{API_PREFIX}/health", tags=["system"], summary="健康检查")
def health() -> dict:
    """返回各依赖的连通性；P1 起补充 db / chroma / llm 的真实探活。"""
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "app": "up",
            "env": settings.app_env,
            "db": "not_checked",
            "chroma": "not_checked",
            "llm": "not_checked",
            "mock_llm": settings.mock_llm,
        },
    }
