"""标签自动生成：用大模型对文档打标（知识点 / 题型 / 难度）。

对应分工表 A 职责⑤ + 任务书 A-02。标签被 B 检索路由、C 展示筛选消费。

用法：
    python scripts/auto_label.py                          # 全部未打标文档（读默认 data/app.db）
    python scripts/auto_label.py --db .tmp/c-integration/app.db --dir knowledge/raw --user alice
    python scripts/auto_label.py --scope doc_xxx           # 只打某个文档
    python scripts/auto_label.py --force                   # 覆盖重打

关键约定：
- 正文从「解析后内容」读取：复用 loader.load_pages 解析 MD/PDF/DOCX/图片，绝不对二进制直接 read_text；
- 凭据独立（LABEL_API_*，留空回退 VLM_*）；无凭据时明确报「待真实调用」，不伪造标签；
- 输出经校验：去空、去重、限制长度与难度枚举；坏 JSON/异常输出不落库；
- 失败不覆盖已有效的同版本标签；标签绑定 content_hash，版本变更后旧标签失效；
- 可显式触发、可重试、可指定范围。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_parser = argparse.ArgumentParser(description="文档自动打标（知识点/题型/难度）")
_parser.add_argument("--db", default=None, help="目标数据库（默认 data/app.db）")
_parser.add_argument("--dir", default=None, help="语料目录（只打标该目录下的文档）")
_parser.add_argument("--scope", default=None, help="只打指定 doc_id（逗号分隔可多个）")
_parser.add_argument("--user", default=None, help="只打某用户名下的文档")
_parser.add_argument("--force", action="store_true", help="覆盖已有标签重打")
_parser.add_argument("--max", type=int, default=0, help="最多打标 N 个（0=不限，用于小样）")
_args, _unknown = _parser.parse_known_args()

_ROOT = Path(__file__).resolve().parents[1]
if _args.db:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(_args.db).as_posix()}"

sys.path.insert(0, str(_ROOT / "backend"))

from app.core.config import settings  # noqa: E402

DIFFICULTIES = {"基础", "进阶", "困难"}
MAX_POINTS = 6
MAX_TYPES = 5
MAX_POINT_LEN = 40
MAX_TYPE_LEN = 24

PROMPT = """你是数学教材标注员。根据文档标题和正文开头，输出一个 JSON 对象（不要任何解释、不要代码围栏）：
{{"knowledge_points": ["知识点1", "知识点2"], "question_types": ["题型"], "difficulty": "基础"}}

要求：
- knowledge_points：2-5 个标准数学术语（如"泰勒公式""伴随矩阵""行列式"）；
- question_types：涉及的题型（如"证明题""计算题""概念辨析"），无则空数组；
- difficulty：只能是"基础"、"进阶"、"困难"三者之一。

标题：{title}
正文：
{body}"""


def _label_credentials() -> tuple[str, str, str]:
    base = settings.label_api_base or settings.vlm_api_base
    key = settings.label_api_key or settings.vlm_api_key
    model = settings.label_model
    return base, key, model


def call_llm(title: str, body: str) -> dict | None:
    """调用标签模型，返回已校验的标签 dict，失败返回 None。"""
    import httpx

    base, key, model = _label_credentials()
    if not base or not key:
        return None

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT.format(title=title, body=body[:1200])}],
    }
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload, timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(3)
                continue
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            return validate(json.loads(_extract_json(text)))
        except Exception:
            time.sleep(2)
    return None


def _extract_json(text: str) -> str:
    """容忍模型在 JSON 前后夹带文字/围栏。"""
    m = re.search(r"\{.*\}", text, flags=re.S)
    return m.group(0) if m else "{}"


def validate(data: dict) -> dict | None:
    """校验模型输出：去空、去重、限长、枚举难度。不合法返回 None。"""
    if not isinstance(data, dict):
        return None
    points = _dedup_truncate(data.get("knowledge_points"), MAX_POINT_LEN, MAX_POINTS)
    types = _dedup_truncate(data.get("question_types"), MAX_TYPE_LEN, MAX_TYPES)
    difficulty = str(data.get("difficulty", "")).strip()
    if difficulty not in DIFFICULTIES:
        return None
    # 至少要有知识点或题型，否则是无效标签
    if not points and not types:
        return None
    return {
        "knowledge_points": points,
        "question_types": types,
        "difficulty": difficulty,
    }


def _dedup_truncate(items, max_len: int, max_n: int) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for x in items:
        s = str(x).strip()
        if not s or s in out:
            continue
        out.append(s[:max_len])
        if len(out) >= max_n:
            break
    return out


def _resolved_text(doc_id: str, filename: str, stored_path: str) -> tuple[str, str]:
    """从解析后正文读取文档内容（MD/PDF/DOCX/图片统一走 loader）。

    返回 (title, body)。title 用文件名，body 用解析后正文。
    """
    from app.services.parsing.loader import load_pages
    from app.db.models import Chunk
    from app.db.session import session_scope

    # Prefer indexed/corrected text, including already parsed images.
    with session_scope() as db:
        chunks = db.query(Chunk).filter(Chunk.doc_id == doc_id).order_by(Chunk.seq).all()
        if chunks:
            return filename, '\n'.join(chunk.content for chunk in chunks)

    path = Path(stored_path) if stored_path and Path(stored_path).is_absolute() else (_ROOT / "data" / stored_path)
    if not path.exists():
        # 兜底：uploads 下按 doc_id 找（历史入库文件改名为 doc_xxx.<ext>）
        cands = list((_ROOT / "data/uploads").glob(f"{doc_id}.*"))
        path = cands[0] if cands else path

    body = ""
    if path.exists():
        suffix = path.suffix.lstrip(".").lower()
        try:
            pages = load_pages(path, suffix if suffix in ("pdf", "docx", "md", "txt") else "txt")
            body = "\n".join(text for _, text in pages)
        except Exception:
            body = ""
    return filename, body


def main() -> int:
    from app.db.models import Document, User
    from app.db.session import ensure_dirs, init_db, session_scope

    ensure_dirs()
    init_db()

    base, key, _ = _label_credentials()
    if not base or not key:
        print(json.dumps({
            "status": "待真实调用",
            "reason": "未配置标签模型凭据（LABEL_API_BASE/LABEL_API_KEY，或 VLM_API_*）",
            "hint": "复制 .env.example 中的 LABEL_API_* 配置后重跑",
        }, ensure_ascii=False, indent=2))
        return 2

    with session_scope() as db:
        query = db.query(Document)
        if _args.user:
            u = db.query(User).filter(User.username == _args.user).first()
            if u is None:
                print(json.dumps({"error": f"用户不存在：{_args.user}"}, ensure_ascii=False))
                return 1
            query = query.filter(Document.user_id == u.id)
        if _args.scope:
            ids = [x.strip() for x in _args.scope.split(",") if x.strip()]
            query = query.filter(Document.id.in_(ids))
        docs = query.order_by(Document.created_at.desc()).all()

    todo = []
    for d in docs:
        if d.tags_json and not _args.force:
            continue
        todo.append(d)

    if _args.max:
        todo = todo[: _args.max]

    print(f"待打标 {len(todo)} / {len(docs)} 个文档（凭据={_label_credentials()[2]}）")

    ok = fail = stale = 0
    with session_scope() as db:
        def work(doc):
            title, body = _resolved_text(doc.id, doc.filename, doc.stored_path)
            tags = call_llm(title, body) if body.strip() else None
            return doc.id, doc.content_hash, doc.updated_at, doc.tags_json, tags

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(work, d) for d in todo]
            for i, fut in enumerate(as_completed(futures), 1):
                doc_id, source_hash, source_updated_at, source_tags, tags = fut.result()
                if tags:
                    # Compare-and-set protects both source version and concurrent label jobs.
                    changed = db.query(Document).filter(
                        Document.id == doc_id,
                        Document.content_hash == source_hash,
                        Document.updated_at == source_updated_at,
                        Document.tags_json == source_tags,
                    ).update(
                        {"tags_json": json.dumps(tags, ensure_ascii=False),
                         "difficulty": tags["difficulty"]},
                        synchronize_session=False,
                    )
                    db.commit()  # Do not hold a write lock while other model calls are running.
                    if changed:
                        ok += 1
                    else:
                        stale += 1
                else:
                    fail += 1
                if i % 10 == 0 or i == len(todo):
                    db.commit()
                    print(f"  进度 {i}/{len(todo)}（成功 {ok} 失败 {fail} 过期/已处理 {stale}）")

    labeled = 0
    with session_scope() as db:
        labeled = db.query(Document).filter(Document.tags_json.isnot(None)).count()

    print(json.dumps({"done": ok, "failed": fail, "stale": stale, "labeled_total": labeled}, ensure_ascii=False))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
