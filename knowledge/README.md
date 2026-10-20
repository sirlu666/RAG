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

## 第二来源：张宇笔记（patrick-andstar/kaoyan-math-ai）

来源：<https://github.com/patrick-andstar/kaoyan-math-ai>（**无许可证**，内容为 AI 从张宇
教材 PDF 生成的草稿，作者标注"例题未回 PDF 复核"），2026-10-20 经
`scripts/prepare_kaoyan_notes.py` 转换后入库（与上面同一知识库）。

| 项 | 值 |
|---|---|
| 篇数 | 31 讲（30讲 18 + 线代 7 + 概率论 6，每讲取 `标准笔记` 正稿） |
| 字符 | 244,887 |
| 切片 | 448 chunk，平均 254 token，最大 570 |
| 例题 | **704 处（编号 564）**——补齐了 obsidian_math 例题稀疏的短板 |
| 公式占比 | 0.83 |
| **Gate 0** | **通过** |

**库内合计：140 文档 / 696 chunk（concept 587 / exercise 64 / example 45），对账 696/696 一致。**
覆盖：高数 + 线代（两来源互补）+ **概率论（张宇 6 讲）**。
答辩注意：张宇部分注明"AI 生成笔记，未逐题复核"。

### 检索质量（2026-10-20 实测）

embedding 已从 dev 哈希切到**智谱 embedding-3**（2048 维，696 条向量重建，对账一致）。
12 题标注集 top-3 科目命中率：**dev 8/12 → embedding-3 12/12**。
质检：`$$` 配对 696/696、水印残留 0、超长 0、类型抽检 60/60。

## 第三来源：张宇概率论全书原稿（PaddleOCR）

来源：同上仓库 `张宇-概率论与数理统计/paddleocr/_final/`（作者对整本 PDF 的 OCR 原稿，
公式为完整 LaTeX，含全部例题），2026-10-20 经 `scripts/prepare_prob_ocr.py` 清洗入库。

| 项 | 值 |
|---|---|
| 篇数 | 6 讲（与标准笔记同源但内容更全：26.7 万字 vs 1.8 万字） |
| 切片 | 296 chunk（concept 225 / example 67 / theory 4），平均 288 token |
| 例题 | **104 处（编号 99）** |
| 清洗 | 图片嵌入 / `%% 待确认 %%` 标注 / 页码注释已剥除，0 残留 |
| **Gate 0** | **通过** |

**库内合计（三来源）：146 文档 / 992 chunk，对账 992/992 一致。**
概率论检索验证 4/4 命中（全概率/条件概率/泊松分布/最大似然估计）。

## 第四来源：张宇 30 讲（高数）与线性代数全书原稿

来源：同上仓库 `张宇基础30讲/paddleocr/_final/` 与 `张宇-线性代数/paddleocr/_final/`，
2026-10-20 经 `scripts/prepare_zhangyu_ocr.py` 清洗入库（清洗方式同概率论原稿）。

| 项 | 值 |
|---|---|
| 篇数 | 25 讲（30讲 18 + 线代 7） |
| 字符 | 约 130 万（含 LaTeX 记号） |
| 切片 | 1527 chunk（example 504 / theory 89），平均 285 token |
| 例题 | **589 处（编号 569）** |
| **Gate 0** | **通过** |

**库内合计（四来源）：171 文档 / 2436 chunk，对账 2436/2436 一致。**

### 例题充足率终版（2026-10-20）

| 科目 | chunk | 例题/习题类 chunk | 结论 |
|---|---|---|---|
| 高数 | 1535 | 474 | ✅ 充足（30讲原稿 443 处编号例题） |
| 线代 | 528 | 109 | ✅ 充足（原稿补齐后从 12 → 109） |
| 概率论 | 365 | 73 | ✅ 充足（原稿 99 处编号例题） |

已知小瑕疵：2/2436 个 chunk（0.13%）为整块推导公式、长于 750 token 上限——
公式完整性优先于长度上限，属设计取舍。

## 待补语料

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
