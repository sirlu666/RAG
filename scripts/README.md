# scripts · A 的离线脚本

| 脚本 | 状态 | 用途 |
|---|---|---|
| `ingest.py` | ✅ 已实现 | `--dry-run` 语料体检（Gate 0）；不带 `--dry-run` 时批量入库 |
| `rebuild_index.py` | ⏳ 待建（A 的后续工作） | 从 chunks 表重建向量，向量库损坏时救命 |
| `check_consistency.py` | ⏳ 待建 | 对比关系库与向量库 id，发现孤儿/缺失 |

```bash
# 体检：字符数、页数、"例 N" 数、chunk 数、公式占比（不写库）
python scripts/ingest.py --dir knowledge/raw --dry-run

# 入库：写 data/app.db + data/chroma + data/uploads
python scripts/ingest.py --dir knowledge/raw --kb 公共教材
```

## 约定

- 脚本必须能独立于 Web 服务运行，不 import FastAPI。
- 支持 `--dry-run`，先打印将要做什么，避免误删数据。
- 输出 JSON 到 stdout（便于 CI 解析），日志走 stderr。
- 顶部 docstring 写：用途 / 前置条件 / 示例 / 风险。
