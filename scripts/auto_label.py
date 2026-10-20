"""标签自动生成：用大模型对每个文档打标（知识点 / 题型 / 难度）。

对应分工表 A 职责⑤："利用大模型对文档自动打标（知识点、题型、难度），
供 B 检索路由使用、C 前端展示分类筛选。"

用法：python scripts/auto_label.py            # 全部未打标文档
      python scripts/auto_label.py --force    # 覆盖重打

实现：文档标题 + 正文前 1200 字 → 智谱 glm-4-flash（免费档）→ JSON 标签。
标签写 documents.tags_json；--migrate 自动加列。
"""

import json
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402

PROMPT = """你是数学教材标注员。根据下面的文档标题和正文开头，输出 JSON（不要解释）：
{{"knowledge_points": ["知识点1", "知识点2"], "question_types": ["题型"],
"difficulty": "基础|进阶|困难 之一"}}

要求：
- knowledge_points：2-5 个标准数学术语（如"泰勒公式""伴随矩阵"）；
- question_types：该文档涉及的题型（如"证明题""计算题""概念辨析"），无则空数组；
- difficulty：按考研数学标准给出。

标题：{title}
正文：
{body}"""


def ensure_columns(db: sqlite3.Connection) -> None:
    cols = {r[1] for r in db.execute("pragma table_info(documents)")}
    if "tags_json" not in cols:
        db.execute("alter table documents add column tags_json text")
    if "difficulty" not in cols:
        db.execute("alter table documents add column difficulty text")


def call_llm(title: str, body: str) -> dict | None:
    import httpx

    payload = {
        "model": "glm-4-flash",
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": PROMPT.format(title=title, body=body[:1200]),
        }],
    }
    for _ in range(3):
        try:
            resp = httpx.post(
                f"{settings.vlm_api_base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.vlm_api_key}"},
                json=payload, timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(3)
                continue
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\{.*\}", text, flags=re.S)
            if not m:
                return None
            data = json.loads(m.group(0))
            return {
                "knowledge_points": [str(x)[:40] for x in data.get("knowledge_points", [])][:6],
                "question_types": [str(x)[:24] for x in data.get("question_types", [])][:5],
                "difficulty": str(data.get("difficulty", ""))[:8],
            }
        except Exception:
            time.sleep(2)
    return None


def main() -> int:
    force = "--force" in sys.argv
    db_path = ROOT / "data/app.db"
    db = sqlite3.connect(db_path)
    ensure_columns(db)
    db.commit()

    rows = db.execute("select id, filename, stored_path from documents").fetchall()
    todo = []
    for doc_id, filename, stored in rows:
        cur = db.execute("select tags_json from documents where id=?", (doc_id,)).fetchone()[0]
        if cur and not force:
            continue
        path = ROOT / "data" / stored if stored and not Path(stored).is_absolute() else Path(stored or "")
        if not path.exists():
            path = ROOT / "data/uploads" / f"{doc_id}.md"
        body = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        todo.append((doc_id, filename, body))

    print(f"待打标 {len(todo)} / {len(rows)} 个文档")
    ok = fail = 0

    def work(item):
        doc_id, filename, body = item
        return doc_id, filename, call_llm(filename, body)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(work, it) for it in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            doc_id, filename, tags = fut.result()
            if tags:
                db.execute(
                    "update documents set tags_json=?, difficulty=? where id=?",
                    (json.dumps(tags, ensure_ascii=False), tags["difficulty"], doc_id),
                )
                ok += 1
            else:
                fail += 1
            if i % 20 == 0 or i == len(todo):
                db.commit()
                print(f"  进度 {i}/{len(todo)}（成功 {ok} 失败 {fail}）")

    db.commit()
    n = db.execute("select count(*) from documents where tags_json is not null").fetchone()[0]
    print(f"完成：已打标 {n}/{len(rows)}，失败 {fail}")
    db.close()
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
