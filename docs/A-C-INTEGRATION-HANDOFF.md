# A → C 集成交付说明（A-01 ~ A-04）

> 本文件是 A 侧对任务书「MathRAG 知识工程补齐与交付」的交付说明。
> 所有命令可复制执行，路径通过参数指定，不绑定某台机器盘符。
> 交付分支：`codex/a-integration-delivery`（基于 main `a43d959`）。

---

## 0. 交付总览与逐项状态

| 项 | 状态 | 关键改动文件 |
|---|---|---|
| A-01 模型与数据可复现交付 | ✅ 完成 | `scripts/ingest.py`（目标目录/用户/知识库可指定） |
| A-02 真实自动标签及消费约定 | ✅ 完成 | `scripts/auto_label.py`、`api/doc.py`、`api/schemas.py`、`rag/indexer.py` |
| A-03 更新失败保留旧版本 | ✅ 完成 | `services/doc_service.py`（两阶段提交） |
| A-04 图片识别适配器 | ✅ 完成 | `services/parsing/recognize.py` |

**逐项证据见下文 §6。** 未完成/待真实调用项见 §7。

---

## 1. 环境（新机从零）

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate    # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env

# 下载 bge-m3 权重（一次性 4.3GB，大权重不进 git）
python -m pip install modelscope
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-m3', local_dir='data/models/bge-m3')"
```

**模型版本**：`BAAI/bge-m3`，本地目录 `data/models/bge-m3`，1024 维。
Embedding 配置 `.env` 默认 `EMBED_PROVIDER=local` + `VECTOR_BACKEND=chroma`。

---

## 2. 语料与数据导入（A-01）

### 2.1 语料清单（171 篇，来源与许可见 `knowledge/README.md`）

| 目录 | 篇数 | 来源 | 许可 |
|---|---|---|---|
| `knowledge/raw/obsidian_math/` | 109 | BlandAlpha/obsidian_math | GPL-3.0 |
| `knowledge/raw/zhangyu_notes/` | 31 | patrick-andstar/kaoyan-math-ai | 无（AI 草稿） |
| `knowledge/raw/zhangyu_prob_ocr/` | 6 | 同上（概率论原稿） | 无 |
| `knowledge/raw/zhangyu_full_ocr/` | 25 | 同上（30讲/线代原稿） | 无 |

### 2.2 导入（支持独立目标目录 / 目标用户 / 目标知识库）

```bash
# 导入到独立目录（不污染 data/app.db，可重复执行）
python scripts/ingest.py \
  --dir knowledge/raw \
  --kb 考研数学 \
  --user alice \
  --db .tmp/c-integration/app.db \
  --upload-dir .tmp/c-integration/uploads \
  --chroma-dir .tmp/c-integration/chroma
```

- `--user` 指定归属用户（用户名，不存在则自动创建）。**不固定到 dev**，由 C 账号集成时映射；
- 重跑幂等：`content_hash` 去重，重复执行不产生重复文档/向量；
- 目标路径经环境变量在导入 `app.*` 前注入，与默认 `data/` 完全隔离。

### 2.3 向量快照（可选，免重算）

仓库已带 `data/chroma/vectors/math_chunks_bge-m3.json.gz`（2519 条 / 25.8MB）：

```bash
python scripts/migrate_vectors.py data/chroma/vectors/math_chunks_bge-m3.json.gz
```

> **注意**：快照恢复的是「向量」，关系库（documents/chunks 表）仍需 §2.2 的 ingest 重建。
> 二者靠 `vector.id == chunks.id` 对齐（见 §6 对账命令）。

---

## 3. 自动标签（A-02）

### 3.1 配置（独立凭据，不假定复用 DeepSeek/VLM key）

`.env` 追加：

```
LABEL_API_BASE=https://open.bigmodel.cn/api/paas/v4
LABEL_API_KEY=<你的 key>
LABEL_MODEL=glm-4-flash
```

留空则回退 `VLM_API_*`；两者都空时脚本明确报「待真实调用」，不伪造标签。

### 3.2 执行

```bash
python scripts/auto_label.py                          # 全部未打标文档
python scripts/auto_label.py --db .tmp/c-integration/app.db --user alice   # 指定库/用户
python scripts/auto_label.py --scope doc_xxx          # 只打某个文档
python scripts/auto_label.py --force                  # 覆盖重打
```

### 3.3 标签约定（C 消费）

`documents.tags_json`（JSON 对象）：

```json
{"knowledge_points": ["伴随矩阵", "行列式"], "question_types": ["计算题"], "difficulty": "基础"}
```

- `knowledge_points`：string[]，≤6 项，每项 ≤40 字符；
- `question_types`：string[]，≤5 项，每项 ≤24 字符；
- `difficulty`：`基础` / `进阶` / `困难`（枚举校验，非法不落库）。

`GET /api/docs` 返回追加字段（未标注为空数组 / null）：

```
knowledge_points: string[]   # 未标注 []
question_types:   string[]   # 未标注 []
difficulty:       string|null
```

**B 读源约定**：优先读数据库 `documents.tags_json`；Chroma metadata 里存 `tags_json`（JSON 字符串，Chroma 只接受标量）与 `difficulty`（标量）作冗余备份。

---

## 4. 安全替换（A-03）

- `overwrite=True` 上传同名文件时，**先建新、后删旧**：旧文档软标记 `superseded`，新文档解析+切片+向量化全部成功后才物理删除旧文档；
- 新文档解析失败（rejected）→ 旧文档自动恢复 `ready`，正文/向量/文件原样可用；
- `reindex` 同样两阶段：新 chunk 写入成功后才清旧 chunk，重建失败旧索引保留；
- 覆盖期间若同名文档正在入库，返回 1005 拒绝（版本冲突保护）。

---

## 5. 图片识别适配器（A-04）

供 B 调用，签名：

```python
from app.services.parsing.recognize import recognize_question_image
result = recognize_question_image(filename: str, raw: bytes)
# -> {"text": str, "latex": str, "warnings": list[str]}
```

- 不创建知识库文档、不落索引、不改用户资料；
- 输入校验：类型（png/jpg/jpeg/bmp/webp/tiff）、大小（≤10MB）、像素（≤16MP），非法抛 `AppError`；
- 引擎：`OCR_ENGINE=rapid`（本地 CPU 离线）或 `vlm`（整图转录，公式更好，需配置凭据）；
- 识别失败/低质量如实返回 `warnings`，不伪造答案。

---

## 6. 实际验证命令与结果（含真实/模拟区分）

### 6.1 全量测试（模拟，无外部依赖）

```bash
cd backend && python -m pytest -q
# 结果：95 passed（原 80 + 新增 15：doc_api 覆盖失败回归 1 + 标签契约 6 + 识别适配器 8）
```

### 6.2 A-01 独立目录导入（真实执行，本地 bge-m3 + Chroma）

```bash
python scripts/ingest.py --dir knowledge/raw/obsidian_math --kb 考研数学 --user alice \
  --db .tmp/c-integration/app.db --upload-dir .tmp/c-integration/uploads --chroma-dir .tmp/c-integration/chroma
# 结果：109 文档 ready / 248 chunk，归属 alice（非 dev）；重跑仍 109/248，无重复
```

### 6.3 A-02 真实打标（真实调用 glm-4-flash，3 篇样本）

```bash
python scripts/auto_label.py --db .tmp/c-label-test/app.db --user alice
# 结果：3/3 成功。样例（伴随矩阵.md）：
#   knowledge_points=["伴随矩阵","行列式","代数余子式","矩阵乘法","矩阵的逆"]
#   question_types=["计算题","证明题"]  difficulty="基础"
```

### 6.4 A-03 覆盖失败回归（模拟，测试内复现任务书缺陷）

```bash
cd backend && python -m pytest -q tests/test_doc_api.py::test_overwrite_failure_keeps_old
# 结果：pass —— 覆盖上传"仅 1 字符"新文件 → rejected，旧文档仍 ready 且 chunk_count>=3
```

### 6.5 A-04 真实识别（真实 rapidocr，本地 CPU）

```bash
cd backend && OCR_ENGINE=rapid python -c "from app.services.parsing.recognize import recognize_question_image; \
  import pathlib; print(recognize_question_image('page7.png', pathlib.Path('../.tmp/page7.png').read_bytes())['text'][:80])"
# 结果：识别出「函数的概念及其性质…例1.1 已知2f(x)+f(1-x)=x²，求f(x)」
```

### 6.6 对账（向量 id 与 chunk id 一致）

```bash
python scripts/check_consistency.py   # 期望 {"consistent": true, missing/orphan 均为空}
```

---

## 7. 尚缺材料 / 待真实调用

| 项 | 说明 |
|---|---|
| ~~真实库 171 篇标签重打~~ | ✅ **已完成**（2026-10-26）：`auto_label.py --force` 重打 171/171 成功，难度枚举/长度/数量全合规（0 不合规）。产物导出 `data/label_export.json`（私密交接，不进 git） |
| MD/PDF/DOCX 各一份打标验证 | 任务书要求三种格式各一份真实打标；已用 MD 验证，PDF/DOCX 待有样例文件后补（解析入口已统一走 `load_pages`，三种格式共用同一正文入口） |
| 向量快照的关系数据 ID 映射 | 快照 gz 只含向量；关系库需 §2.2 ingest 重建，靠 `vector.id==chunks.id` 对齐（已在对账脚本验证） |

---

## 8. 失败恢复

- **入库失败**：`run_ingest` 抛 AppError 时，文档状态 `rejected/failed`，不残留半成品 chunk；覆盖场景旧文档自动回滚；
- **向量库损坏**：`python scripts/rebuild_index.py --full`（可中断续跑）；或 `migrate_vectors.py` 从快照恢复；
- **数据库损坏**：语料在 `knowledge/raw/`，`ingest.py` 可随时重建。

## 9. 已知限制

- bge-m3 本地 CPU 编码约 30 条/分钟，全量 2519 条约 90 分钟（可中断续跑）；
- 图片识别（A-04）对复杂手写/任意排版不做准确率承诺；
- 张宇语料为 AI 生成草稿（无许可证），答辩需注明，不作为正式教材来源。
