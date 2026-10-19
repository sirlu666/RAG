"""向量存储抽象。

- LocalVectorStore：零依赖的文件实现（默认），数据落在 data/chroma/local_store.json；
- ChromaVectorStore：装了 chromadb 时可选，接口一致，metadata 口径不变。
切换：VECTOR_BACKEND=auto|local|chroma（auto = 有 chromadb 就用它）。
"""

import json
import math
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@dataclass
class VectorHit:
    id: str
    score: float
    metadata: dict = field(default_factory=dict)
    document: str = ""


class BaseVectorStore(ABC):
    @abstractmethod
    def upsert(self, ids: list[str], vectors: list[list[float]], documents: list[str], metadatas: list[dict]) -> None: ...

    @abstractmethod
    def delete_doc(self, doc_id: str) -> None: ...

    @abstractmethod
    def query(self, vector: list[float], kb_ids: list[str], top_k: int) -> list[VectorHit]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def ids(self) -> set[str]: ...


class LocalVectorStore(BaseVectorStore):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._items: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._items = {item["id"]: item for item in raw.get("items", [])}
            except Exception:
                self._items = {}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"items": list(self._items.values())}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def upsert(self, ids, vectors, documents, metadatas) -> None:
        with self._lock:
            for i, _id in enumerate(ids):
                self._items[_id] = {
                    "id": _id,
                    "v": [round(float(x), 6) for x in vectors[i]],
                    "d": documents[i],
                    "m": metadatas[i],
                }
            self._save()

    def delete_doc(self, doc_id: str) -> None:
        with self._lock:
            self._items = {k: v for k, v in self._items.items() if v["m"].get("doc_id") != doc_id}
            self._save()

    def query(self, vector, kb_ids, top_k) -> list[VectorHit]:
        if not kb_ids:
            return []
        allowed = set(kb_ids)
        with self._lock:
            items = list(self._items.values())

        scored: list[tuple[float, dict]] = []
        for item in items:
            if item["m"].get("kb_id") not in allowed:
                continue
            scored.append((_cosine(vector, item["v"]), item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            VectorHit(id=item["id"], score=score, metadata=item["m"], document=item["d"])
            for score, item in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self._items)

    def ids(self) -> set[str]:
        return set(self._items.keys())


class ChromaVectorStore(BaseVectorStore):
    """需要 `pip install chromadb`。分数 = 1 - cosine_distance。"""

    def __init__(self):
        import chromadb

        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, ids, vectors, documents, metadatas) -> None:
        self.collection.upsert(ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas)

    def delete_doc(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    def query(self, vector, kb_ids, top_k) -> list[VectorHit]:
        if not kb_ids:
            return []
        res = self.collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where={"kb_id": {"$in": kb_ids}},
            include=["documents", "metadatas", "distances"],
        )
        hits: list[VectorHit] = []
        for i, _id in enumerate(res.get("ids", [[]])[0]):
            distance = res.get("distances", [[]])[0][i]
            hits.append(
                VectorHit(
                    id=_id,
                    score=1.0 - float(distance),
                    metadata=res.get("metadatas", [[]])[0][i] or {},
                    document=res.get("documents", [[]])[0][i] or "",
                )
            )
        return hits

    def count(self) -> int:
        return int(self.collection.count())

    def ids(self) -> set[str]:
        return set(self.collection.get(include=[])["ids"])


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


@lru_cache(maxsize=1)
def get_store() -> BaseVectorStore:
    backend = settings.vector_backend
    if backend in ("auto", "chroma"):
        try:
            return ChromaVectorStore()
        except Exception:
            if backend == "chroma":
                raise
    return LocalVectorStore(settings.chroma_path / "local_store.json")
