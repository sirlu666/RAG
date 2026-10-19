# knowledge · 语料

## 当前状态：空

2026-10-19 已清除全部语料（含维基教科书与示例文件），数据库、向量库、上传目录一并清空：
`documents=0 / chunks=0 / ingest_tasks=0 / knowledge_bases=0`，`data/chroma/local_store.json` 已删除。

**等待提供新的数据来源。** 收到语料后按下面三步入库即可，代码与脚本不需要改。

## 需要什么样的数据

| 项 | 要求 |
|---|---|
| 放置位置 | `knowledge/raw/<科目>/`，例如 `knowledge/raw/calculus/`、`knowledge/raw/highschool/` |
| 格式 | `pdf`（**必须有文字层**）、`docx`、`md`、`txt` |
| 不接受 | 扫描件/纯图片 PDF（按 A 的边界不做 OCR，会被标 `rejected`） |
| 命名 | `<来源>-<书名>-<册次>.<ext>`，例如 `人教A版-必修第一册.pdf` |
| 规模 | Gate 0：≥ 5 万字、≥ 30 处例题（`例 N` / `例题` / `例：` 宽口径） |
| 版权 | 只放有权限使用的资料；对外演示不整段搬运原文，引用需标注来源 |

## 入库三步

```bash
# 1) 体检：字符数 / 页数 / 例题数 / 切片数 / 公式占比（不写库）
python scripts/ingest.py --dir knowledge/raw --dry-run

# 2) 入库（写 data/app.db + data/chroma + data/uploads）
python scripts/ingest.py --dir knowledge/raw --kb 数学教材

# 3) 对账：关系库与向量库 id 必须一致
python scripts/check_consistency.py
```

也可以走接口单文件上传（带进度）：

```bash
curl -F "file=@knowledge/raw/calculus/教材.pdf" http://127.0.0.1:8000/api/docs/upload
```

## 目录约定

| 目录 | 内容 | 是否入库 |
|---|---|---|
| `raw/` | 你提供的原始语料 | ❌（`.gitignore` 排除，避免大文件与版权文件进仓库） |
| `raw/<批次>/manifest.csv` | 如用抓取脚本，记录来源/许可/时间 | ❌ |
| `test/` | 评估用问题集（B 负责） | ❌ 走网盘 |

## 说明：为什么仓库里不留语料

1. 版权：教材 PDF 不能随代码分发；
2. 体积：几十 MB 进 git 会让 clone 变慢、无法回滚；
3. 可复现：只保留入库脚本与体检命令，任何人拿到同一批文件都能重建出一致的 chunk。

历史上曾用中文维基教科书做过验证（95 页 / 40 万字 / 520 chunk），抓取脚本
`scripts/fetch_wikibooks.py` 仍保留；如需恢复该来源，重跑该脚本再入库即可。
