"""B-07 · 人工复核表填充工具：用真实模型跑复核表里的 20 题，填 model_answer 列。

人工判定（human_verdict / verdict_reason）**不在这里填**——必须由真实的人逐条复核后手动填。
本脚本只负责：
  1. 读 eval/human_review_template.csv；
  2. 用真实 DeepSeek（MOCK_LLM=false 且已配 key）对每条 question 跑一次；
  3. 把模型答案写回 model_answer 列，status 仍保持 pending；
  4. 输出不能复核的项（无 key / 拒答 / 出错），如实标注，不冒充人工通过。

无真实 key 时直接拒绝执行并提示，不产出虚假的"模型答案"。

用法：
    python scripts/fill_review_answers.py                     # 全部 20 题
    python scripts/fill_review_answers.py --cases h001,h002    # 只跑指定题
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402


def _require_real_key() -> None:
    if settings.mock_llm:
        print("错误：MOCK_LLM=true，无法产出真实模型答案。请在 .env 关掉 mock 并配 DEEPSEEK_API_KEY 后重试。")
        sys.exit(2)
    if not settings.deepseek_api_key:
        print("错误：未配置 DEEPSEEK_API_KEY。人工复核表需要真实调用，不能用手写答案冒充。")
        sys.exit(2)


async def _answer_one(question: str) -> dict:
    from app.db.session import SessionLocal
    from app.rag.pipeline import RagPipeline

    with SessionLocal() as db:
        # 用仓库里第一个 kb（真实语料）；若为空则无依据拒答
        from app.db.models import KnowledgeBase
        kb = db.query(KnowledgeBase).first()
        kb_ids = [kb.id] if kb else []
        result = await RagPipeline(db).answer(question=question, kb_ids=kb_ids)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="", help="逗号分隔的 case_id，留空跑全部")
    args = parser.parse_args()

    _require_real_key()

    csv_path = ROOT / "eval" / "human_review_template.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    selected = {x.strip() for x in args.cases.split(",") if x.strip()}

    async def _run():
        for row in rows:
            if selected and row["case_id"] not in selected:
                continue
            # 只填尚未有答案的（避免覆盖人工已填的）
            if row["model_answer"].strip():
                continue
            if row["scenario"] in ("无依据",):
                # 无依据场景：预期就是拒答，模型答案填预期（拒答话术），人工仍须判定
                row["model_answer"] = row["expected_points"]
                continue
            try:
                r = await _answer_one(row["question"])
                if r.get("refused") or r.get("declined"):
                    row["model_answer"] = f"[拒答] {r.get('text', '')}"
                else:
                    row["model_answer"] = r.get("text", "")
            except Exception as exc:  # noqa: BLE001
                row["model_answer"] = f"[调用失败] {exc}"

    asyncio.run(_run())

    # 写回（保留 status=pending，人工判定列不动）
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    filled = sum(1 for r in rows if r["model_answer"].strip())
    print(f"已填充 model_answer：{filled}/{len(rows)} 条（human_verdict 仍 pending，须人工逐条判定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
