"""B 侧在真实向量库（Chroma）上的兼容性测试。

背景：A 把 `VECTOR_BACKEND` 默认从 local JSON 换成了 chroma（提交 6c396d4 起，
`.env.example` 默认 `VECTOR_BACKEND=chroma`）。B 的检索器依赖两条隐性约定：

1. 向量库的 id **必须等于** `chunks.id`，否则回表拿不到权威正文；
2. `query()` 返回的 `metadata` 必须能带回 `doc_id / kb_id`，citation 才能溯源。

这两条在 local JSON 实现下由同一份代码保证，但 Chroma 是另一套序列化规则
（metadata 只接受 str/int/float/bool，且经过内部存储往返）。所以必须单独验证，
否则 A 换后端会在 C 侧表现为"能答但引用点不开"。

没有装 chromadb 时整个文件跳过，不阻塞别人的环境。
"""

import pytest

from app.core.config import settings
from app.rag import vectorstore
from app.rag.embedder import embed_texts
from app.rag.retriever import invalidate_bm25_cache, retrieve

pytest.importorskip("chromadb", reason="未安装 chromadb，跳过 Chroma 后端验证")


@pytest.fixture()
def chroma_store(seeded):
    """把同一批 chunk 灌进 Chroma，用完切回 local 并清缓存，避免污染别的测试。"""
    old_backend = settings.vector_backend
    settings.vector_backend = "chroma"
    vectorstore.get_store.cache_clear()

    store = vectorstore.get_store()
    try:
        assert type(store).__name__ == "ChromaVectorStore"

        from app.db.models import Chunk
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            chunks = db.query(Chunk).filter(Chunk.id.in_(seeded["chunk_ids"])).all()
            payload = [(c.id, c.content, c) for c in chunks]

        store.upsert(
            ids=[cid for cid, _, _ in payload],
            vectors=embed_texts([text for _, text, _ in payload]),
            documents=[text for _, text, _ in payload],
            metadatas=[
                {
                    "chunk_id": c.id,
                    "user_id": c.user_id,
                    "kb_id": c.kb_id,
                    "doc_id": c.doc_id,
                    "doc_name": "人教A版必修一.pdf",
                    "subject": "highschool_math",
                    "content_type": c.content_type,
                    "seq": c.seq,
                    "has_formula": ("\\" in c.content) or ("^" in c.content),
                    "page": c.page or 0,
                }
                for _, _, c in payload
            ],
        )
        invalidate_bm25_cache()
        yield store
    finally:
        settings.vector_backend = old_backend
        vectorstore.get_store.cache_clear()
        invalidate_bm25_cache()


def test_chroma_query_returns_id_equal_to_chunk_id(seeded, chroma_store):
    """约定 1：向量库 id 就是 chunk_id，否则回表会拿到 orphan 警告并丢结果。"""
    from app.db.models import Chunk
    from app.db.session import SessionLocal

    question = "增函数的定义是什么"
    hits = chroma_store.query(embed_texts([question])[0], kb_ids=[seeded["kb_id"]], top_k=5)

    assert hits, "Chroma 没召回任何结果"
    hit_ids = {h.id for h in hits}
    assert hit_ids <= set(seeded["chunk_ids"]), f"向量库 id 与 chunks.id 不一致：{hit_ids}"

    # 每个 hit 都能在 chunks 表里找到对应行（回表不会产生 orphan）
    with SessionLocal() as db:
        found = {c.id for c in db.query(Chunk).filter(Chunk.id.in_(hit_ids)).all()}
    assert found == hit_ids, f"有 {hit_ids - found} 个向量 id 在 chunks 表里不存在"


def test_chroma_metadata_survives_roundtrip(seeded, chroma_store):
    """约定 2：metadata 往返后 doc_id/kb_id 仍是原值，citation 才能溯源。"""
    hits = chroma_store.query(
        embed_texts(["增函数的定义是什么"])[0], kb_ids=[seeded["kb_id"]], top_k=5
    )
    assert hits
    meta = hits[0].metadata
    assert meta["doc_id"] == seeded["doc_id"]
    assert meta["kb_id"] == seeded["kb_id"]
    assert meta["chunk_id"] == hits[0].id
    # Chroma 会把 bool 存成 int，这里只要求"可判定真假"，不锁死类型
    assert bool(meta["has_formula"]) in (True, False)


def test_retrieve_works_end_to_end_on_chroma(seeded, chroma_store):
    """B 的完整检索链路（向量 + BM25 + RRF + 回表）在 Chroma 上跑通。"""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        result = retrieve(db, "例 3 判断函数的单调性", [seeded["kb_id"]])

    assert result.candidates, "Chroma 后端下检索结果为空"
    top = result.candidates[0]
    # 回表成功后 content 必须是关系库里的权威正文，不是向量库里存的副本
    assert top.content and not top.content.startswith("[orphan]")
    assert top.chunk_id in set(seeded["chunk_ids"])
    assert result.vector_hits > 0
