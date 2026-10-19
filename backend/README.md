# backend · 后端

## 模块归属（改代码前先看这里）

```
app/
├─ main.py              # 入口，路由挂载       [B 维护]
├─ core/
│  ├─ config.py         # 全局配置             [B]
│  ├─ security.py       # JWT / 密码哈希       [C]
│  ├─ deps.py           # get_current_user    [C]
│  ├─ logging.py        # 结构化日志           [B]
│  └─ exceptions.py     # AppError + 统一异常处理 [B]
├─ api/
│  ├─ schemas.py        # Pydantic 模型 = 契约  [B 主笔，全员提 PR]
│  ├─ auth.py           # 登录注册             [C]
│  ├─ kb.py             # 知识库 CRUD          [C]
│  ├─ doc.py            # 上传/进度/预览/删除   [A]
│  ├─ chat.py           # SSE 问答             [B]
│  └─ feedback.py       # 点赞点踩             [C]
├─ services/
│  ├─ parsing/          # pdf/docx/md/txt 解析与清洗 [A]
│  ├─ segmenter.py      # 知识点/例题/习题识别  [A]
│  ├─ ocr.py            # 图片/扫描件 OCR      [A]
│  ├─ doc_service.py    # 上传任务状态机        [A]
│  └─ tagger.py         # 自动打标签            [A]
├─ rag/
│  ├─ splitter.py       # 公式保护切片          [A]
│  ├─ embedder.py       # 向量化               [A]
│  ├─ indexer.py        # Chroma 读写           [A]
│  ├─ retriever.py      # 向量召回             [B]
│  ├─ hybrid.py         # BM25 + RRF           [B]
│  ├─ reranker.py       # 精排                 [B]
│  ├─ prompt.py         # system/few-shot      [B]
│  ├─ memory.py         # 多轮与 query 改写     [B]
│  ├─ llm.py            # DeepSeek 封装         [B]
│  └─ pipeline.py       # 组装链路             [B]
└─ db/
   ├─ models.py         # 表结构               [C 建，他人只读]
   └─ session.py        # engine/session       [C]
```

> 铁律：`rag/` 不许 import FastAPI；`api/` 不许直接操作 Chroma。

## 本地运行

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env    # 填 DEEPSEEK_API_KEY / EMBED_API_KEY

# 在项目根目录执行（保证 data/ 与 .env 路径一致）
uvicorn app.main:app --reload --port 8000
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

## 约定

- 所有响应都经过 `ApiResponse(code, message, data)`（`core/exceptions.py` 里定义，P1 落地）。
- 所有配置走 `settings`，禁止 `os.getenv`。
- 每个 public 函数写中文 docstring：干什么、参数、返回、异常。
- 新增依赖必须同步 `requirements.txt`。

## 自测

```bash
pytest -q                     # 单元 + 接口
ruff check app && black --check app
```
