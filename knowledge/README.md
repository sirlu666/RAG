# knowledge · 语料

## 当前语料：中文维基教科书（CC BY-SA）

| 项 | 值 |
|---|---|
| 来源 | https://zh.wikibooks.org （中文维基教科书） |
| 书目 | 微积分学 / 线性代数（**高中数学已于 2026-10-19 按要求清除**） |
| 页面数 | 40 |
| 解析后字符 | 107,118 |
| 切片后 | 150 个 chunk，平均 229 token，最大 720 token |
| 公式占比 | 0.87（含 LaTeX 的 chunk 比例） |
| Gate 0 | **未通过**：字符数达标，例题 26 处（要求 ≥30），需补语料 |
| 许可 | CC BY-SA，每篇正文首行都写了来源 URL 与抓取时间 |

变更记录：
- 2026-10-19 清除高中数学 55 页（370 chunk）：原始 md、manifest 记录、向量与数据库记录一并删除；
  需要恢复时重跑 `fetch_wikibooks.py --prefix 高中数学/` 再入库即可。

抓取可复现（`raw/` 不入 git，但脚本与清单保证可重建）：

```bash
# 当前保留：微积分学 + 线性代数（高中数学已清除，如需恢复再加第一行）
# python scripts/fetch_wikibooks.py --prefix 高中数学/ --limit 60
python scripts/fetch_wikibooks.py --prefix 微积分学/ 线性代数/ --limit 45
python scripts/ingest.py --dir knowledge/raw/wikibooks --dry-run   # Gate 0 体检
python scripts/ingest.py --dir knowledge/raw/wikibooks --kb 维基教科书-数学
```

`knowledge/raw/wikibooks/manifest.csv` 记录每篇的 `file / title / url / license / retrieved_at / chars`，
重复抓取会合并清单，不会覆盖旧记录。

### 为什么选它，而不是直接下教材 PDF

1. **授权清楚**：CC BY-SA 允许在标注来源的前提下使用与改编；商业教材 PDF 没有这个条件。
2. **结构友好**：文本层完整、公式是 LaTeX、有例题与习题，不需要 OCR。
3. **可复现**：MediaWiki API 有稳定接口，别人 clone 后能抓到同一批内容。
4. **代价**：行文偏"讲义/百科"而非"教材"，`例 1/例 2` 编号只有 17 处（教材体例才密集编号），
   宽口径（例 N / 例题 / 例：）也只有 26 处，低于 Gate 0 的 30 处门槛——因此**当前语料不足以支撑"教材原题"类提问**。

## 目录与规矩

| 目录 | 内容 | 是否入库 |
|---|---|---|
| `raw/wikibooks/` | 抓取结果 + manifest.csv | ❌（`.gitignore` 排除，可脚本重建） |
| `samples/` | 自写示例语料，用于跑通链路 | ✅ |
| `test/` | 评估用问题集（B 负责） | ❌ 走网盘 |

1. 大文件不入 git；语料用脚本或网盘分发。
2. 文件名规范：`<来源>-<书名>-<册次>.md/pdf`。
3. 每份语料在 manifest 里登记来源与许可；正文首行保留出处。
4. 入库前先 `--dry-run`：一页 PDF 正常 500–1500 字，少于 50 字属扫描件，按边界直接拒收（不做 OCR）。
5. 仅用于课程项目内部评测；对外演示不整段搬运原文，引用时标注来源。
