# backend · A 的后端切片

> 原则：**接口先立住，实现保持最小可用。** 当前只暴露 A 对外的 6 个文档接口，
> B（问答）与 C（账号/知识库）的模块一律不在此目录实现，只留挂载点与依赖签名。

## 目录

```
app/
├─ main.py               # 只挂载 /api/docs；B/C 的路由是注释位
├─ api/
│  ├─ doc.py             # ★ A 的对外边界：6 个接口
│  └─ schemas.py         # 文档出入参（B 的 SSE 模型后续在这里追加）
├─ core/
│  ├─ config.py          # A 的配置（embedding / 向量库 / 存储 / 切片）
│  ├─ exceptions.py      # AppError + 统一响应 {code,message,data,request_id}
│  ├─ _dev_user.py       # ⚠ 鉴权临时替身（C 上线后删）
├─ db/
│  ├─ models.py          # 只含 A 需要的 5 张表
│  └─ session.py         # SQLite WAL + 单写者约定
├─ services/
│  ├─ doc_service.py     # 上传 → 任务 → 后台入库 → 状态/删除/重建
│  └─ parsing/loader.py  # pdf(文本层)/docx/md/txt 解析 + 清洗
└─ rag/
   ├─ splitter.py        # 公式保护切片 + 例题/习题/定理识别
   ├─ embedder.py        # dev 哈希向量 / api bge-m3
   ├─ indexer.py         # 写 chunks + 写向量（失败回滚）
   └─ vectorstore.py     # local 文件实现 / chroma 可选，同一接口
```

## A 的接口（契约见 docs/A-接口与边界.md §3）

| 方法 | 路径 | 关键约定 |
|---|---|---|
| POST | `/api/docs/upload` | multipart：`file`、`kb_id`(可空)；返回 `{doc_id, task_id, status}` |
| GET | `/api/docs` | `?kb_id=` 可选；返回 `{id, filename, status, chunk_count, error_msg...}` |
| GET | `/api/docs/{id}/status` | 前端 1.5s 轮询；`progress` 0-100，`stage∈parse/split/embed/index` |
| GET | `/api/docs/{id}/preview` | 分页看 chunk；未 ready 返回 2003 |
| DELETE | `/api/docs/{id}` | 先删向量再删记录，最后删文件 |
| POST | `/api/docs/{id}/reindex` | 重新解析并重建（幂等，不会重复 chunk） |

状态机：`pending → parsing → embedding → ready`，异常走 `failed`（可重试）或 `rejected`（无文字层，需换文件）。

### 自测

```bash
cd backend && uvicorn app.main:app --reload --port 8000
curl -F "file=@../knowledge/raw/demo.md" http://127.0.0.1:8000/api/docs/upload
curl "http://127.0.0.1:8000/api/docs"
curl "http://127.0.0.1:8000/api/health"
```

统一响应：`{"code":0,"message":"ok","data":...,"request_id":"..."}`；非 0 时 `data=null`。

## 依赖与运行

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example ../.env
pytest -q                # 切片与清洗的单元测试
ruff check app
```

## 还没做的（A 的后续清单，不是接口阻塞项）

1. `EMBED_PROVIDER=api` 联调 bge-m3，并做 300/500/800 三档切片对比（决定最终 chunk 大小）。
2. PDF 页眉页脚统计式清洗（当前只处理页码行与硬换行）。
3. `rebuild_index.py`、`check_consistency.py` 两个运维脚本。
4. Chroma 后端的真机验证（当前默认 local 文件实现，接口一致）。
5. 并发压测：单写锁下的排队行为要给出数据。

## 两个待对接点（已留好，不替 B/C 实现）

| # | 位置 | 现状 | 谁来接 |
|---|---|---|---|
| 1 | `api/_dev_user.py::dev_current_user` | 开发占位：不校验 token，固定 `dev` 用户 | C 换成 JWT，签名不变 |
| 2 | `services/doc_service.py::_ensure_default_kb` | 没有 `kb_id` 时自动建"默认知识库" | C 的 `/api/kbs` 上线后改为强校验 |
