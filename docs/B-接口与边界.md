# B · 接口与边界（RAG 引擎与大模型应用）

> 本文件是 B 这一侧的唯一契约。只写 B 交付什么、C 怎么调、以及明确不做什么。
> 上游契约见 `docs/A-接口与边界.md`（ChunkMetadata），团队宪法见提交历史中的 `docs/01-架构与接口契约.md`。

## 1. 边界

**B 负责**：把 A 存进去的 chunk 变成"有依据、可引用、答不上就拒答"的回答。

```
问题 → 向量召回 + BM25 召回 → RRF 融合 → (可选)Rerank
     → 相关度门槛 → Prompt(System+Few-shot+资料+近3轮) → DeepSeek 流式
     → SSE: meta → citation* → delta* → done
```

| 不做 | 归属 | 边界在哪 |
|---|---|---|
| 解析、切片、向量化、入库、删除 | A | B 只读 `chunks` 表与向量库，不改写入口径 |
| 登录 / JWT / 知识库 CRUD / 会话列表页 / 前端 | C | B 只依赖"当前用户 id + kb_ids"，写 `conversations`/`messages` 供 C 读 |
| 用户问题改写、指代消解、微调、Agent 工具链 | 范围外 | 见 `06-范围基线.md` §2，只保留"近 3 轮上下文拼接" |
| OCR / 拍照 / 相似题 / 点赞点踩 | 范围外 | 同上 |

## 2. 产出物

```
backend/app/
├─ rag/
│  ├─ llm.py          # B1 DeepSeek 客户端：流式、首 token 超时重试、token 统计、MOCK_LLM
│  ├─ hybrid.py       # B6 BM25（纯 Python）+ RRF 融合
│  ├─ retriever.py    # B2 向量 + BM25 召回，回表取权威正文
│  ├─ reranker.py     # B7 可选 Rerank（未配置即 no-op）
│  ├─ prompt.py       # B3 System + 三套 Few-shot（方程/函数/证明）+ 拒答话术
│  ├─ context.py      # B9 近 3 轮上下文（按字符预算截断）
│  └─ pipeline.py     # 编排：召回→重排→拒答→生成→事件流
├─ api/chat.py        # B4/B5 POST /api/chat/stream（SSE）
├─ api/schemas.py     # 五个事件模型（追加，未改 A 的字段）
└─ db/chat_models.py  # conversations / messages
scripts/eval.py       # B10 Recall@5 / MRR / 消融，支持从 chunk 反推出题
scripts/dump_openapi.py         # 导出 docs/api/openapi.json（C 生成 TS 类型用）
docs/api/openapi.json           # 机器可读契约（静态，避免 C 依赖后端启动）
docs/api/README.md              # 三个契约文件的用途与联调顺序
docs/api/mock/chat_stream.txt   # 可执行契约：pytest 逐帧反序列化
backend/tests/test_*.py         # 契约、RRF、端到端、越权
```

## 3. `POST /api/chat/stream`

**请求**（`Authorization: Bearer <jwt>`；C 上线前用 `Bearer dev:<name>` 自测）

```json
{ "conversation_id": null, "kb_ids": ["kb_xx"], "question": "判断 f(x)=x^2+2x 的单调性", "stream": true }
```

**响应** `text/event-stream`，事件顺序固定：

| 事件 | 时机 | 字段 |
|---|---|---|
| `meta` | 检索完成、正文开始前 | `message_id, conversation_id, retrieval_ms, hits` |
| `citation` | 正文前，可多条 | `index, chunk_id, doc_id, doc_name, page, snippet, score, content_type` |
| `delta` | 生成中，可多条 | `text` |
| `done` | 结束 | `message_id, tokens_in, tokens_out, latency_ms, first_token_ms, confidence`（追加 `model/refused/answer/citations`） |
| `error` | 异常 | `code, message` |

**错误码（B 用到的）**

| code | HTTP | 场景 |
|---|---|---|
| 1003 | 403 | kb 或会话不属于当前用户 |
| 1004 | 404 | 会话不存在 |
| 4001 | 502 | 大模型失败（已重试 2 次） |
| 4002 | 504 | 检索异常 |
| 5000 | 500 | 内部错误 |

> 越权与参数错误在**建立流之前**返回 JSON 信封（`{code,message,data,request_id}`），不塞进 SSE。

**`stream=false`**：同一接口返回一次性的 `ok({message_id, conversation_id, answer, citations, confidence, refused})`，方便脚本/评估。

**引用跳转原文（C 用）**：`citation.doc_id` + `citation.chunk_id` 直接对上 A 的
`GET /api/docs/{doc_id}/preview?page=1&size=20`，逐条比对 `items[].id` 找锚点；
`page` 只在 PDF 来源里有值，Markdown 为 `null`。不要用 `doc_name` 反查文档，重名会串。

## 4. 检索与拒答

| 参数 | 默认 | 说明 |
|---|---|---|
| `RETRIEVAL_TOP_K` | 20 | 向量、BM25 各取 20 条 |
| `RRF_K` | 60 | RRF 平滑常数，两路按排名融合 |
| `RERANK_TOP_N` | 5 | 送进 Prompt 的片段数；citation 条数 = 它 |
| `HYBRID_ENABLED` | true | false 则退化为纯向量（消融用） |
| `RELEVANCE_THRESHOLD` | 0.35 | 低于此值直接拒答 |

- **拒答（B8）**：候选为空或最高相关度低于阈值 → 输出"未找到依据 + 缺少什么 + 建议补充章节"，`done.refused=true`。
- **置信度**：配了 Rerank 用 rerank 分；否则用向量余弦相似度。dev 哈希向量下该值无实际语义，**切 bge-m3 后需重新标定阈值**。
- **幻觉三层**：门槛拒答 → Prompt 强制 `[n]` → 后处理校验编号（越界引用会被剔除，日志留痕）。

## 5. 配置项（`.env`，已加入 `.env.example`）

`DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS / LLM_TIMEOUT_S / LLM_FIRST_TOKEN_TIMEOUT_S / LLM_MAX_RETRIES / MOCK_LLM / RETRIEVAL_TOP_K / RERANK_TOP_N / RRF_K / HYBRID_ENABLED / RELEVANCE_THRESHOLD / BM25_CACHE_TTL_S / HISTORY_TURNS / HISTORY_CHAR_BUDGET / RERANK_API_BASE / RERANK_API_KEY / RERANK_MODEL / RERANK_TIMEOUT_S`

零新增第三方依赖：httpx（A 已引）、jieba（A 已引）足够，BM25 与 RRF 自己实现。

## 6. 评估（B10）

```bash
# 1) 从已入库 chunk 反推出题（gold = 该 chunk，天然可算 Recall@5）
python scripts/eval.py --build --kb kb_xx --limit 80 --out eval/math_80.jsonl

# 2) 跑检索指标（不调大模型，快、可复现）
python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid

# 3) 三种消融对比
python scripts/eval.py --run --dataset eval/math_80.jsonl --mode vector
python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid
python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid+rerank

# 4) 连生成一起跑（要 DEEPSEEK_API_KEY；会统计引用命中与拒答率，答案正确率仍需人工判定）
python scripts/eval.py --run --dataset eval/math_80.jsonl --mode hybrid --with-answer
```

报告写到 `eval/reports/<时间>_<mode>.json`，字段：

| 字段 | 含义 |
|---|---|
| `recall_at_5` | gold chunk 是否落在前 5 |
| `recall_at_1` | 是否排第一（比 Recall@5 严格，看区分度） |
| `mrr` | 首个命中位置的倒数均值 |
| `refused_rate` / `citation_hit_rate` | 只在 `--with-answer` 时有值 |
| `avg_retrieval_ms` | 单题检索耗时 |
| `query_overlap_mean` / `leak_level` | **评测集自检**，见下 |

**关于指标可信度（必须主动说明）**

题目是用 gold chunk 原文反推的（例题取"解："前的题干，概念取首句），所以 query 与原文
天然字面重合，属于 in-corpus 检索，**Recall 会偏乐观**。脚本会把重合度算出来写进报告：

- 平均字符 2-gram Jaccard ≥ 0.6 → `leak_level=high`，接近"照抄能否命中"
- 0.3–0.6 → `medium`，答辩需说明
- < 0.3 → `low`，措辞已改写，较可信

实测示例语料（8 题）为 `0.53 / medium`。答辩时除报 `recall_at_5`，还要一并给出
`leak_level`，并附 10–20 题**人工改写题**的对照结果，否则会被质疑指标虚高。

> 当前 `knowledge/raw/` 在本机为空（语料 gitignored，只在 A 机器上）。
> 本地只用示例文档验证过链路，**还没有可写进答辩的真实指标**。

## 7. 交给 C 的三个点

1. **鉴权**：`api/chat.py` 用的是 `app.api._dev_user.dev_current_user`（A 的临时替身，签名 `(db, authorization) -> User`）。C 换成 JWT 依赖时签名保持一致即可，B 不用改。
2. **会话接口**：`conversations` / `messages` 两张表由 B 写入、C 读取（`messages.citations` 是 JSON 字符串）。C 的 `GET /api/conversations`、`GET /api/conversations/{id}/messages` 直接查这两张表，字段名见 `db/chat_models.py`。
3. **机器可读契约**：`docs/api/openapi.json`（全量 schema，可直接 `openapi-typescript` 生成类型）
   + `docs/api/mock/chat_stream.txt`（SSE 帧样例，给解析器写单测）。
   后端改动后跑 `python scripts/dump_openapi.py` 重新导出并一起提交，防止契约漂移。

## 8. 已知限制（写进答辩"局限"章）

- `MOCK_LLM=true` 只是模板拼装，**不可用于效果评估**。
- Rerank 默认关闭：没配 `RERANK_API_BASE/KEY` 时按 RRF 顺序截断，消融只能报"纯向量 / +BM25"两档。
- 只做上下文拼接、不做问题改写：指代特别绕的追问仍可能跑偏（范围基线明确砍掉改写）。
- 无停止生成：SSE 单向，C 侧只能 abort 后重新生成（ADR 04）。
- 单进程：BM25 索引是进程内缓存，多 worker 会各建一份（一期单机够用）。
- 回答正确率无法自动判定，只能人工抽检；脚本给的是检索指标与引用命中率。

**环境与升级（2026-10-21 实测，A 换底座后暴露）**

| 现象 | 原因 | 处理 |
|---|---|---|
| 向量路 0 命中，但库里有向量 | Chroma collection 名带 embedding 模型后缀（`math_chunks_BAAI-bge-m3`）；旧数据在 `math_chunks` 里，新代码只查带后缀的名字，**历史向量静默不可见** | 换 embedding 模型或升级后必须 `python scripts/rebuild_index.py` 重建；`data/chroma` 下旧 collection 会残留占空间 |
| `rebuild_index.py` 报 `no such column: documents.tags_json` | A 给 `documents` 加了 `tags_json / difficulty`，但项目用 `create_all` 建表，**不会 ALTER 已存在的旧库** | 升级时删掉旧 `data/app.db` 重建（或让 A 补迁移脚本） |
| `pip install rapidocr_onnxruntime` 失败 | 该包所有版本要求 Python <3.13，本项目 README 推荐 3.13 | 装不上不影响 B（B 不用 OCR）；A 的 `test_ocr.py` 会因此红一条，属 A 侧依赖问题 |

> 上面前两条对 B 的现实含义：**纯向量模式在"换模型/升级"场景下不可靠，`HYBRID_ENABLED=true` 的
> BM25 是兜底**。实测在向量路全空的旧库上，`--mode hybrid` 仍拿到 Recall@5=1.0，`--mode vector` 为 0。
> 这条既是融合检索的价值证据，也提醒上线前必须跑一次重建索引。

## 9. 验证记录

### 2026-10-21（A 换底座后回归）

A 侧 18 个提交把默认向量库切成 Chroma、embedding 收编为 `BaseEmbedding` 抽象、
`documents` 表加了 `tags_json / difficulty`。B 侧针对性回归：

| 项 | 结果 |
|---|---|
| 全量测试 | `pytest -q` **61 passed**（A 25 + B 36），无红 |
| **Chroma 后端兼容** | 新增 `tests/test_chroma_backend.py` 3 条：向量库 id 必须等于 `chunk_id`、metadata 往返后 `doc_id/kb_id` 可溯源、完整检索链路（向量+BM25+RRF+回表）在 Chroma 上跑通 |
| 三档消融 | `vector / hybrid / hybrid+rerank` 全部跑通（`rerank` 未配 key，脚本明确警告"实际等于 hybrid"，不谎报） |
| 向量失效兜底 | 旧库上 `--mode vector` 因 collection 改名 0 命中，`--mode hybrid` 仍 Recall@5=1.0 → 融合检索的兜底价值有实测支撑 |
| 评测集自检 | 反推出题的 query 字面重合度 0.53（`medium`），报告自动带 `leak_level` 与 `caveat`，不再输出无标注的虚高数字 |
| A→B 契约 | 向量 id = `chunk.id`（`indexer.py:160`）、`content_type` 新增 `caption` 值 → B 只透传不判断，无需改 |
| B→C 契约 | `docs/api/openapi.json` 与未改动代码一致，`test_openapi_contract.py` 绿；citation 的 `doc_id` 未回退 |

### 2026-10-19（首次打通）

| 项 | 结果 |
|---|---|
| 测试 | `pytest -q` **38 passed**（A 17 + B 21：SSE 契约 4、BM25/RRF 6、A→B 联调 2、OpenAPI 防漂移 2、端到端/越权/拒答 7） |
| **A→B 联调** | 全程只调 A 的 6 个接口：`/api/docs/upload` 入库 → `/api/chat/stream` 命中该文档；再传一篇，B 立刻可检索（BM25 靠语料指纹失效，不等 TTL）；删除文档后不再召回 |
| 真机 SSE | `POST /api/chat/stream` 输出 `meta → citation×4 → delta… → done`；`done` 带 `confidence / tokens / first_token_ms / model` |
| 引用可溯源 | citation 带 `doc_id + chunk_id`，可直接调 A 的 preview 定位；`snippet` 含完整「题干 + 解 + 公式」 |
| 拒答 | 阈值抬高到 0.99 时输出「未找到依据」，`refused=true`，且不产生 citation |
| 越权 | `Bearer dev:bob` 请求 alice 的 kb → HTTP 403 / code 1003（开流前拦截） |
| 入库联动 | 示例语料 7 chunk（最大 171 token），向量 7 条，`/api/health` 的 `vectors` 一致 |
| 评估链路 | `eval.py --build` 从 chunk 反推出题 → `--run` 出 `recall_at_5 / mrr / avg_retrieval_ms` |
| 契约防漂移 | `docs/api/openapi.json` 与代码不一致时 `test_openapi_contract.py` 直接红；mock 帧逐条 `model_validate` |

**仍缺的验证（答辩前必须补，全部卡在外部资源）**

1. **真实语料指标**：A 已在自己机器接入考研语料（张宇 30 讲 / 线代全书 / 概率论，约 2500 chunk），
   但 `knowledge/raw/` 被 gitignore，本机拿不到。需从 A 机器拷语料到 `knowledge/raw/`，
   再 `python scripts/eval.py --build --kb <id> --limit 80` → 三档 `--run`。
   A 报的 12/12 召回是在他机器上用智谱 embedding-3 跑的，B 这边无法复现，不能直接引用。
2. **`RELEVANCE_THRESHOLD` 标定**：`EMBED_PROVIDER=dev` 是哈希向量，分数分布与 bge-m3 不同，
   现在的 0.35 对真实向量没有意义。切 `api/local` 后要重跑一遍，用"该拒答的题"和"该答的题"
   各 10 条画出分数分布再定。
3. **真实模型**：`DEEPSEEK_API_KEY` 为空，全部走 `MOCK_LLM`。首 token 延迟、引用命中率、
   拒答措辞都未实测。
4. **人工改写题集**：现在只有反推出的题（泄漏 medium）。要证明语义检索而非字面匹配，
   需 10–20 题人工改写（换说法、不共用原文措辞），给出与反推题集的对照。
