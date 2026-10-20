"""A 工作完成度自检：一键验收。

用法：python scripts/verify_work.py
全部只读，不改任何数据。每项输出 ✅/❌ 与证据，最后给出总结论。
"""

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, evidence: str) -> None:
    RESULTS.append((name, ok, evidence))
    print(f"{'✅' if ok else '❌'} {name}：{evidence}")


def main() -> int:
    print("=" * 60)
    print("A 工作验收自检（只读，不改数据）")
    print("=" * 60)

    # 1. 代码健康：全部测试
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=300,
    )
    m = re.search(r"(\d+) passed", r.stdout)
    passed = int(m.group(1)) if m else 0
    failed = re.search(r"(\d+) failed", r.stdout)
    check("单元/集成测试", bool(m) and not failed, f"{passed} passed" + (f"，{failed.group(1)} failed！" if failed else ""))

    # 2. 数据完整性
    db_path = ROOT / "data/app.db"
    if db_path.exists():
        db = sqlite3.connect(db_path)
        docs_total, docs_ready = (
            db.execute("select count(*) from documents").fetchone()[0],
            db.execute("select count(*) from documents where status='ready'").fetchone()[0],
        )
        check("入库状态", docs_total > 0 and docs_ready == docs_total, f"{docs_ready}/{docs_total} 文档 ready")
        chunks = db.execute("select count(*) from chunks").fetchone()[0]
        kb = db.execute("select count(*) from knowledge_bases").fetchone()[0]
        check("chunk 规模", chunks >= 300, f"{chunks} chunk / {kb} 个知识库")
        covered = set()
        for pat, subject in [("张宇-概率论", "概率论"), ("1-1.", "高数"), ("2-1.", "线代")]:
            if db.execute("select count(*) from documents where filename like ?", (f"%{pat}%",)).fetchone()[0]:
                covered.add(subject)
        check("三科覆盖", covered == {"高数", "线代", "概率论"}, "含 " + "、".join(sorted(covered)))
        types = dict(db.execute("select content_type, count(*) from chunks group by 1").fetchall())
        check("结构化类型", types.get("example", 0) + types.get("exercise", 0) > 30,
              f"example={types.get('example',0)} exercise={types.get('exercise',0)}")
    else:
        check("入库状态", False, "data/app.db 不存在，语料未入库")

    # 3. 向量库对账
    r = subprocess.run([sys.executable, "scripts/check_consistency.py"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    ok = '"consistent": true' in r.stdout
    n = re.search(r'"db_chunks": (\d+),\s*"vector_chunks": (\d+)', r.stdout)
    ev = f"db={n.group(1)} vector={n.group(2)}" if n else r.stdout[:60]
    check("向量库对账", ok, ev)

    # 4. 检索冒烟：三个标准问题应命中对应科目
    try:
        code = (
            "import sys, sqlite3; sys.path.insert(0,'backend')\n"
            "sys.path.insert(0,'backend')\n"
            "from app.rag.embedder import embed_query\n"
            "from app.rag.vectorstore import get_store\n"
            "kb = sqlite3.connect('data/app.db').execute('select id from knowledge_bases limit 1').fetchone()[0]\n"
            "qs = {'全概率公式':'概率论', '不定积分的计算':'高数', '矩阵的秩':'线代'}\n"
            "bad = []\n"
            "for q, want in qs.items():\n"
            "    hits = get_store().query(embed_query(q), [kb], 3)\n"
            "    names = ' '.join(h.metadata.get('doc_name','') for h in hits)\n"
            "    tag = '概率论' if '概率论' in names else ('线代' if any(k in names for k in ('矩阵','行列式','向量组','方程组')) else ('高数' if any(k in names for k in ('积分','极限','微分','函数')) else '其他'))\n"
            "    if tag != want: bad.append(f'{q}->{tag}')\n"
            "print('OK' if not bad else 'MISS:' + ';'.join(bad))\n"
        )
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                           text=True, timeout=120)
        ok = "OK" in r.stdout
        check("检索冒烟（3 问命中科目）", ok, r.stdout.strip()[:80] or r.stderr[:80])
    except Exception as exc:
        check("检索冒烟", False, str(exc)[:80])

    # 5. 契约与文档
    for f, desc in [
        ("docs/A-接口与边界.md", "接口契约"),
        ("docs/需求说明书.md", "需求说明书"),
        ("docs/OCR小样报告.md", "OCR 报告"),
        ("backend/app/api/doc.py", "6 接口实现"),
    ]:
        check(f"交付物：{desc}", (ROOT / f).exists(), f)

    # 6. Git 状态：已提交、已推送
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    dirty = bool(r.stdout.strip())
    check("工作区干净（无未提交变更）", not dirty, "有未提交文件" if dirty else "clean")
    r = subprocess.run(["git", "log", "--oneline", "-1", "origin/main"], cwd=ROOT,
                       capture_output=True, text=True)
    r2 = subprocess.run(["git", "log", "--oneline", "-1", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True)
    synced = r.stdout.split()[0] == r2.stdout.split()[0] if r.stdout and r2.stdout else False
    check("已同步到 GitHub", synced, f"HEAD={r2.stdout.strip()[:30]}")

    # 总结
    bad = [name for name, ok, _ in RESULTS if not ok]
    print("=" * 60)
    if not bad:
        print(f"结论：✅ 全部 {len(RESULTS)} 项通过——A 的交付完整可用。")
    else:
        print(f"结论：❌ {len(bad)} 项未过：{'、'.join(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
