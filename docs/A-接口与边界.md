# A · 接口与边界

> 本文件是 A 这一侧的唯一契约。只写 A 产出什么、别人怎么调、以及明确不做什么。
> B/C 的内部实现不在本文件也不在本仓库。

## 1. 边界

**A 负责**：把资料变成"可检索、可引用、可删除"的 chunk，并把这件事包装成 6 个接口。

```
上传 → 解析（pdf 文本层 / 扫描件 OCR / docx / md / txt）→ 清洗 → 结构化识别
     → 公式保护切片 → 向量化 → 写关系库 + 向量库 → 状态可查 → 可删除 / 可重建
```

扫描件走 OCR 管线：`rapidocr` 识别文字（CPU，约 3–5s/页）→ 按行合并 → 页眉页脚清洗
→ 独立公式行用 `pix2tex` 转 LaTeX（或接 Mathpix 兼容接口）。

**A 不负责**（分别归 B / C）：

| 不做 | 归属 | 边界在哪 |
|---|---|---|
| 检索、融合、Rerank、Prompt、生成、SSE 问答 | B | B 读 A 写入的 chunks 与向量，自己实现检索 |
| 登录、JWT、知识库 CRUD、会话历史、前端 | C | A 只依赖"当前用户 id"和"知识库 id"两个值 |
| 自动打标签 / 相似题 / 拍照入口（前端） | 范围外 | 见 §7 |

## 2. 产出物

```
backend/
├─ app/api/doc.py            # 6 个接口（A 的对外边界）
├─ app/api/schemas.py        # 文档出入参
├─ app/api/_dev_user.py      # 鉴权临时替身（C 上线后删）
├─ app/services/
│  ├─ doc_service.py         # 上传 → 任务 → 入库 → 状态/删除/重建
│  ├─ parsing/loader.py      # 多格式解析 + 清洗（PDF 无文字层时转 OCR）
│  └─ parsing/ocr.py         # 扫描件：行合并 / 页眉剥离 / 公式转 LaTeX
├─ app/rag/
│  ├─ splitter.py            # 公式保护切片 + 例题/习题/定理识别
│  ├─ embedder.py            # dev 哈希向量 / api bge-m3
│  ├─ indexer.py             # 写 chunks + 写向量（失败回滚）
│  └─ vectorstore.py         # local 文件实现 / chroma 可选
├─ app/db/models.py          # users/kbs 最小外键 + documents/chunks/ingest_tasks
├─ app/core/config.py        # embedding / 向量库 / 存储 / 切片
├─ app/core/exceptions.py    # AppError + 统一响应
└─ app/main.py               # 只挂载 /api/docs
scripts/fetch_wikibooks.py   # 抓取中文维基教科书语料（CC BY-SA，带 manifest）
scripts/ocr_pdf.py           # 扫描版 PDF → markdown（OCR 预处理，不写库）
scripts/ingest.py            # 语料体检（--dry-run）与批量入库
scripts/rebuild_index.py     # 从 chunks 表重建向量
scripts/check_consistency.py # 关系库与向量库 id 对账
backend/tests/               # 切片/清洗单测 + 6 接口集成测试
knowledge/raw/               # 语料目录（不入 git，等待提供）
```

## 3. 六个接口

统一响应：`{"code":0,"message":"ok","data":...,"request_id":"..."}`；非 0 时 `data=null`。

| # | 方法 | 路径 | 入参 | 出参 |
|---|---|---|---|---|
| 1 | POST | `/api/docs/upload` | multipart：`file`、`kb_id`(可空)、`overwrite`(默认 false) | `{doc_id, task_id, status}` |
| 2 | GET | `/api/docs` | `?kb_id=` 可选 | 文档数组（含 `status`/`chunk_count`/`error_msg`） |
| 3 | GET | `/api/docs/{id}/status` | — | `{doc_id,status,progress,stage,error,chunk_count}` |
| 4 | GET | `/api/docs/{id}/preview` | `?page=1&size=20` | `{doc_id,total,page,size,items[]}` |
| 5 | DELETE | `/api/docs/{id}` | — | `{doc_id,deleted:true}` |
| 6 | POST | `/api/docs/{id}/reindex` | — | `{doc_id,task_id,status:"pending"}` |

**状态机**

```
pending → parsing → embedding → ready
                    ↘ failed（可重试）    ↘ rejected（无文字层，需换文件；不可重试）
```

`progress`：parse 0-40、split 40-60、embed 60-95、index 95-100。前端建议 1.5s 轮询 #3。

**版本管理（避免旧数据污染检索）**

| 场景 | 行为 |
|---|---|
| 同库、同内容（sha256 相同） | 拒绝，返回 1005 |
| 同库、同文件名、内容不同，`overwrite=false` | 当作新文档并存（历史版本保留） |
| 同库、同文件名、`overwrite=true` | 先删旧文档（向量 → chunks → 文件），再建新文档 |
| 只想重跑解析 | `POST /api/docs/{id}/reindex`，幂等，不会产生重复 chunk |
| 只坏了向量库 | `scripts/rebuild_index.py`，从 chunks 表重建，不重新解析 |

**A 用到的错误码**

| code | HTTP | 场景 |
|---|---|---|
| 1001 | 400 | 参数校验失败 / 空文件 |
| 1003 | 403 | 文档或知识库不属于当前用户 |
| 1004 | 404 | 文档/知识库不存在 |
| 1005 | 409 | 同库内重复文件（sha256 相同） |
| 2001 | 413 | 超过 50MB |
| 2002 | 415 | 不支持的类型 |
| 2003 | 422 | 无文字层 / 解析后内容过少 / 未 ready 就预览 |
| 5000 | 500 | 内部错误 |

## 4. A → B 的契约：ChunkMetadata

向量库中每条记录：`id = chunk.id`，`document = chunk.content`，`embedding = vector`，
`metadata` 只能是下表子集（Chroma 仅接受 str/int/float/bool，`page` 为空时省略，禁止嵌套）。

| key | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chunk_id` | str | ✅ | 与关系库 `chunks.id` 一致 |
| `user_id` | str | ✅ | 隔离兜底 |
| `kb_id` | str | ✅ | 检索过滤主键 |
| `doc_id` | str | ✅ | 删除与溯源 |
| `doc_name` | str | ✅ | 展示用文件名 |
| `subject` | str | ✅ | 学科标识 |
| `content_type` | str | ✅ | `concept\|example\|exercise\|theory\|caption\|other` |
| `page` | int | ❌ | PDF 页码，从 1 开始 |
| `seq` | int | ✅ | 文档内顺序号 |
| `has_formula` | bool | ✅ | 含 LaTeX 为 true |

**B 怎么用**

```python
from app.rag.vectorstore import get_store
hits = get_store().query(embedding, kb_ids=["kb_xx"], top_k=20)
# VectorHit(id, score, metadata, document)
# 正文与页码以关系库 chunks 表为准，metadata 只做过滤与展示
```

## 5. 切片规格（A 的自检标准）

| 项 | 规格 |
|---|---|
| 目标长度 | 400–800 tokens（中文约 300–600 字） |
| 上限 | 目标 600 token；硬上限约 750（×1.25） |
| 公式膨胀 | 占位符比公式短，还原后超限的 chunk 按行重切；单行若是一条超长公式则保持原子不拆 |
| overlap | 80–120 tokens，仅在被迫切断时使用 |
| 公式保护 | 切点不得落在 `$...$` / `$$...$$` / `\begin{}...\end{}` 内部 |
| 单元完整性 | 例题的"题干 + 解/证明/分析/答案 + 点评"合并成一个 chunk |
| 标题归属 | 短标题不单独成 chunk，作为下一段的前缀（保留上下文） |
| 噪声 | 页码行；页眉页脚按"≥60% 页面重复"统计清洗 |
| 扫描件 | 每页有效字符 < 50 → 自动 OCR；`OCR_ENABLE=false` 时 `rejected` |

## 6. 两个交接点（A 已留位，不替别人实现）

| # | 位置 | 现状 | 谁接 |
|---|---|---|---|
| 1 | `api/_dev_user.py::dev_current_user` | 不校验 token，固定 `dev` 用户；支持 `Bearer dev:<name>` 做多用户自测 | C 换成 JWT，签名不变，删除该文件 |
| 2 | `doc_service._ensure_default_kb` | 没有 `kb_id` 时自动建"默认知识库" | C 的 `/api/kbs` 上线后改为对 `kb_id` 强校验 |

## 7. 范围外（A 侧明确不做）

自动打标签、相似题、拍照入口（前端裁切/上传）、检索与生成、前端、部署、鉴权实现、会话历史。
理由见仓库提交历史中的范围基线；一句话：**删掉它，A 的哪项指标会下降？答不出就不做。**

## 8. 已知限制

- `EMBED_PROVIDER=dev` 是哈希向量，只能验证链路；指标必须切 `api` + bge-m3 并重建索引。
- 仓库内不含任何语料（2026-10-19 全部清除）：由项目负责人提供，放 `knowledge/raw/` 后按 `knowledge/README.md` 三步入库；
  Gate 0 需用真实语料复跑后才能给出结论。
- OCR 是 CPU 推理：约 3–5s/页；884 页的书要 45–75 分钟，入库任务在前端显示 `stage=ocr`。
- 公式识别只对"独立公式行"生效；夹在中文里的行内公式仍保留 OCR 原文（`P(BIA)` 这类符号会失真），
  想彻底解决需要版面模型（MinerU）或商业接口（Mathpix）。
- PDF 只做文本层；双栏/表格按文本流降级，不保证版式。
- 检索质量不在 A 的责任范围，A 保证的是"切得对、存得住、删得干净"。
