"""向量化。

provider=dev  ：本地哈希向量（零依赖、确定性），**只用于跑通链路与自测，检索质量不可用于答辩**。
provider=api  ：调用 OpenAI 兼容的 /embeddings 接口（bge-m3 等）。
"""

import hashlib
import math
import re

from app.core.config import settings
from app.core.exceptions import AppError

try:  # 可选依赖：没装就退化为字符级分词
    import jieba

    jieba.setLogLevel(60)
except Exception:  # pragma: no cover
    jieba = None

_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    if jieba is not None:
        tokens = [t.strip() for t in jieba.lcut(text) if t.strip()]
    else:
        tokens = re.findall(r"[a-zA-Z]+|\d+|[\u4e00-\u9fff]", text)

    # 中文补充二元组，缓解术语被切碎（"单调区间" → 单调/调区/区间）
    cjk = "".join(_CJK.findall(text))
    tokens.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
    return [t for t in tokens if t]


def _hash_vector(tokens: list[str], dim: int) -> list[float]:
    vec = [0.0] * dim
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        idx = value % dim
        sign = 1.0 if (value >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _api_embed(texts: list[str]) -> list[list[float]]:
    import httpx

    base = settings.embed_api_base.rstrip("/")
    if not base or not settings.embed_api_key:
        raise AppError(4001, "Embedding 接口未配置（EMBED_API_BASE / EMBED_API_KEY）")

    out: list[list[float]] = []
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(texts), settings.embed_batch):
            batch = texts[i : i + settings.embed_batch]
            resp = client.post(
                f"{base}/embeddings",
                headers={"Authorization": f"Bearer {settings.embed_api_key}"},
                json={"model": settings.embed_model, "input": batch},
            )
            if resp.status_code != 200:
                raise AppError(4001, f"Embedding 调用失败：HTTP {resp.status_code}")
            data = resp.json().get("data", [])
            data.sort(key=lambda x: x.get("index", 0))
            out.extend([item["embedding"] for item in data])
    return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embed_provider == "api":
        return _api_embed(texts)
    return [_hash_vector(tokenize(t), settings.embed_dim) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def dim() -> int:
    return settings.embed_dim
