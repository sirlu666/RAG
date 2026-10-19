# scripts · 离线脚本

> 这些脚本必须能独立于 Web 服务运行（不 import FastAPI），方便复现与答辩演示。

| 脚本 | 用途 | Owner | CLI |
|---|---|---|---|
| `ingest.py` | 批量把 `knowledge/raw/` 入库（可指定 kb_id / 学科） | A | `python scripts/ingest.py --dir knowledge/raw --kb public --subject highschool_math` |
| `rebuild_index.py` | 从 `chunks` 表重建 Chroma（向量库损坏时救命） | A | `python scripts/rebuild_index.py --collection math_chunks` |
| `check_consistency.py` | 对比关系库与向量库数量/ID 差异 | A | `python scripts/check_consistency.py` |
| `eval.py` | 跑测试集，输出 Recall@5 / MRR / 正确率 / P95 延迟 | B | `python scripts/eval.py --dataset eval/math_80.jsonl --tag hybrid+rerank` |
| `smoke.py` | 端到端冒烟：上传→等 ready→提问→断言有 citations | C | `python scripts/smoke.py --base http://127.0.0.1:8000` |
| `make_eval_set.py` | 从已入库 chunk 反推出题（问题+标准答案+gold chunk_id） | B | `python scripts/make_eval_set.py --n 80 --out eval/math_80.jsonl` |

> 已按 `06-范围基线.md` 删除 `tag.py`（自动打标签不在范围内）。

## 约定

- 所有脚本支持 `--dry-run`，先打印将要做什么，避免误删数据。
- 输出统一 JSON 到 stdout（便于 CI 解析），日志走 stderr。
- 每个脚本顶部 docstring 写：用途 / 前置条件 / 示例 / 风险。
