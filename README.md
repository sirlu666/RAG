# MathRAG · A 的工作区（知识工程 / ETL）

> 三人组项目里 **只属于 A 的部分**：把教材/讲义变成"可检索、可引用、可删除"的 chunk。
> B（RAG 引擎）与 C（平台交互）的代码不在本仓库，两边只通过两份契约对接：
> **ChunkMetadata（A→B）** 和 **6 个 `/api/docs/*` 接口（A→C）**。

## 1. A 负责什么（已完成）

```
上传 → 解析（pdf 文本层 / docx / md / txt）→ 清洗 → 结构化识别 → 公式保护切片
     → 向量化 → 写关系库 + 向量库 → 状态可查 → 可删除 / 可重建
```

| 能力 | 入口 | 说明 |
|---|---|---|
| 多格式解析 | `services/parsing/loader.py` | 只做文本层；扫描件直接拒收（不做 OCR） |
| 结构化识别 | `rag/splitter.py` | 识别 例/习题/定理/定义，保证一道例题不被拆开 |
| 公式保护切片 | `rag/splitter.py` | 占位符法；1000 次切片不截断公式（有单测） |
| 向量化 | `rag/embedder.py` | `dev` 哈希向量（零依赖）/ `api` 调 bge-m3 |
| 索引读写 | `rag/indexer.py` | 关系库正文 + 向量库 metadata，写失败自动回滚 |
| 文档生命周期 | `services/doc_service.py` | 任务状态机、进度、单写锁、删除、重建、同名覆盖 |
| 版本管理 | `services/doc_service.py` | 内容去重（sha256）、`overwrite=true` 删旧建新、重建索引幂等 |
| 6 个接口 | `api/doc.py` | 上传/列表/进度/预览/删除/重建 |
| 离线脚本 | `scripts/*.py` | 语料体检入库、索引重建、一致性校验 |

**不在本仓库（故意）**：前端、部署、登录鉴权、知识库 CRUD、检索/生成、会话。
这些都归 B/C；需要时只按契约调用 A 的接口。

## 2. 目录

```
math-rag-tutor/
├─ backend/app/
│  ├─ api/doc.py           # 6 个文档接口（A 的对外边界）
│  ├─ api/schemas.py       # 文档相关出入参
│  ├─ services/
│  │  ├─ doc_service.py    # 任务状态机 + 后台入库
│  │  └─ parsing/loader.py # 多格式解析 + 清洗
│  ├─ rag/
│  │  ├─ splitter.py       # 公式保护切片
│  │  ├─ embedder.py       # 向量化（dev/api）
│  │  ├─ indexer.py        # 写库 + metadata
│  │  └─ vectorstore.py    # 向量库（local / chroma 可切）
│  ├─ db/models.py         # 文档链路 5 张表
│  ├─ core/                # 配置、异常、鉴权占位
│  └─ main.py              # 只挂载 /api/docs
├─ backend/tests/          # 切片/清洗单测 + 6 接口集成测试
├─ scripts/                # 语料抓取 / 体检入库 / 重建向量 / 一致性对账
├─ knowledge/              # 语料（raw 不入 git；samples/ 是自写示例）
└─ docs/                   # A 的接口与边界（唯一契约）
```

## 3. 跑起来

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env        # 默认 EMBED_PROVIDER=dev，无需任何 key

uvicorn app.main:app --reload --port 8000
# 必须从 backend/ 启动（代码里是 `app.*` 绝对导入）；
# .env 与 data/ 的路径由 core/config.py 统一按项目根目录解析，不会分裂。
```

### 三条命令验证链路

```bash
# 0) 单测 + 接口集成测试（含后台入库、越权、重复、覆盖、重建）
cd backend && pytest -q && cd ..

# 1) 语料体检（Gate 0 用这个：字符数 / 例N / chunk 数 / 公式占比）
python scripts/ingest.py --dir knowledge/raw --dry-run
#    没有语料时先用示例：--dir knowledge/samples

# 2) 入库（会写 data/ 下的 sqlite、向量库、上传文件）
python scripts/ingest.py --dir knowledge/samples --kb 示例库

# 3) 接口自测
curl -F "file=@knowledge/samples/函数与导数.md" http://127.0.0.1:8000/api/docs/upload
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

## 5. 给 C 的两个待接点（我没替你做）

1. `app/api/_dev_user.py` 是**临时替身**：不校验 token，固定使用 `dev` 用户（`Bearer dev:<name>` 可切用户）。
   请用 JWT 实现替换 `dev_current_user`，签名保持不变，然后删除该文件。
2. `doc_service._ensure_default_kb()` 在没有 `kb_id` 时自动建一个"默认知识库"。
   等 `/api/kbs` 上线后，删掉这个兜底，改为强校验 `kb_id`。

## 6. 已知限制（写进答辩的"边界"）

- `EMBED_PROVIDER=dev` 是哈希向量，**只能验证链路通不通，检索质量不可用于评估**；跑评估前必须切 `api` 并重建索引。
- 扫描版 PDF 直接拒收（按 A 的边界不做 OCR）。
- 单进程单写者：并发上传会排队，不支持多 worker。
- PDF 双栏/表格按文本流降级，不保证版式。
- A 不实现检索与生成；**B 已接入，见 §8**（A 的边界不变）。

## 7. 验证记录

在隔离 venv（Python 3.13）中实测通过：

```text
pytest -q ................ 17 passed
```

| 验证项 | 结果 |
|---|---|
| **真实语料** | 中文维基教科书 40 页 / 107,118 字 / 150 chunk；**Gate 0 未通过**（例题 26 处 < 30，需补语料） |
| **入库规模** | 41 个文档全部 `ready`；157 个 chunk（含示例库 7 个）；对账 157/157 一致 |
| 6 个接口（上传/列表/进度/预览/删除/重建） | 全部通；后台任务执行完 status=ready、progress=100 |
| 示例语料 `knowledge/samples/函数与导数.md` | 2220 字节 → 7 个 chunk；例题含"解 + 公式 + 点评"未被拆开 |
| 解析 | 页眉页脚（≥60% 页面重复）与页码行被清除；中文硬换行已合并 |
| 切片上限 | 平均 283 token，最大 739（目标 600 ×1.25），无公式截断 |
| 版本管理 | 同内容重复上传 → 1005；`overwrite=true` 删旧建新；reindex 前后 chunk 数一致 |
| 隔离 | `Bearer dev:other` 读他人文档 → 403 / 1003 |
| 对账与重建 | `check_consistency.py` 一致；`rebuild_index.py` 重建 157 条向量 |
| 异常 | 不支持类型 → 2002；无文字层 PDF → rejected（需真实扫描件复现） |

> 2026-10-19：按要求清除高中数学语料（55 页 / 370 chunk），原始 md、manifest、向量与库记录一并删除。
> 恢复命令：`python scripts/fetch_wikibooks.py --prefix 高中数学/ --limit 60` 再入库。

语料来源与许可：中文维基教科书（CC BY-SA），每篇正文首行保留来源 URL 与抓取时间，明细见
`knowledge/README.md` 与 `knowledge/raw/wikibooks/manifest.csv`。

## 8. B 侧：问答链路（本仓库已接入）

B 的代码按同一套契约接到了 `backend/app` 里，边界与用法见 **`docs/B-接口与边界.md`**。

```bash
# 契约：POST /api/chat/stream，事件 meta → citation* → delta* → done
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" -H "Authorization: Bearer dev" \
  -d '{"kb_ids":["kb_xxx"],"question":"判断 f(x)=x^2+2x 的单调性"}'
```

- 模块：`rag/llm.py`（DeepSeek 流式+重试）、`rag/hybrid.py`（BM25+RRF）、`rag/retriever.py`、`rag/reranker.py`（可选）、`rag/prompt.py`（System+3 套 Few-shot）、`rag/context.py`（近 3 轮）、`rag/pipeline.py`（编排）
- 接口：`api/chat.py`；表：`db/chat_models.py`（conversations / messages）
- 评估：`python scripts/eval.py --build --kb kb_xxx` → `--run --mode vector|hybrid|hybrid+rerank`
- 没配 `DEEPSEEK_API_KEY` 时设 `MOCK_LLM=true`，可跑通 SSE 链路（回答是模板，不可评估）
- 依赖零新增：httpx / jieba 都是 A 已引入的；BM25 与 RRF 自实现
- B 的验证记录：`pytest -q` 34 passed（含 SSE 契约、RRF、端到端流式、越权 403、拒答）
