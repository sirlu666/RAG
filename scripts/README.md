# scripts · A 的离线脚本

| 脚本 | 用途 | 常用命令 |
|---|---|---|
| `fetch_wikibooks.py` | 从中文维基教科书抓数学语料（CC BY-SA），转 markdown 并记 manifest | `python scripts/fetch_wikibooks.py --prefix 高中数学/ --limit 60` |
| `ingest.py` | `--dry-run` 语料体检（Gate 0 用）；不带该参数则批量入库 | `python scripts/ingest.py --dir knowledge/raw --dry-run` |
| `rebuild_index.py` | 从 chunks 表重建向量（向量库损坏时救命） | `python scripts/rebuild_index.py [--doc doc_xxx]` |
| `check_consistency.py` | 对比关系库与向量库 id，发现孤儿/缺失 | `python scripts/check_consistency.py` |

```bash
# 1) 体检：字符数 / 页数 / "例 N" 数 / chunk 数 / 公式占比（不写库）
python scripts/ingest.py --dir knowledge/raw --dry-run

# 2) 入库：写 data/app.db + data/chroma + data/uploads
python scripts/ingest.py --dir knowledge/raw --kb 公共教材

# 3) 运维
python scripts/check_consistency.py
python scripts/rebuild_index.py
```

退出码约定：体检未达 Gate 0 返回 2；一致性有差异返回 1；其余成功返回 0。

## 约定

- 脚本必须能独立于 Web 服务运行，不 import FastAPI。
- 支持 `--dry-run`，先打印将要做什么，避免误删数据。
- 输出 JSON 到 stdout（便于 CI 解析），日志走 stderr。
- 顶部 docstring 写：用途 / 前置条件 / 示例 / 风险。
