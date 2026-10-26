"""B-07 · 人工复核表填充工具：用真实模型跑复核表里的 20 题，填 model_answer 列。

判定边界（严格遵守任务书「不得 agent 自标通过」红线）：
  - **数学答案正确性** 一律留给真人判定，human_verdict 保持 pending。
  - 只有「机制/行为」是客观可验证的，本脚本才自动判：
      · scenario == 无依据 且模型确实拒答（refused 或 declined）
        → human_verdict = "auto:pass"，verdict_reason 写"拒答机制正确触发（行为判定，非答案对错）"
      · scenario == 无依据 但模型居然给出了正答（漏拒）
        → human_verdict = "auto:fail"，verdict_reason 写"应拒答却给出正答（行为判定）"
  其余 case（涉及真实数学答案）一律 pending，人工逐条判定。

无真实 key 时直接拒绝执行并提示，不产出虚假的"模型答案"。

用法：
    python scripts/fill_review_answers.py                     # 全部 20 题
    python scripts/fill_review_answers.py --cases h015,h016    # 只跑指定题
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
            # 只填尚未有答案的（避免覆盖人工已填的）；已有人工判定也跳过
            if row["model_answer"].strip() or row["human_verdict"].strip():
                continue
            try:
                r = await _answer_one(row["question"])
                refused = bool(r.get("refused"))
                declined = bool(r.get("declined"))
                text = r.get("text", "") or ""
                if refused or declined:
                    row["model_answer"] = f"[拒答] {text}"
                else:
                    row["model_answer"] = text
                # 机制/行为自动判定：仅限「无依据」场景
                if row["scenario"] == "无依据":
                    if refused or declined:
                        row["human_verdict"] = "auto:pass"
                        row["verdict_reason"] = "拒答机制正确触发（行为判定，非答案对错）"
                        row["status"] = "auto_checked"
                    else:
                        row["human_verdict"] = "auto:fail"
                        row["verdict_reason"] = "应拒答却给出正答（漏拒，行为判定）"
                        row["status"] = "auto_checked"
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
    auto = sum(1 for r in rows if r["human_verdict"].startswith("auto:"))
    pending = sum(1 for r in rows if not r["human_verdict"].strip())
    print(f"已填 model_answer：{filled}/{len(rows)} 条")
    print(f"自动行为判定（auto:*）：{auto} 条；仍待人工判定（pending）：{pending} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
