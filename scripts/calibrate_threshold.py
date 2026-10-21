"""标定 `RELEVANCE_THRESHOLD`（B8）：用正/负样本的相关度分布定阈值。

问题：0.35 这个默认值没有依据。dev 哈希向量和 bge-m3 的分数分布完全不同，
直接沿用会"该拒的不拒、该答的不答"。

做法：
- 正样本（该答）：从 kb 的 chunk 反推出题，取检索结果的 top_score；
- 负样本（该拒）：域外问题（数学库里问做饭/历史/编程），同样取 top_score；
- 看两类分布能否分开，给出建议阈值。

两类分不开时**明确报"不可分"**并给出重叠区间，不硬编一个数字——
硬给只会把问题藏到线上。

用法：
    python scripts/calibrate_threshold.py --kb kb_xxx --limit 40
    python scripts/calibrate_threshold.py --kb kb_xxx --review   # 只打印逐题分数
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval import _make_question  # noqa: E402  复用同一套造题逻辑，保证与评估集同分布

from app.core.config import settings  # noqa: E402
from app.db.models import Chunk  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402

# 域外问题：数学知识库答不了，理应被拒。刻意覆盖不同"误导方向"，
# 避免只测"完全不相关"这种容易分的情况。
OFF_DOMAIN = [
    "红烧肉怎么做好吃",
    "唐朝的开国皇帝是谁",
    "Python 的 GIL 是什么",
    "如何申请护照",
    "股票市盈率怎么算",
    "感冒了应该吃什么药",
    "怎么用 Excel 做数据透视表",
    "明天北京天气如何",
    "什么是量子纠缠",
    "怎样提高英语听力",
    "合同法里违约金上限是多少",
    "手机屏幕碎了怎么修",
]


def percentile(values: list[float], q: float) -> float:
    """线性插值分位数（避免引 numpy）。"""
    if not values:
        return 0.0
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def _stats(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "p10": round(percentile(values, 0.10), 4),
        "median": round(percentile(values, 0.50), 4),
        "p90": round(percentile(values, 0.90), 4),
        "max": round(max(values), 4),
    }


def build_positive_queries(kb_id: str, limit: int) -> list[str]:
    with SessionLocal() as db:
        rows = (
            db.query(Chunk)
            .filter(Chunk.kb_id == kb_id)
            .order_by(Chunk.doc_id, Chunk.seq)
            .limit(limit * 3)  # 有些 chunk 出不了题，多取一些
            .all()
        )
    queries = []
    for chunk in rows:
        q = _make_question(chunk.content, chunk.content_type)
        if q:
            queries.append(q)
        if len(queries) >= limit:
            break
    return queries


def _error_rates(pos: list[float], neg: list[float], thr: float | None) -> dict | None:
    """在给定阈值下，正样本被误拒的比例、负样本被误放行的比例。"""
    if thr is None or not pos or not neg:
        return None
    false_refusal = sum(1 for s in pos if s < thr) / len(pos)
    false_accept = sum(1 for s in neg if s >= thr) / len(neg)
    return {
        "threshold": round(thr, 4),
        "false_refusal_rate": round(false_refusal, 4),  # 该答却拒
        "false_accept_rate": round(false_accept, 4),  # 该拒却答
    }


def calibrate(kb_id: str, limit: int, review: bool) -> dict:
    pos_queries = build_positive_queries(kb_id, limit)
    if not pos_queries:
        raise SystemExit("kb 里没有可造题的 chunk，先入库语料")

    pos_scores: list[float] = []
    neg_scores: list[float] = []
    detail: list[dict] = []

    with SessionLocal() as db:
        for q in pos_queries:
            score = retrieve(db, q, [kb_id]).top_score
            pos_scores.append(score)
            if review:
                detail.append({"kind": "positive", "query": q, "score": round(score, 4)})

        for q in OFF_DOMAIN:
            score = retrieve(db, q, [kb_id]).top_score
            neg_scores.append(score)
            if review:
                detail.append({"kind": "negative", "query": q, "score": round(score, 4)})

    pos, neg = _stats(pos_scores), _stats(neg_scores)
    verdict: str
    suggested: float | None = None

    if pos and neg:
        if neg["max"] < pos["min"]:
            verdict = "完全可分：负样本最高分低于正样本最低分"
            suggested = round((neg["max"] + pos["min"]) / 2, 3)
        elif neg["p90"] < pos["p10"]:
            verdict = "基本可分：有少量重叠，取 p10/p90 中点"
            suggested = round((neg["p90"] + pos["p10"]) / 2, 3)
        else:
            verdict = (
                "不可分：正负样本分数区间大幅重叠，"
                "任何单一阈值都会有误拒或误答。需先换真实 embedding 再标定"
            )
    else:
        verdict = "样本不足"

    # 只有两类真的交叠时才有"重叠区间"，否则给 None（避免输出反序的无意义区间）
    overlap: list[float] | None = None
    if pos and neg:
        lo, hi = max(neg["min"], pos["min"]), min(neg["max"], pos["max"])
        overlap = [round(lo, 4), round(hi, 4)] if lo <= hi else None

    report = {
        "kb_id": kb_id,
        "embed_provider": settings.embed_provider,
        "vector_backend": settings.vector_backend,
        "current_threshold": settings.relevance_threshold,
        "positive": pos,
        "negative": neg,
        "verdict": verdict,
        "suggested_threshold": suggested,
        "overlap_range": overlap,
        # 两个阈值都在同一批样本上回测，好判断"换不换"值不值
        "at_current_threshold": _error_rates(pos_scores, neg_scores, settings.relevance_threshold),
        "at_suggested_threshold": _error_rates(pos_scores, neg_scores, suggested),
        "note": (
            "正样本由 chunk 反推，措辞与原文重合，分数偏高的可能性存在；"
            "负样本是域外问题。若两者不可分，说明当前 embedding 没有区分力"
            "（多为 EMBED_PROVIDER=dev 的哈希向量），不是阈值能解决的问题。"
        ),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if review:
        report["detail"] = detail
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="标定拒答阈值 RELEVANCE_THRESHOLD")
    parser.add_argument("--kb", required=True, help="知识库 id")
    parser.add_argument("--limit", type=int, default=40, help="正样本题数上限")
    parser.add_argument("--review", action="store_true", help="输出逐题分数")
    parser.add_argument("--out", default="", help="报告路径（默认 eval/reports/）")
    args = parser.parse_args()

    report = calibrate(args.kb, args.limit, args.review)

    if args.out:
        out = ROOT / args.out
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = ROOT / "eval" / "reports" / f"{stamp}_threshold.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in report.items() if k != "detail"}, ensure_ascii=False, indent=2))
    print(f"报告 → {out}")
    if report["embed_provider"] == "dev":
        print("提醒：dev 哈希向量下该结论只证明脚本可用，阈值需在真实 embedding 上重标。")


if __name__ == "__main__":
    main()
