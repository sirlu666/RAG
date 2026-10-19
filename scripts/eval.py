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

            if with_answer:
                answer = asyncio.run(
                    RagPipeline(db).answer(question=item["question"], kb_ids=item["kb_ids"])
                )
                if answer["refused"]:
                    refused += 1
                if any(c["chunk_id"] in gold for c in answer["citations"]):
                    cite_hit += 1

    total = len(items)
    report = {
        "mode": mode,
        "dataset": str(dataset),
        "n": total,
        "recall_at_5": round(recall_hits / total, 4),
        "mrr": round(rr_total / total, 4),
        "avg_retrieval_ms": round(sum(retrieval_ms) / total, 1),
        "with_answer": with_answer,
        "refused_rate": round(refused / total, 4) if with_answer else None,
        "citation_hit_rate": round(cite_hit / total, 4) if with_answer else None,
        "config": {
            "top_k": settings.retrieval_top_k,
            "rrf_k": settings.rrf_k,
            "rerank_top_n": settings.rerank_top_n,
            "threshold": settings.relevance_threshold,
            "embed_provider": settings.embed_provider,
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
