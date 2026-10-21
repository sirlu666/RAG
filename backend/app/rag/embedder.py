"""向量化 — EmbeddingProvider 抽象。

三种实现，接口一致（encode 返回**归一化**的 float 向量列表）：

- HashEmbedding  (provider=dev)   ：本地哈希，确定性，仅用于跑通链路与自测；
- ApiEmbedding   (provider=api)   ：OpenAI 兼容 /embeddings，重试/截断/批处理内建；
- LocalEmbedding (provider=local) ：sentence-transformers 本地模型（默认 bge-m3），
                                    零 API 成本、断网可用。

对外入口（签名不变，B 的调用零影响）：
    embed_texts(texts) / embed_query(text) / dim() / tokenize(text)

选型由 settings.embed_provider 决定；测试用 reset_provider() 清除单例。
"""

import logging
import time
from abc import ABC, abstractmethod
import hashlib
import math
import re

logger = logging.getLogger("mathrag.embed")

from app.core.config import resolve, settings
from app.core.exceptions import AppError

try:  # 可选依赖：没装就退化为字符级分词
    import jieba

    jieba.setLogLevel(60)
except Exception:  # pragma: no cover
    jieba = None

_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """混合检索（BM25）用的分词：jieba + 中文二元组。"""
    text = (text or "").lower()
    if jieba is not None:
        tokens = [t.strip() for t in jieba.lcut(text) if t.strip()]
    else:
        tokens = re.findall(r"[a-zA-Z]+|\d+|[\u4e00-\u9fff]", text)

    # 中文补充二元组，缓解术语被切碎（"单调区间" → 单调/调区/区间）
    cjk = "".join(_CJK.findall(text))
    tokens.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
    return [t for t in tokens if t]


# --------------------------------------------------------------------------
# Provider 抽象：重试 / 截断 / 批处理 / 归一化收敛在这一层，实现类只管"怎么算"
# --------------------------------------------------------------------------

class BaseEmbedding(ABC):
    """所有 embedding 实现的契约：encode 返回归一化 float 向量，长度与输入一致。"""

    @abstractmethod
    def encode(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def dim(self) -> int: ...

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class HashEmbedding(BaseEmbedding):
    """provider=dev：确定性哈希向量，零依赖。仅供链路验证，检索质量不可用于答辩。"""

    def __init__(self, dim: int = 256):
        self._dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for text in texts:
            vec = [0.0] * self._dim
            tokens = tokenize(text) or [text.strip() or "<empty>"]  # 空文本也必须有非零向量
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                vec[value % self._dim] += 1.0 if (value >> 8) & 1 else -1.0
            vecs.append(self._normalize(vec))
        return vecs

    def dim(self) -> int:
        return self._dim


class ApiEmbedding(BaseEmbedding):
    """provider=api：OpenAI 兼容 /embeddings。输入截断、429/5xx 退避重试内建。"""

    RETRYABLE = (429, 500, 502, 503)

    def encode(self, texts: list[str]) -> list[list[float]]:
        import httpx

        base = settings.embed_api_base.rstrip("/")
        if not base or not settings.embed_api_key:
            raise AppError(4001, "Embedding 接口未配置（EMBED_API_BASE / EMBED_API_KEY）")

        out: list[list[float]] = []
        with httpx.Client(timeout=60) as client:
            for i in range(0, len(texts), settings.embed_batch):
                batch = [self._clamp(t) for t in texts[i : i + settings.embed_batch]]
                out.extend(self._post(client, base, batch))
        return out

    @staticmethod
    def _clamp(text: str) -> str:
        limit = settings.embed_max_chars
        if len(text) > limit:
            logger.warning("embedding 输入 %d 字符超上限 %d，截断（尾部公式可能丢失）",
                           len(text), limit)
            return text[:limit]
        return text

    def _post(self, client, base: str, batch: list[str]) -> list[list[float]]:
        for attempt in range(6):
            resp = client.post(
                f"{base}/embeddings",
                headers={"Authorization": f"Bearer {settings.embed_api_key}"},
                json={"model": settings.embed_model, "input": batch},
            )
            if resp.status_code in self.RETRYABLE:
                wait = min(30.0, 2.0 * (2**attempt))
                logger.warning("embedding HTTP %d，%.0fs 后重试（第 %d 次）",
                               resp.status_code, wait, attempt + 1)
                time.sleep(wait)
                continue
            break
        if resp.status_code != 200:
            raise AppError(4001, f"Embedding 调用失败：HTTP {resp.status_code}")
        data = resp.json().get("data", [])
        data.sort(key=lambda x: x.get("index", 0))
        return [self._normalize(item["embedding"]) for item in data]

    def dim(self) -> int:
        return 0  # 由服务端决定；向量库以实际写入为准


class LocalEmbedding(BaseEmbedding):
    """provider=local：sentence-transformers 本地模型，单例懒加载，断网可用。"""

    _model = None

    def _load(self):
        if LocalEmbedding._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise AppError(
                    4001, "本地 embedding 需要 sentence-transformers：pip install sentence-transformers"
                ) from exc
            path = resolve(settings.embed_local_model)
            logger.info("加载本地 embedding 模型：%s", path)
            LocalEmbedding._model = SentenceTransformer(
                str(path), device="cpu",
                cache_folder=str(settings.chroma_path.parent / "models"),
            )
            logger.info("模型加载完成，维度 %d", self.dim())
        return LocalEmbedding._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        out = []
        for v in model.encode(texts, batch_size=16, show_progress_bar=False,
                              normalize_embeddings=True):
            out.append(self._normalize(v.tolist() if hasattr(v, "tolist") else list(v)))
        return out

    def dim(self) -> int:
        return int(LocalEmbedding._model.get_sentence_embedding_dimension()) \
            if LocalEmbedding._model is not None else 1024


_PROVIDERS = {
    "dev": HashEmbedding,
    "api": ApiEmbedding,
    "local": LocalEmbedding,
}

_provider: BaseEmbedding | None = None


def get_provider() -> BaseEmbedding:
    """按 settings.embed_provider 返回单例；换配置后需 reset_provider()。"""
    global _provider
    if _provider is None:
        cls = _PROVIDERS.get(settings.embed_provider)
        if cls is None:
            raise AppError(4001, f"未知的 EMBED_PROVIDER：{settings.embed_provider}")
        _provider = cls()
    return _provider


def reset_provider() -> None:
    """测试/换配置后清除单例。"""
    global _provider
    _provider = None


# --------------------------------------------------------------------------
# 对外入口（签名不变）
# --------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_provider().encode(texts)


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def dim() -> int:
    d = get_provider().dim()
    return d if d else settings.embed_dim
