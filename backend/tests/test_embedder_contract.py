"""EmbeddingProvider 契约测试：三种实现走同一组断言。

不加载真实模型、不发真实请求（api/local 均用替身），秒级完成。
"""

import sys
import types

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.rag.embedder import (
    ApiEmbedding,
    HashEmbedding,
    LocalEmbedding,
    embed_texts,
    get_provider,
    reset_provider,
    tokenize,
)

CONTRACT_TEXTS = ["泰勒公式", "设 f(x) 在 [a,b] 上连续", ""]


def _assert_contract(vectors: list[list[float]]):
    assert len(vectors) == len(CONTRACT_TEXTS)
    for v in vectors:
        assert all(isinstance(x, float) for x in v)
        norm = sum(x * x for x in v) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-5)  # 归一化


# ---------- dev：真实跑（快） ----------

def test_hash_contract_and_determinism():
    v1 = HashEmbedding(256).encode(CONTRACT_TEXTS)
    v2 = HashEmbedding(256).encode(CONTRACT_TEXTS)
    _assert_contract(v1)
    assert v1 == v2  # 确定性


def test_hash_distinguishes_topics():
    h = HashEmbedding(256)
    a = h.encode(["泰勒公式"])[0]
    b = h.encode(["完全无关的另一个主题内容"])[0]
    assert a != b


# ---------- api：mock HTTP ----------

class _FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


class _FakeClient:
    """可编程的 httpx.Client 替身：按脚本依次返回响应。"""

    script: list = []
    calls: list = []

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None, timeout=None):
        type(self).calls.append(json)
        resp = self.script.pop(0)
        if resp.status_code == 200 and "data" not in resp._payload:
            inputs = json["input"]
            resp._payload = {
                "data": [{"index": i, "embedding": [1.0] * 8} for i in range(len(inputs))]
            }
        return resp


@pytest.fixture()
def fake_client(monkeypatch):
    monkeypatch.setattr(settings, "embed_api_base", "https://fake/v1")
    monkeypatch.setattr(settings, "embed_api_key", "k")
    client = _FakeClient()
    monkeypatch.setattr("httpx.Client", lambda **kw: client)
    monkeypatch.setattr("app.rag.embedder.time.sleep", lambda s: None)
    return client


def test_api_truncates_overlong_input(fake_client):
    fake_client.script = [_FakeResp(200)]
    settings.embed_max_chars = 100
    out = ApiEmbedding().encode(["x" * 5000, "短文本"])
    assert len(out) == 2
    sent = fake_client.calls[0]["input"]
    assert len(sent[0]) == 100  # 被截断
    assert sent[1] == "短文本"


def test_api_retries_on_429_then_succeeds(fake_client):
    fake_client.script = [_FakeResp(429), _FakeResp(200)]
    out = ApiEmbedding().encode(["泰勒公式"])
    assert len(out) == 1 and len(out[0]) == 8
    assert len(fake_client.script) == 0  # 两次都消费掉了


def test_api_gives_up_after_retries(fake_client):
    fake_client.script = [_FakeResp(429) for _ in range(6)]
    with pytest.raises(AppError):
        ApiEmbedding().encode(["泰勒公式"])


# ---------- local：替身模型 ----------

class _FakeST:
    def __init__(self, *a, **kw):
        pass

    def get_sentence_embedding_dimension(self):
        return 8

    def encode(self, texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True):
        return [[0.5] * 8 for _ in texts]


def test_local_loads_once_and_normalizes(monkeypatch):
    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = _FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)
    monkeypatch.setattr(settings, "embed_local_model", "data/models/bge-m3")
    monkeypatch.setattr(LocalEmbedding, "_model", None)  # 清单例，测完自动还原

    emb = LocalEmbedding()
    out = emb.encode(CONTRACT_TEXTS)
    _assert_contract(out)
    assert LocalEmbedding._model is emb._load()  # 单例


# ---------- 工厂与公开入口 ----------

def test_factory_and_reset(monkeypatch):
    monkeypatch.setattr(settings, "embed_provider", "dev")
    reset_provider()
    assert isinstance(get_provider(), HashEmbedding)
    reset_provider()
    monkeypatch.setattr(settings, "embed_provider", "nope")
    with pytest.raises(AppError):
        get_provider()
    reset_provider()
    monkeypatch.setattr(settings, "embed_provider", "dev")


def test_public_embed_texts_uses_provider(monkeypatch):
    monkeypatch.setattr(settings, "embed_provider", "dev")
    reset_provider()
    out = embed_texts(["泰勒公式"])
    assert len(out) == 1 and len(out[0]) == settings.embed_dim


def test_tokenize_keeps_bigrams():
    tokens = tokenize("单调区间")
    assert "单调" in tokens and "区间" in tokens
