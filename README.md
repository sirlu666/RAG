# MathRAG · 数学智能答疑与个人知识库系统

> 基于 RAG + 大模型的数学问答系统：拍照/文字提问 → 检索教材与个人资料 → 分步推导 + 引用溯源。
> 三人组课程设计 / 毕业设计项目。

## 一句话定位

不是"再套一个 ChatGPT 壳"，而是**把数学资料变成可检索、可引用、可追溯的知识底座**，让回答有据可查、过程可验证。

## 团队与分工

| 角色 | 定位 | 负责域 | 主要产出 |
|---|---|---|---|
| **A** | 知识工程 / ETL 工程师 | `backend/app/services/parsing`、`backend/app/rag/indexing`、`knowledge/` | 多格式解析、结构化切片、向量入库、增量更新、自动打标签 |
| **B** | AI 算法 / RAG 架构师 | `backend/app/rag`、`backend/app/api/chat` | 混合召回、Rerank、Prompt/Few-shot、流式封装、多轮、评估集 |
| **C** | 全栈 / 前后端一体 | `frontend/`、`backend/app/api/{auth,kb}`、`deploy/` | 对话界面、公式渲染、知识库管理、权限、部署 |

**两个契约交界点（最重要的两份文件）**
1. `docs/01-架构与接口契约.md` §3 `ChunkMetadata` —— A → B 的交接面，第 1 周冻结。
2. `docs/api/README.md` 约定的 OpenAPI 契约 —— B → C 的交接面，第 1 周冻结。

## 技术栈

- **前端**：Vue 3 + Vite + TypeScript + Element Plus + Pinia + markdown-it + KaTeX + highlight.js
- **后端**：FastAPI + Pydantic v2 + SQLAlchemy 2 + SQLite（开发）/ PostgreSQL（部署）
- **RAG**：LangChain（LCEL）+ Chroma + BM25（jieba）+ bge-m3 / bge-reranker
- **大模型**：DeepSeek-chat（OpenAI 兼容接口），流式 SSE
- **解析**：PyMuPDF + python-docx + markdown + PaddleOCR / MinerU（扫描件）
- **部署**：Docker Compose + Nginx

## 目录结构

```
math-rag-tutor/
├─ docs/                 # 全部设计文档（先读 00 → 02 → 03）
│  └─ api/               # 接口契约与 mock 说明
├─ backend/
│  └─ app/
│     ├─ api/            # 路由层：只做参数校验与响应组装
│     ├─ services/       # 业务层：解析、入库、任务状态机
│     ├─ rag/            # 检索与生成：切分、召回、rerank、pipeline
│     ├─ db/             # 模型与迁移
│     └─ core/           # 配置、日志、鉴权、异常
├─ frontend/             # Vue3 应用
├─ knowledge/            # 原始语料（不提交大文件，见 .gitignore）
├─ scripts/              # 离线脚本：批量入库、评估、造数
└─ deploy/               # docker-compose、nginx
```

## 快速开始（P0 阶段即可跑通）

```bash
# 1. 后端
cd backend
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
cp ../.env.example ../.env                          # 填 DEEPSEEK_API_KEY
uvicorn app.main:app --reload --port 8000
# 打开 http://127.0.0.1:8000/docs

# 2. 前端
cd frontend
pnpm install
pnpm dev                                            # http://127.0.0.1:5173，已配 /api 代理
```

## 文档索引

| 文档 | 内容 | 谁最该读 |
|---|---|---|
| [docs/00-项目总览与技术方案.md](docs/00-项目总览与技术方案.md) | 目标、功能优先级、选型理由、关键架构决策（ADR） | 全员 |
| [docs/01-架构与接口契约.md](docs/01-架构与接口契约.md) | 分层、数据模型、Chunk schema、API 清单、SSE 协议 | 全员（冻结项） |
| [docs/02-开发流程与里程碑.md](docs/02-开发流程与里程碑.md) | 10 周 5 阶段、每周计划、DoD、集成节奏 | 全员 |
| [docs/03-三人分工与协作规范.md](docs/03-三人分工与协作规范.md) | WBS、Git 规范、交接清单、沟通节奏 | 全员 |
| [docs/04-风险清单与答辩要点.md](docs/04-风险清单与答辩要点.md) | 风险与对策、答辩问答、Demo 脚本 | 全员 |

## 当前状态

`P0 需求与契约冻结` —— 目录骨架、文档、可运行的 hello-world 后端与前端壳已就位；下一步按 `docs/02` 的 W1 任务开工。
