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
| `citation` | 正文前，可多条 | `index, chunk_id, doc_name, page, snippet, score, content_type` |
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

报告写到 `eval/reports/<时间>_<mode>.json`，包含 `recall_at_5 / mrr / refused_rate / avg_retrieval_ms`。

> 当前 `knowledge/raw/` 为空，**还没有真实指标**。语料入库后再跑，数字才可写进答辩。

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

## 9. 验证记录（2026-10-19）

| 项 | 结果 |
|---|---|
| 测试 | `pytest -q` **34 passed**（A 17 + B 17：SSE 契约 4、BM25/RRF 6、端到端/越权/拒答 7） |
| 真机 SSE | `POST /api/chat/stream` 输出 `meta → citation×4 → delta… → done`；`done` 带 `confidence / tokens / first_token_ms / model` |
| 引用可溯源 | citation 的 `snippet` 含完整「题干 + 解 + 公式」，`doc_name` + `page`（PDF 时）可回跳 |
| 拒答 | 阈值抬高到 0.99 时输出「未找到依据」，`refused=true`，且不产生 citation |
| 越权 | `Bearer dev:bob` 请求 alice 的 kb → HTTP 403 / code 1003（开流前拦截） |
| 入库联动 | 示例语料 7 chunk（最大 171 token），向量 7 条，`/api/health` 的 `vectors` 一致 |
| 评估链路 | `eval.py --build` 从 chunk 反推出题 → `--run` 出 `recall_at_5 / mrr / avg_retrieval_ms` |
| 慢启动 | 首查 ~400ms（BM25 建索引 + Chroma 冷启动），之后缓存命中在百毫秒内 |

**未完成的验证（受环境/资源限制，答辩前必须补）**

1. 真实语料指标缺位：`scripts/fetch_wikibooks.py` 在当前离线环境访问 `zh.wikibooks.org` 时 SSL 握手超时，
   40 万字语料未落到本地。请从 A 的机器拷 `knowledge/raw/wikibooks/`，或换可用网络重跑抓取脚本，
   再执行 `eval.py --build --limit 80` 与三档消融。
2. `EMBED_PROVIDER=dev` 是哈希向量，任何检索指标都只能证明链路通；切 `api` + bge-m3（`EMBED_DIM=1024`）
   并重建索引后，`RELEVANCE_THRESHOLD` 需重新标定。
3. 未接真实模型：`DEEPSEEK_API_KEY` 为空时走 `MOCK_LLM`，生成质量与首 token 延迟均未实测。
