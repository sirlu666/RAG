"""测试环境隔离：**必须在导入 app 之前**设好环境变量。

- 数据库 / 向量库都指向临时目录，不碰开发用的 data/；
- EMBED_PROVIDER=dev + VECTOR_BACKEND=local：零外部依赖，跑得快；
- MOCK_LLM=true：不调真实模型，SSE 链路仍完整；
- 阈值调到 0.05：dev 哈希向量的分数分布与 bge-m3 不同，避免测试被误判为"拒答"。
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="mathrag-test-")

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/app.db"
os.environ["CHROMA_DIR"] = f"{_TMP}/chroma"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["VECTOR_BACKEND"] = "local"
os.environ["EMBED_PROVIDER"] = "dev"
os.environ["MOCK_LLM"] = "true"
os.environ["RERANK_API_BASE"] = ""
os.environ["RERANK_API_KEY"] = ""
os.environ["RELEVANCE_THRESHOLD"] = "0.05"

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import chat_models  # noqa: F401  # 建表前必须先导入
from app.db.models import Chunk, Document, KnowledgeBase, User
from app.db.session import SessionLocal
from app.main import app
from app.rag.embedder import embed_texts
from app.rag.retriever import invalidate_bm25_cache
from app.rag.vectorstore import get_store

SAMPLE_CHUNKS = [
    (
        "concept",
        (
            "一般地，设函数 f(x) 的定义域为 I，如果对于定义域 I 内某个区间 D 上的任意两个自变量的值 x1，x2，"
            "当 x1<x2 时，都有 f(x1)<f(x2)，那么就说函数 f(x) 在区间 D 上是增函数。"
        ),
        132,
    ),
    (
        "example",
        (
            "例 3 判断函数 f(x)=x^2+2x 在区间上的单调性。解：f(x)=(x+1)^2-1，其图象是开口向上的抛物线，"
            "对称轴为 x=-1，所以在 (-∞,-1] 上单调递减，在 [-1,+∞) 上单调递增。"
        ),
        134,
    ),
    (
        "theory",
        (
            "求根公式：一元二次方程 ax^2+bx+c=0（a≠0）的解为 x=(-b±√(b^2-4ac))/(2a)，"
            "其中判别式 Δ=b^2-4ac 决定实根个数。"
        ),
        156,
    ),
]


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def seeded(client):
    """造一个用户 alice + 知识库 + 3 条 chunk + 向量，供检索测试使用。"""
    with SessionLocal() as db:
        alice = User(username="alice")
        bob = User(username="bob")
        db.add_all([alice, bob])
        db.flush()

        kb = KnowledgeBase(user_id=alice.id, name="必修一")
        db.add(kb)
        db.flush()

        doc = Document(
            kb_id=kb.id,
            user_id=alice.id,
            filename="人教A版必修一.pdf",
            stored_path="tmp/none.pdf",
            file_type="pdf",
            size_bytes=1024,
            status="ready",
            chunk_count=len(SAMPLE_CHUNKS),
        )
        db.add(doc)
        db.flush()

        chunks = []
        for seq, (content_type, content, page) in enumerate(SAMPLE_CHUNKS):
            chunk = Chunk(
                doc_id=doc.id,
                kb_id=kb.id,
                user_id=alice.id,
                seq=seq,
                content=content,
                content_type=content_type,
                page=page,
                token_count=len(content),
            )
            chunks.append(chunk)
        db.add_all(chunks)
        db.commit()

        store = get_store()
        store.upsert(
            ids=[c.id for c in chunks],
            vectors=embed_texts([c.content for c in chunks]),
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    "chunk_id": c.id,
                    "user_id": alice.id,
                    "kb_id": kb.id,
                    "doc_id": doc.id,
                    "doc_name": doc.filename,
                    "subject": "highschool_math",
                    "content_type": c.content_type,
                    "seq": c.seq,
                    "has_formula": "\\" in c.content or "^" in c.content,
                    "page": c.page or 0,
                }
                for c in chunks
            ],
        )
        invalidate_bm25_cache()
        yield {"alice": alice.id, "bob": bob.id, "kb_id": kb.id, "doc_id": doc.id,
               "chunk_ids": [c.id for c in chunks]}


@pytest.fixture()
def alice_headers():
    return {"Authorization": "Bearer dev:alice"}


@pytest.fixture()
def bob_headers():
    return {"Authorization": "Bearer dev:bob"}


@pytest.fixture()
def settings_obj():
    return settings
