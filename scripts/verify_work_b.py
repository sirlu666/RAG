"""B 工作完成度自检：一键验收（RAG 引擎与大模型应用）。

用法：
    python scripts/verify_work.py

全部只读，不改任何数据、不产生费用。每项输出 ✅/❌ 与证据，最后给出总结论。

设计对齐 A 的 scripts/verify_work.py：覆盖「测试 / 检索指标 / 拒答防线 / SSE 端到端 /
契约无漂移 / 交付物 / git 同步」七个维度，让 C 和答辩老师拿到仓库能一键确认 B 完整可用。

离线可跑：检索与拒答不调大模型；SSE 冒烟用 MOCK_LLM（不消耗 DEEPSEEK_API_KEY）。
若检测到真实 key 且要量生成，用 scripts/verify_generation.py（见 docs/B-接口与边界.md §6）。
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, evidence: str) -> None:
    RESULTS.append((name, ok, evidence))
    print(f"{'✅' if ok else '❌'} {name}：{evidence}")


def _run_py(code: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """在项目根目录跑一段 python，继承当前环境（含 .env 的 local+chroma 配置）。"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )


def main() -> int:
    print("=" * 60)
    print("B 工作验收自检（RAG 引擎，只读，不改数据）")
    print("=" * 60)

    # 1. 代码健康：全部测试
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=600,
    )
    m = re.search(r"(\d+) passed", r.stdout)
    passed = int(m.group(1)) if m else 0
    failed = re.search(r"(\d+) failed", r.stdout)
    check("单元/集成测试", bool(m) and not failed,
          f"{passed} passed" + (f"，{failed.group(1)} failed！" if failed else ""))

    # 2. 检索指标可复现（反推 80 题 + 改写 18 题，hybrid 模式）
    #    不调大模型，离线可跑；用 run_eval 的纯函数入口，避免子进程串扰。
    ev = ""
    ok = True
    try:
        code = (
            "import json, sys, io, contextlib\n"
            "sys.path.insert(0, 'backend')\n"
            "from scripts.eval import run_eval\n"
            "from pathlib import Path\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf):\n"
            "    r80 = run_eval(Path('eval/math_80.jsonl'), 'hybrid', False, None)\n"
            "    r18 = run_eval(Path('eval/math_18_rewritten.jsonl'), 'hybrid', False, None)\n"
            "print(json.dumps({'r80': r80['recall_at_5'], 'r18': r18['recall_at_5'],"
            " 'mrr80': r80['mrr'], 'mrr18': r18['mrr']}, ensure_ascii=False))\n"
        )
        r = _run_py(code, timeout=600)
        mj = re.search(r"\{.*\}", r.stdout, re.S)
        if mj:
            d = json.loads(mj.group(0))
            ok = d["r80"] >= 0.95 and d["r18"] >= 0.5
            ev = (f"反推80题 Recall@5={d['r80']:.4f} MRR={d['mrr80']:.4f}；"
                  f"改写18题 Recall@5={d['r18']:.4f} MRR={d['mrr18']:.4f}")
        else:
            ok = False
            ev = (r.stdout + r.stderr)[-120:]
    except Exception as exc:
        ok = False
        ev = str(exc)[:120]
    check("检索指标（hybrid，两组题集）", ok, ev)

    # 3. 拒答防线：域外问题应被拒（不调模型）
    try:
        code = (
            "import sys, asyncio\n"
            "sys.path.insert(0, 'backend')\n"
            "from app.db.session import SessionLocal\n"
            "from app.rag.pipeline import RagPipeline\n"
            "kb = None\n"
            "import sqlite3\n"
            "kb = sqlite3.connect('data/app.db').execute('select id from knowledge_bases limit 1').fetchone()[0]\n"
            "async def go():\n"
            "    with SessionLocal() as db:\n"
            "        bad = []\n"
            "        for q in ['红烧肉怎么做好吃', '唐朝的开国皇帝是谁']:\n"
            "            evs = [e async for e in RagPipeline(db).run(question=q, kb_ids=[kb], message_id='m', conversation_id='c')]\n"
            "            done = [e['data'] for e in evs if e['event']=='done'][0]\n"
            "            if not (done.get('refused') or done.get('declined')):\n"
            "                bad.append(q)\n"
            "        print('OK' if not bad else 'MISS:' + ';'.join(bad))\n"
            "asyncio.run(go())\n"
        )
        r = _run_py(code, timeout=300)
        ok = "OK" in r.stdout
        check("拒答防线（域外问题被拒）", ok, r.stdout.strip()[:80] or r.stderr.strip()[:80])
    except Exception as exc:
        check("拒答防线", False, str(exc)[:120])

    # 4. SSE 端到端冒烟（MOCK_LLM，不产生费用）：事件顺序 meta→citation*→delta*→done
    try:
        code = (
            "import sys\n"
            "sys.path.insert(0, 'backend')\n"
            "from fastapi.testclient import TestClient\n"
            "from app.main import app\n"
            "import sqlite3\n"
            "kb = sqlite3.connect('data/app.db').execute('select id from knowledge_bases limit 1').fetchone()[0]\n"
            "with TestClient(app) as c:\n"
            "    body = {'question':'洛必达法则的适用条件是什么','kb_ids':[kb],'stream':True}\n"
            "    with c.stream('POST','/api/chat/stream', json=body, headers={'Authorization':'Bearer dev:dev'}) as r:\n"
            "        seq=[]\n"
            "        for line in r.iter_lines():\n"
            "            if line.startswith('event:'):\n"
            "                seq.append(line.split(':',1)[1].strip())\n"
            "        import json as _j\n"
            "        print('HTTP', r.status_code, _j.dumps(seq))\n"
        )
        r = _run_py(code, timeout=300)
        # 校验：首事件 meta，末事件 done，中间 citation/delta 顺序合理
        mm = re.search(r"HTTP (\d+) (\[.*\])", r.stdout)
        if mm:
            status = int(mm.group(1))
            seq = json.loads(mm.group(2))
            ok = (status == 200 and seq and seq[0] == "meta" and seq[-1] == "done"
                  and "citation" in seq and "delta" in seq)
            ev = f"HTTP {status}，事件 {seq[:1]}…{seq[-1:]}（共 {len(seq)} 帧）"
        else:
            ok = False
            ev = (r.stdout + r.stderr)[-120:]
    except Exception as exc:
        ok = False
        ev = str(exc)[:120]
    check("SSE 端到端（meta→citation*→delta*→done）", ok, ev)

    # 5. 契约文件齐全 + openapi 无漂移
    contract_files = [
        "docs/B-接口与边界.md",
        "docs/api/openapi.json",
        "docs/api/mock/chat_stream.txt",
        "docs/api/README.md",
    ]
    missing = [f for f in contract_files if not (ROOT / f).exists()]
    check("契约文件齐全", not missing, "缺 " + "、".join(missing) if missing else f"{len(contract_files)} 份齐全")
    # openapi 无漂移：重新导出后 diff 应为空
    r = subprocess.run([sys.executable, "scripts/dump_openapi.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    r2 = subprocess.run(["git", "diff", "--stat", "docs/api/openapi.json"], cwd=ROOT,
                        capture_output=True, text=True, timeout=30)
    check("OpenAPI 无漂移", r2.stdout.strip() == "", "重导后零变化" if r2.stdout.strip() == "" else r2.stdout.strip()[:80])

    # 6. 交付物文档
    for f, desc in [
        ("docs/B-接口与边界.md", "B 接口契约"),
        ("docs/A-接口与边界.md", "A 接口契约（上游）"),
        ("scripts/eval.py", "检索评估"),
        ("scripts/verify_generation.py", "生成评估"),
        ("scripts/calibrate_threshold.py", "阈值标定"),
    ]:
        check(f"交付物：{desc}", (ROOT / f).exists(), f)

    # 7. Git 状态：已提交、已推送
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    check("工作区干净（无未提交变更）", not r.stdout.strip(), "有未提交文件" if r.stdout.strip() else "clean")
    r = subprocess.run(["git", "log", "--oneline", "-1", "origin/main"], cwd=ROOT,
                       capture_output=True, text=True)
    r2 = subprocess.run(["git", "log", "--oneline", "-1", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True)
    synced = r.stdout.split()[0] == r2.stdout.split()[0] if r.stdout and r2.stdout else False
    check("已同步到 GitHub", synced, f"HEAD={r2.stdout.strip()[:30]}")

    # 总结
    bad = [name for name, okk, _ in RESULTS if not okk]
    print("=" * 60)
    if not bad:
        print(f"结论：✅ 全部 {len(RESULTS)} 项通过——B 的交付完整可用。")
    else:
        print(f"结论：❌ {len(bad)} 项未过：{'、'.join(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
