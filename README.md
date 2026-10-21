# MathRAG · 考研数学 RAG 答疑（A 知识工程 + B RAG 引擎 + C 平台交互）

> 三人组协作仓库：**A（知识工程 / ETL）与 B（RAG 引擎 / 大模型应用）代码已在本仓库**，
> C（平台交互 / 前端）尚未接入。三方通过契约对接：
> **ChunkMetadata（A→B）**、**6 个 `/api/docs/*` 接口（A→C）**、
> **`POST /api/chat/stream`（B→C）**。
>
> 需求基线：`docs/需求说明书.md`（v1.1）
> ｜ A 契约：`docs/A-接口与边界.md`
> ｜ B 契约：`docs/B-接口与边界.md`

## 1. A 负责什么（已完成）

```
上传 → 解析（pdf 文本层 / 扫描件 OCR / docx / md / txt）→ 清洗 → 结构化识别
     → 公式保护切片 → 向量化 → 写关系库 + 向量库 → 状态可查 → 可删除 / 可重建
```

| 能力 | 入口 | 说明 |
|---|---|---|
| 多格式解析 | `services/parsing/loader.py` | pdf/docx/md/txt；PDF 无文字层自动转 OCR |
| 扫描件 OCR | `services/parsing/ocr.py` | 图片→文字、行合并、页眉剥离、独立公式转 LaTeX（3–5s/页 CPU） |
| 结构化识别 | `rag/splitter.py` | 识别 例/习题/定理/定义，保证一道例题不被拆开 |
| 公式保护切片 | `rag/splitter.py` | 占位符法；1000 次切片不截断公式（有单测） |
| 向量化 | `rag/embedder.py` | EmbeddingProvider 三实现：dev 哈希 / api 云端 / **local bge-m3（当前，免费断网）** |
| 索引读写 | `rag/indexer.py` | 关系库正文 + 向量库 metadata，写失败自动回滚 |
| 文档生命周期 | `services/doc_service.py` | 任务状态机、进度、单写锁、删除、重建、同名覆盖 |
| 版本管理 | `services/doc_service.py` | 内容去重（sha256）、`overwrite=true` 删旧建新、重建索引幂等 |
| 6 个接口 | `api/doc.py` | 上传/列表/进度/预览/删除/重建 |
| 离线脚本 | `scripts/*.py` | OCR 预处理、语料体检入库、索引重建、一致性校验 |

**不在本仓库（故意）**：前端、部署、登录鉴权、知识库 CRUD UI、会话列表页。
这些归 C；需要时按契约调用 A/B 的接口（B 的问答接口见 §8，会话表见 `db/chat_models.py`）。

## 2. 目录

```
math-rag-tutor/
├─ backend/app/
│  ├─ api/doc.py           # 6 个文档接口（A 的对外边界）
│  ├─ api/schemas.py       # 文档相关出入参
│  ├─ services/
│  │  ├─ doc_service.py    # 任务状态机 + 后台入库
│  │  ├─ parsing/loader.py # 多格式解析 + 清洗（无文字层转 OCR）
│  │  └─ parsing/ocr.py    # 扫描件：行合并 / 页眉剥离 / 公式→LaTeX
│  ├─ rag/
│  │  ├─ splitter.py       # 公式保护切片
│  │  ├─ embedder.py       # 向量化（dev/api）
│  │  ├─ indexer.py        # 写库 + metadata
│  │  └─ vectorstore.py    # 向量库（local / chroma 可切）
│  ├─ db/models.py         # 文档链路 5 张表
│  ├─ core/                # 配置、异常、鉴权占位
│  └─ main.py              # 只挂载 /api/docs
├─ backend/tests/          # 切片/清洗单测 + 6 接口集成测试
├─ scripts/                # 语料抓取 / OCR 预处理 / 体检入库 / 重建向量 / 对账
├─ knowledge/              # 语料（raw 不入 git；samples/ 是自写示例）
└─ docs/                   # A 的接口与边界（唯一契约）
```

## 3. 跑起来

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env        # 默认 EMBED_PROVIDER=local + VECTOR_BACKEND=chroma

uvicorn app.main:app --reload --port 8000
# 必须从 backend/ 启动（代码里是 `app.*` 绝对导入）；
# .env 与 data/ 的路径由 core/config.py 统一按项目根目录解析，不会分裂。
```

### B / C 新机上手清单（2026-10-21 更新）

1. **装依赖**：`pip install -r requirements.txt`（已含 chromadb / sentence-transformers / torch CPU）；
2. **下模型**（一次性）：
   - embedding（4.3GB）：`python -m pip install modelscope` 然后
     `python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-m3', local_dir='data/models/bge-m3')"`
   - rerank（2.3GB，可选，`RERANK_PROVIDER=local` 才需要）：同样方式下载
     `BAAI/bge-reranker-v2-m3` 到 `data/models/bge-reranker-v2-m3`（或从队友机器拷整个 `data/models/`）；
3. **配 .env**：`cp ../.env.example ../.env`（默认本地 bge-m3 + Chroma + 本地 rerank，无需任何 key）；
4. **语料**：仓库不含语料（版权原因）。找 A 要 `knowledge/raw/` 目录（约 4MB），
   或拿现成的 `data/` 整目录拷贝（免重建）；
5. **有语料没 data 时重建**：`python scripts/ingest.py --dir knowledge/raw --kb 考研数学`，
   然后 `python scripts/rebuild_index.py --full`（本地 bge-m3，CPU 约 90 分钟，可中断续跑）；
6. **自检**：
   - A 侧：`python scripts/verify_work.py` → 应 13 项全过；
   - B 侧：`python scripts/verify_work_b.py` → 应 13 项全过（测试/检索指标/拒答/SSE/契约/交付物/git）；
7. B 的 LLM key 自己配（`.env` 的 `DEEPSEEK_API_KEY`，或临时 `MOCK_LLM=true`）。

### 三条命令验证链路

```bash
# 0) 单测 + 接口集成测试（含后台入库、越权、重复、覆盖、重建）
cd backend && pytest -q && cd ..

# 1) 语料体检（Gate 0：字符数 / 例题数 / chunk 数 / 公式占比，不写库）
#    把语料放到 knowledge/raw/<科目>/ 后执行：
python scripts/ingest.py --dir knowledge/raw --dry-run

# 2) 入库（会写 data/ 下的 sqlite、向量库、上传文件）
python scripts/ingest.py --dir knowledge/raw --kb 数学教材

# 3) 接口自测
curl -F "file=@knowledge/raw/<科目>/<教材>.pdf" http://127.0.0.1:8000/api/docs/upload
curl "http://127.0.0.1:8000/api/docs"
curl "http://127.0.0.1:8000/api/docs/<doc_id>/status"
curl "http://127.0.0.1:8000/api/docs/<doc_id>/preview?page=1&size=5"
```

## 4. 对接契约

### 4.1 A → B：ChunkMetadata（`docs/A-接口与边界.md` §4）

每条向量记录带这些 metadata（Chroma 只接受 str/int/float/bool，`page` 为空时省略）：

```json
{"chunk_id":"ch_xx","user_id":"u_xx","kb_id":"kb_xx","doc_id":"doc_xx",
 "doc_name":"必修一.pdf","subject":"highschool_math","content_type":"example",
 "seq":12,"has_formula":true,"page":132}
```

B 侧检索时这样用（A 已提供存储层）：

```python
from app.rag.vectorstore import get_store
hits = get_store().query(embedding, kb_ids=["kb_xx"], top_k=20)   # -> VectorHit(id, score, metadata, document)
# 正文与页码以关系库 chunks 表为准，metadata 只做过滤与展示
```

### 4.2 A → C：6 个接口（`docs/A-接口与边界.md` §3）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/docs/upload` | multipart：`file` + `kb_id`（可空）+ `overwrite`（默认 false）→ `{doc_id, task_id, status}` |
| GET | `/api/docs?kb_id=` | 文档列表 |
| GET | `/api/docs/{id}/status` | `{status, progress, stage, error, chunk_count}`，前端 1.5s 轮询 |
| GET | `/api/docs/{id}/preview` | 分页预览 chunk |
| DELETE | `/api/docs/{id}` | 删文档 + 向量 + 文件 |
| POST | `/api/docs/{id}/reindex` | 重建索引（重新解析） |

统一响应：`{code, message, data, request_id}`；错误码见 `docs/A-接口与边界.md` §3。

## 5. 给 C 的待接点（我没替你做）

A 侧留了两个：

1. `app/api/_dev_user.py` 是**临时替身**：不校验 token，固定使用 `dev` 用户（`Bearer dev:<name>` 可切用户）。
   请用 JWT 实现替换 `dev_current_user`，签名保持不变，然后删除该文件。
2. `doc_service._ensure_default_kb()` 在没有 `kb_id` 时自动建一个"默认知识库"。
   等 `/api/kbs` 上线后，删掉这个兜底，改为强校验 `kb_id`。

B 侧给 C 的交接点见 **`docs/B-接口与边界.md` §7**（鉴权签名 / 会话表读写 /
机器可读契约 openapi.json + mock / 渲染判定），核心是 `POST /api/chat/stream` 的
SSE 事件流 `meta → citation* → delta* → done`，以及 `refused or declined` 的拒答判定。

## 6. 已知限制（写进答辩的"边界"）

- `EMBED_PROVIDER=dev` 是哈希向量，**只能验证链路通不通，检索质量不可用于评估**；跑评估前必须切 `api` 并重建索引。
- 扫描件可 OCR，但**行内公式仍是 OCR 原文**（`P(BIA)` 这类符号会失真）；只有独立公式行能转成 LaTeX。彻底解决需版面模型（MinerU）或商业接口（Mathpix）。
- 单进程单写者：并发上传会排队，不支持多 worker。
- PDF 双栏/表格按文本流降级，不保证版式。
- A 不实现检索与生成；**B 已接入，见 §8**（A 的边界不变）。

## 7. 验证记录

在隔离 venv（Python 3.13）中实测通过：

```text
pytest -q ................ 80 passed（A 25 + B 55）
```

| 验证项 | 结果 |
|---|---|
| **数据状态** | 已入库：171 篇 Markdown / 2519 chunk（bge-m3 本地向量化 + Chroma），对账 2519=2519 零孤儿 |
| **扫描件 OCR** | 6 本考研 PDF（884 页，0 文字层）实测：文字识别可用；独立公式行转 LaTeX（`\mathbb{P}_N^{*}=N(N-1)\cdots`），行内公式仍为原文 |
| 6 个接口（上传/列表/进度/预览/删除/重建） | 全部通；后台任务执行完 status=ready、progress=100（用测试内联片段验证） |
| 解析与切片 | 例题含"解 + 公式 + 点评"不被拆开；公式不截断；页眉页脚与页码行被清除 |
| 切片上限 | 目标 600 token、硬上限 750；公式表按行重切（历史语料实测最大 739） |
| 版本管理 | 同内容重复上传 → 1005；`overwrite=true` 删旧建新；reindex 前后 chunk 数一致 |
| 隔离 | `Bearer dev:other` 读他人文档 → 403 / 1003 |
| 对账 | `check_consistency.py` → 2519 = 2519 一致 |
| 异常 | 不支持类型 → 2002；`OCR_ENABLE=false` 时无文字层 PDF → rejected/2003 |

> 语料（171 篇）随仓库分发（`knowledge/raw/`，来源与许可见 `knowledge/README.md`），
> 向量快照 `data/chroma/vectors/*.json.gz` 只作归档（A 只实现导出、未实现导入，重建仍走 `ingest.py`）。
> 详细验证记录见 `docs/A-接口与边界.md` 与 `docs/B-接口与边界.md` §9。

## 8. B 侧：问答链路（本仓库已接入）

B 的代码按同一套契约接到了 `backend/app` 里，边界与用法见 **`docs/B-接口与边界.md`**。

```bash
# 契约：POST /api/chat/stream，事件 meta → citation* → delta* → done
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" -H "Authorization: Bearer dev" \
  -d '{"kb_ids":["kb_xxx"],"question":"判断 f(x)=x^2+2x 的单调性"}'
```

- 模块：`rag/llm.py`（DeepSeek 流式+重试）、`rag/hybrid.py`（BM25+RRF）、`rag/retriever.py`、`rag/reranker.py`（本地 bge-reranker-v2-m3）、`rag/prompt.py`（System+3 套 Few-shot）、`rag/context.py`（近 3 轮）、`rag/pipeline.py`（编排）
- 接口：`api/chat.py`；表：`db/chat_models.py`（conversations / messages）
- 评估：`python scripts/eval.py --build --kb kb_xxx` → `--run --mode vector|hybrid|hybrid+rerank`；
  量生成用 `scripts/verify_generation.py`；阈值标定用 `scripts/calibrate_threshold.py`
- 没配 `DEEPSEEK_API_KEY` 时设 `MOCK_LLM=true`，可跑通 SSE 链路（回答是模板，不可评估）
- 依赖零新增：httpx / jieba 都是 A 已引入的；BM25 与 RRF 自实现
- B 的验证记录：`pytest -q` 80 passed，真实语料/真实模型下检索指标、生成指标、阈值标定、rerank 消融全部实测（见 `docs/B-接口与边界.md` §9）
