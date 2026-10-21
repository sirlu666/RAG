"""B1 · 真实模型生成验证：首 token 延迟 / 端到端延迟 / 引用合法性 / 拒答正确性。

与 eval.py 的分工：
- eval.py 量**检索**（Recall@5 / MRR），不依赖大模型，可以离线跑
- 本脚本量**生成**，必须配真实 DEEPSEEK_API_KEY，MOCK 模式下数字无意义（脚本会拒绝跑）

它检查三件答辩会被追问的事：
1. 首 token 延迟（用户"感觉快不快"的真实指标，不是总耗时）
2. 引用编号是否越界 —— 幻觉防线第三层。LLM 常编出 [6] 而只给了 5 条引用，
   prompt 里有 sanitize_citations 兜底，这里量出它到底触发多少次
3. 域外问题是否真的拒答（且不调模型、0 引用）

用法（仓库根目录，依赖 .venv）：
    python scripts/verify_generation.py --dataset eval/math_80.jsonl --limit 10
    python scripts/verify_generation.py --dataset eval/math_80.jsonl --limit 20 --only-ood
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
from app.db.session import SessionLocal
from app.rag.pipeline import RagPipeline

REPORT_DIR = ROOT / "eval" / "reports"

# 12 条域外问题：与考研数学无关，理应全部拒答。
# 与 calibrate_threshold.py 用的是同一批，便于交叉对照。
OOD_QUESTIONS = [
    "红烧肉怎么做好吃",
    "唐朝的开国皇帝是谁",
    "Python 的 GIL 是什么",
    "今天北京的天气怎么样",
    "推荐几部好看的科幻电影",
    "如何挑选一台笔记本电脑",
    "股票和债券有什么区别",
    "感冒了应该吃什么药",
    "世界杯是哪一年开始的",
    "怎么学好英语口语",
    "中国的首都是哪里",
    "怎样养一只猫",
]

_CITE_RE = re.compile(r"\[(\d{1,2})\]")


def _percentile(values: list[float], p: float) -> float:
    """与 calibrate_threshold.py 同口径：线性插值分位数。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo))


def _summarize(nums: list[float]) -> dict:
    if not nums:
        return {}
    return {
        "mean": round(sum(nums) / len(nums), 1),
        "p50": round(_percentile(nums, 0.50), 1),
        "p90": round(_percentile(nums, 0.90), 1),
        "max": round(max(nums), 1),
    }


async def _run_one(question: str, kb_ids: list[str], gold: set[str]) -> dict:
    """跑一道题，把 done 事件里的指标摊平。"""
    with SessionLocal() as db:
        events = [
            e
            async for e in RagPipeline(db).run(
                question=question,
                kb_ids=kb_ids,
                message_id="m_verify",
                conversation_id="c_verify",
            )
        ]

    done = next((e["data"] for e in events if e["event"] == "done"), None)
    errors = [e["data"] for e in events if e["event"] == "error"]
    if done is None:
        return {"question": question, "failed": True, "error": errors[0] if errors else "无 done 事件"}

    answer = done.get("answer") or ""
    citations = done.get("citations") or []
    n_cite = len(citations)

    # 引用合法性：答案里出现的 [n] 必须落在 1..len(citations)
    indices = [int(m.group(1)) for m in _CITE_RE.finditer(answer)]
    invalid = sorted({i for i in indices if i < 1 or i > n_cite})

    # 引用命中：任一引用 chunk 属于该题的 gold（有 gold 才算）
    hit = None
    if gold:
        hit = any(c.get("chunk_id") in gold for c in citations)

    return {
        "question": question,
        "failed": False,
        "refused": bool(done.get("refused")),
        "confidence": round(float(done.get("confidence") or 0), 4),
        "first_token_ms": int(done.get("first_token_ms") or 0),
        "latency_ms": int(done.get("latency_ms") or 0),
        "tokens_in": int(done.get("tokens_in") or 0),
        "tokens_out": int(done.get("tokens_out") or 0),
        "n_citations": n_cite,
        "n_cite_marks": len(indices),
        "invalid_citations": invalid,
        "citation_hit": hit,
        "answer_chars": len(answer),
        "answer": answer,
    }


def _load_cases(dataset: Path, limit: int) -> list[dict]:
    items = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items[:limit]


async def main_async(args: argparse.Namespace) -> dict:
    if settings.mock_llm or not settings.deepseek_api_key:
        print("拒绝执行：当前是 MOCK 模式或未配 DEEPSEEK_API_KEY，生成的延迟与质量都不代表真实情况。")
        print("请在 .env 配 DEEPSEEK_API_KEY 且 MOCK_LLM=false 后重跑。")
        sys.exit(2)

    report: dict = {
        "model": settings.deepseek_model,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "top_k": settings.retrieval_top_k,
            "rerank_top_n": settings.rerank_top_n,
            "threshold": settings.relevance_threshold,
            "max_tokens": settings.llm_max_tokens,
            "temperature": settings.llm_temperature,
            "embed_provider": settings.embed_provider,
        },
        "indomain": [],
        "ood": [],
    }

    if not args.only_ood:
        cases = _load_cases(Path(args.dataset), args.limit)

        # 预热：首题常因 TCP/TLS 建连 + 服务端冷启动出现 15s 级尾延迟，
        # 混进统计会把 p90 拉爆。单独跑一次并把耗时记进报告，不参与汇总。
        if not args.no_warmup:
            warm_at = datetime.now().isoformat(timespec="seconds")
            warm = await _run_one(cases[0]["question"], cases[0]["kb_ids"], set())
            report["warmup"] = {
                "at": warm_at,
                "first_token_ms": warm.get("first_token_ms"),
                "latency_ms": warm.get("latency_ms"),
                "tokens_out": warm.get("tokens_out"),
            }
            print(
                f"预热（不计入汇总）：首tok {warm.get('first_token_ms')}ms "
                f"总 {warm.get('latency_ms')}ms tokens {warm.get('tokens_out')}"
            )

        print(f"=== 域内 {len(cases)} 题（真实生成）===")
        for i, item in enumerate(cases, 1):
            row = await _run_one(item["question"], item["kb_ids"], set(item.get("gold_chunk_ids") or []))
            report["indomain"].append(row)
            if row["failed"]:
                print(f"  {i:2}. 失败 {row['error']}")
            else:
                flag = "拒答" if row["refused"] else "作答"
                bad = f" 越界{row['invalid_citations']}" if row["invalid_citations"] else ""
                print(
                    f"  {i:2}. {flag} 首tok {row['first_token_ms']:>5}ms 总 {row['latency_ms']:>6}ms "
                    f"tok {row['tokens_in']:>4}/{row['tokens_out']:<4} 引用{row['n_citations']}{bad}  {row['question'][:24]}"
                )

    if not args.skip_ood:
        ood = OOD_QUESTIONS[: args.ood_limit]
        print(f"\n=== 域外 {len(ood)} 题（应全部拒答）===")
        for i, q in enumerate(ood, 1):
            row = await _run_one(q, args.kb_ids, set())
            report["ood"].append(row)
            if row["failed"]:
                print(f"  {i:2}. 失败 {row['error']}")
            else:
                flag = "拒答✓" if row["refused"] else "硬答✗"
                print(
                    f"  {i:2}. {flag} conf {row['confidence']:.4f} 引用{row['n_citations']} "
                    f"tok {row['tokens_in']:>4}/{row['tokens_out']:<4}  {q}"
                )

    # ---------------- 汇总 ----------------
    ok = [r for r in report["indomain"] if not r["failed"]]
    answered = [r for r in ok if not r["refused"]]
    ood_ok = [r for r in report["ood"] if not r["failed"]]

    summary = {
        "indomain_n": len(ok),
        "indomain_refused": len(ok) - len(answered),
        "first_token_ms": _summarize([r["first_token_ms"] for r in answered]),
        "latency_ms": _summarize([r["latency_ms"] for r in answered]),
        "tokens_out": _summarize([r["tokens_out"] for r in answered]),
        "citation_marks": _summarize([r["n_cite_marks"] for r in answered]),
        "invalid_citation_rate": round(
            sum(1 for r in answered if r["invalid_citations"]) / len(answered), 4
        )
        if answered
        else None,
        "citation_hit_rate": round(
            sum(1 for r in answered if r["citation_hit"]) / len(answered), 4
        )
        if answered and any(r["citation_hit"] is not None for r in answered)
        else None,
        "ood_n": len(ood_ok),
        "ood_refused_rate": round(sum(1 for r in ood_ok if r["refused"]) / len(ood_ok), 4) if ood_ok else None,
        # 拒答路径在 stream_chat 之前就 return，first_token_ms 恒为 0；
        # tokens_out 是拒答话术的估算值，不能用它判断"是否调用模型"。
        "ood_llm_called": sum(1 for r in ood_ok if r["first_token_ms"] > 0),
        "ood_citations_nonzero": sum(1 for r in ood_ok if r["n_citations"] > 0),
    }
    report["summary"] = summary

    if answered:
        tokens = [r["tokens_out"] for r in answered if r["latency_ms"] > 0]
        secs = [r["latency_ms"] / 1000 for r in answered if r["latency_ms"] > 0]
        if tokens and secs:
            summary["tokens_per_s"] = round(sum(tokens) / sum(secs), 1)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_generation.json"
    # 报告里不留完整答案正文以外的敏感信息；答案保留便于人工抽检
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 汇总 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"报告 → {out}")
    if settings.embed_provider == "dev":
        print("提醒：EMBED_PROVIDER=dev 时检索是假的，本报告的引用命中率不可用。")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="真实模型生成验证（B1）")
    ap.add_argument("--dataset", default="eval/math_80.jsonl", help="评估集（含 gold_chunk_ids）")
    ap.add_argument("--kb", dest="kb_ids", default="kb_9191bbbe7c47", help="域外测试用的知识库 id")
    ap.add_argument("--limit", type=int, default=10, help="域内题数")
    ap.add_argument("--ood-limit", type=int, default=12, help="域外题数（最多 12）")
    ap.add_argument("--only-ood", action="store_true", help="只跑域外拒答")
    ap.add_argument("--skip-ood", action="store_true", help="只跑域内生成")
    ap.add_argument("--no-warmup", action="store_true", help="不预热（会让首题冷启动混进统计）")
    args = ap.parse_args()

    if isinstance(args.kb_ids, str):
        args.kb_ids = [args.kb_ids]
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
