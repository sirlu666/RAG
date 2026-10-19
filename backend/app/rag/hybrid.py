"""B6 · 混合召回的基础件：BM25 + RRF。

为什么需要它（答辩要点）：
- 数学题干常含精确符号与专有术语（"f(x)=x²+2x"、"单调递增"），BM25 的精确匹配比向量稳；
- 学生的口语化提问（"求导" ≈ "导数计算"）向量更能兜住；
- 两路分数不同量纲，用 RRF 按排名融合，免去归一化参数的拍脑袋。
"""

from __future__ import annotations

import math
from collections import Counter

from app.rag.embedder import tokenize


def _bm25_tokens(text: str) -> list[str]:
    """BM25 用的分词：在 A 的分词基础上去掉单字汉字。

    单字（"的""是""在"）几乎不携带区分度，留着会让任何问题都能命中任何文档，
    表现为"问量子力学也能召回数学教材"。二元组已经在 tokenize 里补过，不会丢词。
    """
    return [
        token
        for token in tokenize(text)
        if not (len(token) == 1 and "\u4e00" <= token <= "\u9fff")
    ]


class BM25Index:
    """纯 Python BM25（Okapi），语料 ≤1 万 chunk 足够，不引第三方依赖。"""

    def __init__(self, docs: list[tuple[str, str]], k1: float = 1.5, b: float = 0.75) -> None:
        """docs: [(chunk_id, content)]，顺序即返回顺序。"""
        self.k1 = k1
        self.b = b
        self._ids = [d[0] for d in docs]
        self._tfs: list[Counter] = []
        self._lens: list[int] = []
        self._df: Counter = Counter()
        for _, text in docs:
            tokens = _bm25_tokens(text)
            tf = Counter(tokens)
            self._tfs.append(tf)
            self._lens.append(len(tokens))
            for term in tf:
                self._df[term] += 1
        self._n = len(docs)
        self._avg_len = (sum(self._lens) / self._n) if self._n else 0.0

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._n:
            return []
        terms = _bm25_tokens(query)
        if not terms:
            return []

        scores: list[tuple[float, str]] = []
        for idx, tf in enumerate(self._tfs):
            score = 0.0
            length = self._lens[idx] or 1
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
                denom = freq + self.k1 * (1 - self.b + self.b * length / (self._avg_len or 1))
                score += idf * freq * (self.k1 + 1) / denom
            if score > 0:
                scores.append((score, self._ids[idx]))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [(cid, round(score, 4)) for score, cid in scores[:top_k]]

    def __len__(self) -> int:
        return self._n


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)，rank 从 1 开始。

    传入多路召回的 id 有序列表，返回 {chunk_id: fused_score}（已按分数降序无法保证，调用方排序）。
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        for pos, chunk_id in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + pos)
    return fused


def order_by_rrf(fused: dict[str, float]) -> list[str]:
    return [cid for cid, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)]
