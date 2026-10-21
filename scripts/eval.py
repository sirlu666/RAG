"""B10 · 评估脚本：Recall@5 / MRR / 拒答率 + 三档消融。

为什么"从 chunk 反推出题"：gold 天然存在（题目就是从这条 chunk 生成的），
不必人工标注；缺点是偏容易、偏原文措辞，答辩时要如实说明。

用法（在仓库根目录执行，依赖 .venv）：
    python scripts/eval.py --build --kb kb_xx --limit 80 --out eval/math_80.jsonl
    python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid
    python scripts/eval.py --run --dataset eval/math_80.jsonl --mode vector
    python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid+rerank
    python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid --with-answer
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.models import Chunk
from app.db.session import SessionLocal
from app.rag.pipeline import RagPipeline
from app.rag.retriever import retrieve

REPORT_DIR = ROOT / "eval" / "reports"
_QUESTION_NOISE = re.compile(r"^(例|练习|习题)\s*\d*[\.、:]?\s*")


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    clean = "".join(text.split())
    if len(clean) < n:
        return {clean} if clean else set()
    return {clean[i : i + n] for i in range(len(clean) - n + 1)}


def query_overlap(question: str, content: str) -> float:
    """query 与 gold chunk 的字面重合率（字符 2-gram Jaccard）。

    这是评测集本身的自检指标，不是检索指标。反推出题必然复用原文措辞，
    重合率越高，测的越接近"照抄能否命中"，而不是语义检索能力。
    答辩时要主动声明这一点，否则 Recall 会被质疑虚高。
    """
    q = _char_ngrams(question)
    c = _char_ngrams(content)
    if not q or not c:
        return 0.0
    return round(len(q & c) / len(q | c), 4)


def _leak_level(mean_overlap: float) -> str:
    if mean_overlap >= 0.6:
        return "high（近于照抄，指标偏乐观）"
    if mean_overlap >= 0.3:
        return "medium（有字面重合，需说明）"
    return "low（措辞已改写，较可信）"



def _make_question(content: str, content_type: str) -> str | None:
    """从 chunk 反推一个问题；返 None 表示这条不适合出题。"""
    text = " ".join(content.split())
    if len(text) < 40:
        return None

    if content_type == "example":
        # 例题：取"解："之前的题干
        stem = re.split(r"(解[:：]|解答[:：]|分析[:：])", text)[0].strip()
        stem = _QUESTION_NOISE.sub("", stem)
        if 15 <= len(stem) <= 400:
            return f"{stem} 请写出完整解答过程。"
        return None

    # 概念/定理：用首句提问，保留术语，便于 BM25 精确命中
    first = re.split(r"[。！？]", text)[0].strip()
    if 10 <= len(first) <= 200:
        return f"请说明：{first}？"
    return None


def build_dataset(kb_id: str, limit: int, out: Path) -> None:
    with SessionLocal() as db:
        rows = (
            db.query(Chunk)
            .filter(Chunk.kb_id == kb_id)
            .order_by(Chunk.doc_id, Chunk.seq)
            .all()
        )

    items: list[dict] = []
    for chunk in rows:
        question = _make_question(chunk.content, chunk.content_type)
        if not question:
            continue
        items.append(
            {
                "id": f"q{len(items) + 1:03d}",
                "question": question,
                "kb_ids": [chunk.kb_id],
                "gold_chunk_ids": [chunk.id],
                "gold_doc_id": chunk.doc_id,
                "content_type": chunk.content_type,
                "page": chunk.page,
                # 评测集自检：query 与 gold 原文的字面重合度，越高指标越偏乐观
                "query_overlap": query_overlap(question, chunk.content),
            }
        )
        if len(items) >= limit:
            break

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n",
        encoding="utf-8",
    )
    print(f"写入 {len(items)} 题 → {out}")
    if items:
        mean_overlap = sum(i["query_overlap"] for i in items) / len(items)
        print(
            f"query 字面重合度均值 {mean_overlap:.2f} → 泄漏等级 {_leak_level(mean_overlap)}"
        )
    if len(items) < limit:
        print(f"注意：可用题目不足 {limit} 条（语料 chunk 少或过短），先补语料再跑评估。")


def load_dataset(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def _apply_mode(mode: str) -> None:
    settings.hybrid_enabled = mode in ("hybrid", "hybrid+rerank")
    if mode == "hybrid+rerank" and not (settings.rerank_api_base and settings.rerank_api_key):
        print("警告：RERANK_API_BASE/KEY 未配置，hybrid+rerank 实际等于 hybrid。")


def run_eval(dataset: Path, mode: str, with_answer: bool, limit: int | None) -> dict:
    items = load_dataset(dataset)
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit("数据集为空，先用 --build 生成题目")

    _apply_mode(mode)

    recall_hits = 0
    top1_hits = 0
    rr_total = 0.0
    refused = 0
    cite_hit = 0
    retrieval_ms: list[int] = []

    with SessionLocal() as db:
        for item in items:
            result = retrieve(db, item["question"], item["kb_ids"])
            ranked = [c.chunk_id for c in result.candidates[:5]]
            retrieval_ms.append(result.retrieval_ms)

            gold = set(item["gold_chunk_ids"])
            hit_rank = next((i for i, cid in enumerate(ranked, start=1) if cid in gold), None)
            if hit_rank:
                recall_hits += 1
                rr_total += 1.0 / hit_rank
                if hit_rank == 1:
                    top1_hits += 1

            if with_answer:
                answer = asyncio.run(
                    RagPipeline(db).answer(question=item["question"], kb_ids=item["kb_ids"])
                )
                if answer["refused"]:
                    refused += 1
                if any(c["chunk_id"] in gold for c in answer["citations"]):
                    cite_hit += 1

    total = len(items)
    overlaps = [i.get("query_overlap") for i in items if i.get("query_overlap") is not None]
    mean_overlap = round(sum(overlaps) / len(overlaps), 4) if overlaps else None
    report = {
        "mode": mode,
        "dataset": str(dataset),
        "n": total,
        "recall_at_5": round(recall_hits / total, 4),
        "recall_at_1": round(top1_hits / total, 4),
        "mrr": round(rr_total / total, 4),
        "avg_retrieval_ms": round(sum(retrieval_ms) / total, 1),
        "with_answer": with_answer,
        "refused_rate": round(refused / total, 4) if with_answer else None,
        "citation_hit_rate": round(cite_hit / total, 4) if with_answer else None,
        # --- 评测集可信度自检（不是检索指标）---
        "query_overlap_mean": mean_overlap,
        "leak_level": _leak_level(mean_overlap) if mean_overlap is not None else "unknown",
        "caveat": (
            "题目由 gold chunk 反推（query 复用原文措辞），属于 in-corpus 检索，"
            "指标偏乐观；query_overlap_mean 越高越接近照抄命中。"
            "答辩时应同时说明这一点，并附小样本人工改写题的对照结果。"
        ),
        "config": {
            "top_k": settings.retrieval_top_k,
            "rrf_k": settings.rrf_k,
            "rerank_top_n": settings.rerank_top_n,
            "threshold": settings.relevance_threshold,
            "embed_provider": settings.embed_provider,
            "vector_backend": settings.vector_backend,
            "hybrid_enabled": settings.hybrid_enabled,
            "rerank_enabled": bool(settings.rerank_api_base and settings.rerank_api_key),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = REPORT_DIR / f"{stamp}_{mode.replace('+', '-')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"报告 → {out}")
    if settings.embed_provider == "dev":
        print("提醒：EMBED_PROVIDER=dev 是哈希向量，本次指标只能验证链路，不能写进答辩。")
    if report["leak_level"].startswith(("high", "medium")):
        print(f"提醒：评测集泄漏等级 {report['leak_level']}，Recall 偏乐观，答辩须同时说明。")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="B 侧检索/生成评估")
    parser.add_argument("--build", action="store_true", help="从 chunk 反推评估集")
    parser.add_argument("--run", action="store_true", help="跑评估（不带 --build 时的默认行为）")
    parser.add_argument("--kb", default="", help="--build 时指定知识库 id")
    parser.add_argument("--out", default="eval/math_80.jsonl")
    parser.add_argument("--dataset", default="eval/math_80.jsonl")
    parser.add_argument("--mode", default="hybrid", choices=["vector", "hybrid", "hybrid+rerank"])
    parser.add_argument("--with-answer", action="store_true", help="连生成一起跑（需模型 key）")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.build:
        if not args.kb:
            raise SystemExit("--build 需要 --kb")
        build_dataset(args.kb, args.limit or 80, ROOT / args.out)
        return

    run_eval(ROOT / args.dataset, args.mode, args.with_answer, args.limit)


if __name__ == "__main__":
    main()
