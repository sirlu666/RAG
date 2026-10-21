# backend · A + B 的后端实现

> 原则：**接口先立住，实现保持最小可用。**
> 本目录同时承载 A 的文档链路（`/api/docs/*`）与 B 的问答链路（`/api/chat/stream`）。
> C（账号 / 知识库 CRUD / 前端）的路由不在此装配，只留挂载点与依赖签名。

## 目录

```
app/
├─ main.py               # 挂载 A（/api/docs/*）+ B（/api/chat/stream）+ /api/health
├─ api/
│  ├─ doc.py             # ★ A 的对外边界：6 个文档接口
│  ├─ chat.py            # ★ B 的对外边界：POST /api/chat/stream（SSE）
│  ├─ schemas.py         # 出入参（A 的文档模型 + B 的五个 SSE 事件模型）
│  └─ _dev_user.py       # ⚠ 鉴权临时替身（C 上线后删）
├─ core/
│  ├─ config.py          # A（embedding/向量库/存储/切片）+ B（LLM/检索/rerank）配置
│  ├─ exceptions.py      # AppError + 统一响应 {code,message,data,request_id}
├─ db/
│  ├─ models.py          # A 的 5 张表（users/knowledge_bases/documents/chunks/ingest_tasks）
│  ├─ chat_models.py     # B 的 2 张表（conversations / messages，供 C 读）
│  └─ session.py         # SQLite WAL + 单写者约定
├─ services/
│  ├─ doc_service.py     # 上传 → 任务 → 后台入库 → 状态/删除/重建
│  └─ parsing/loader.py  # pdf(文本层)/docx/md/txt 解析 + 清洗
└─ rag/
   ├─ splitter.py        # 公式保护切片 + 例题/习题/定理识别（A）
   ├─ embedder.py        # dev 哈希 / api / local bge-m3（A）
   ├─ indexer.py         # 写 chunks + 写向量，失败回滚（A）
   ├─ vectorstore.py     # local 文件实现 / chroma 可选，同一接口（A）
   ├─ llm.py             # DeepSeek 客户端：流式、首 token 超时重试、token 统计（B）
   ├─ hybrid.py          # BM25（纯 Python）+ RRF 融合（B）
   ├─ retriever.py       # 向量 + BM25 召回，回表取权威正文（B）
   ├─ reranker.py        # 可选 Rerank：local/api/none 三 provider（B）
   ├─ prompt.py          # System + 三套 Few-shot + 拒答话术（B）
   ├─ context.py         # 近 3 轮上下文，按字符预算截断（B）
   └─ pipeline.py        # 编排：召回→重排→拒答→生成→事件流（B）
```

## A 的接口（契约见 `docs/A-接口与边界.md` §3）

| 方法 | 路径 | 关键约定 |
|---|---|---|
| POST | `/api/docs/upload` | multipart：`file`、`kb_id`(可空)；返回 `{doc_id, task_id, status}` |
| GET | `/api/docs` | `?kb_id=` 可选；返回 `{id, filename, status, chunk_count, error_msg...}` |
| GET | `/api/docs/{id}/status` | 前端 1.5s 轮询；`progress` 0-100，`stage∈parse/split/embed/index` |
| GET | `/api/docs/{id}/preview` | 分页看 chunk；未 ready 返回 2003 |
| DELETE | `/api/docs/{id}` | 先删向量再删记录，最后删文件 |
| POST | `/api/docs/{id}/reindex` | 重新解析并重建（幂等，不会重复 chunk） |

状态机：`pending → parsing → embedding → ready`，异常走 `failed`（可重试）或 `rejected`（无文字层，需换文件）。

## B 的接口（契约见 `docs/B-接口与边界.md` §3）

| 方法 | 路径 | 关键约定 |
|---|---|---|
| POST | `/api/chat/stream` | SSE 事件流 `meta → citation* → delta* → done`；`stream:false` 时一次性 JSON |

错误码 `1003/1004/4001/4002/5000`；越权与参数错误在开流前返回 JSON 信封。
拒答判定用 `refused or declined`（不是 citation 数量）。

## 依赖与运行

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env                        # 默认 local bge-m3 + Chroma + 本地 rerank，无需 key
pytest -q                                         # 80 passed（A 25 + B 55）
```

> `.env` 与 `data/` 的路径由 `core/config.py` 统一按项目根目录解析；必须从 `backend/` 启动。

## 自测

```bash
cd backend && uvicorn app.main:app --reload --port 8000
curl http://127.0.0.1:8000/api/health          # 健康检查（含 llm/retrieval 状态）
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" -H "Authorization: Bearer dev" \
  -d '{"kb_ids":["kb_xxx"],"question":"两个重要极限分别是什么"}'
```

统一响应：`{"code":0,"message":"ok","data":...,"request_id":"..."}`；非 0 时 `data=null`。

## 两个待对接点（已留好，不替 C 实现）

| # | 位置 | 现状 | 谁来接 |
|---|---|---|---|
| 1 | `api/_dev_user.py::dev_current_user` | 开发占位：不校验 token，固定 `dev` 用户（`Bearer dev:<name>` 切用户） | C 换成 JWT，签名不变 |
| 2 | `services/doc_service.py::_ensure_default_kb` | 没有 `kb_id` 时自动建"默认知识库" | C 的 `/api/kbs` 上线后改为强校验 |
