# knowledge · 语料

## 当前语料：BlandAlpha/obsidian_math（考研数学笔记）

来源：<https://github.com/BlandAlpha/obsidian_math>（Obsidian 笔记，GPL-3.0），
2026-10-20 经 `scripts/prepare_obsidian_math.py` 清洗转换，**已入库**（知识库 `考研数学`）。

| 项 | 值（库内实测） |
|---|---|
| 文档 | 114 篇，全部 `ready` |
| chunk | 255（concept 213 / exercise 24 / example 18），平均 174 token，最大 677 |
| 含公式 | 220 / 255（LaTeX 原生，零 OCR 误差） |
| 对账 | 255/255 一致，无孤儿无缺失 |
| **Gate 0** | **通过**（12.8 万字 / 例题宽口径 54 处） |
| 覆盖 | 高数（极限/微分/积分/多元/微分方程）+ 线代（行列式→二次型），**无概率论** |
| 检索验证 | 3 个模拟提问均命中正确章节；精准排序待切 bge-m3（现 dev 哈希向量） |

清洗规则（`scripts/prepare_obsidian_math.py`）：`[[双链]]`→纯文本、`> [!example]` 标注→
**例** 等前缀、frontmatter 与 `#标签` 剥离、目录索引页跳过；`$...$` 公式原样不动。

许可说明：GPL-3.0。本地检索使用无碍；若对外分发衍生语料需遵循同许可并附来源链接。

## 待补语料

- 扫描版教辅（6 本考研数学一 PDF，884 页）：等确认后走 VLM 全量 OCR（约 3 小时）；
- 评估题集：B 负责。

## 需要什么样的数据

| 项 | 要求 |
|---|---|
| 放置位置 | `knowledge/raw/<科目>/`，例如 `knowledge/raw/calculus/`、`knowledge/raw/highschool/` |
| 格式 | `pdf`（**必须有文字层**）、`docx`、`md`、`txt` |
| 扫描件 | 支持，但需开启 `OCR_ENABLE=true`（CPU 约 3–5s/页）；识别质量差或公式错得多的页会保留原文 |
| 命名 | `<来源>-<书名>-<册次>.<ext>`，例如 `人教A版-必修第一册.pdf` |
| 规模 | Gate 0：≥ 5 万字、≥ 30 处例题（`例 N` / `例题` / `例：` 宽口径） |
| 版权 | 只放有权限使用的资料；对外演示不整段搬运原文，引用需标注来源 |

## 入库三步

```bash
# 0) 扫描件先做 OCR（不写库，产物是 md；--pages 用于小样验证）
python scripts/ocr_pdf.py --input knowledge/raw/kaoyan_math1 --out knowledge/raw/kaoyan_math1_ocr --pages 1-3

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
