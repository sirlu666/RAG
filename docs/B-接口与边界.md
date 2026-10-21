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
| `citation` | 正文前，可多条 | `index, chunk_id, doc_id, doc_name, page, snippet, score, content_type, seq, char_start, char_end` |
| `delta` | 生成中，可多条 | `text` |
| `done` | 结束 | `message_id, tokens_in, tokens_out, latency_ms, first_token_ms, confidence`（追加 `model/refused/declined/answer/citations`） |
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

**定位片段（C 用）**：当前语料 171 篇全是 Markdown，`page` **恒为 `null`**，只靠 `page`
跳不过去。因此 citation 追加了三个定位字段：

| 字段 | 含义 | 怎么用 |
|---|---|---|
| `seq` | 该 chunk 在文档内的序号（从 0 起） | 按 chunk 顺序翻页/上下条 |
| `char_start` / `char_end` | 该 chunk 在**原文全文**中的字符区间 | 拿到 `GET /api/docs/{doc_id}` 的全文后切片高亮 |

两者都给了，PDF 用 `page`，Markdown 用字符区间。老数据（升级前入库）`char_start=char_end=0`，
此时退回按 `seq` 定位——字段一定是数字，不会是 `null`，C 侧可以直接解构。

**拒答的两种形态（C 用）**，别把第二种当答案渲染：

| 字段 | 触发 | 表现 |
|---|---|---|
| `done.refused=true` | 检索最高分低于阈值，**没调用模型** | 无 `citation` 事件，`answer` 为固定话术，`first_token_ms=0` |
| `done.declined=true` | 检索过了阈值，但模型读完资料仍说"未找到依据" | 有 `citation`（≥1），正文以"未找到依据"开头 |

C 侧统一判定条件：**`refused or declined` → 按"无依据"样式展示**（灰底 + 建议补充方向），
不要用 `citation` 数量判断——`declined` 时引用数是大于 0 的。
判定实现见 `pipeline.answer_declined()`：只认**正文开头**的"未找到依据"，
因为模型常在一段真答案结尾补"未找到依据：资料未给出 X"作小注（实测存在），用包含匹配会误杀好答案。

## 4. 检索与拒答

| 参数 | 默认 | 说明 |
|---|---|---|
| `RETRIEVAL_TOP_K` | 20 | 向量、BM25 各取 20 条 |
| `RRF_K` | 60 | RRF 平滑常数，两路按排名融合 |
| `RERANK_TOP_N` | 5 | 送进 Prompt 的片段数；citation 条数 = 它 |
| `RERANK_PROVIDER` | `local` | `local` 本地 bge-reranker-v2-m3 / `api` OpenAI 兼容 / `none` 不重排 |
| `HYBRID_ENABLED` | true | false 则退化为纯向量（消融用） |
| `RELEVANCE_THRESHOLD` | **0.62** | 低于此值直接拒答（标定方法见 §6.1） |

- **拒答（B8）**：候选为空或最高相关度低于阈值 → 输出"未找到依据 + 缺少什么 + 建议补充章节"，`done.refused=true`。
- **置信度**：配了 Rerank 用 rerank 分；否则用向量余弦相似度。
  **注意 bge-m3 的余弦分布整体偏高**：域外问题也有 0.48–0.57，所以阈值必须重标，不能沿用小模型时代的经验值。
- **幻觉三层**：门槛拒答 → Prompt 强制 `[n]` → 后处理校验编号（越界引用会被剔除，日志留痕）。

## 5. 配置项（`.env`，已加入 `.env.example`）

`DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS / LLM_TIMEOUT_S / LLM_FIRST_TOKEN_TIMEOUT_S / LLM_MAX_RETRIES / MOCK_LLM / RETRIEVAL_TOP_K / RERANK_TOP_N / RRF_K / HYBRID_ENABLED / RELEVANCE_THRESHOLD / BM25_CACHE_TTL_S / HISTORY_TURNS / HISTORY_CHAR_BUDGET / RERANK_PROVIDER / RERANK_LOCAL_MODEL / RERANK_API_BASE / RERANK_API_KEY / RERANK_MODEL / RERANK_TIMEOUT_S`

零新增第三方依赖：httpx（A 已引）、jieba（A 已引）足够，BM25 与 RRF 自己实现；
本地 rerank 复用 embedding 已引入的 sentence-transformers（CrossEncoder），不另装包。

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

# 5) 只量生成（B1）：首 token 延迟 / 端到端延迟 / 引用越界率 / 域外拒答，含冷启动单列
python scripts/verify_generation.py --dataset eval/math_80.jsonl --limit 12
```

`eval.py` 量**检索**（不依赖大模型，可离线）；`verify_generation.py` 量**生成**（必须有真实
`DEEPSEEK_API_KEY`，MOCK 模式下脚本直接拒绝执行）。两者分开是因为检索指标要能天天跑，
而生成指标每次都要花钱。

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

实测真实语料（80 题）为 `0.33 / medium`。答辩时除报 `recall_at_5`，还要一并给出
`leak_level`，并附 10–20 题**人工改写题**的对照结果，否则会被质疑指标虚高。

**真实语料三档消融（2026-10-21，bge-m3 + 2519 chunk + 80 题）**

| 模式 | Recall@5 | Recall@1 | MRR | 平均检索耗时 |
|---|---|---|---|---|
| `vector`（纯向量） | 0.9625 | 0.8750 | 0.9167 | 389 ms |
| `hybrid`（向量 + BM25 + RRF） | **1.0000** | **0.9125** | **0.9542** | 439 ms |
| `hybrid+rerank`（本地 bge-reranker-v2-m3） | 1.0000 | 0.9000 | 0.9421 | 446 ms |

- 混合检索把 Recall@5 从 96.25% 拉到 **100%**，MRR +0.037（+4.1%），代价约 50 ms。
  这是 B6 融合检索的价值证据，且是同一批题、同一模型的公平对照。
- **rerank 在反推题集上没有提升、甚至微降**（Recall@1 0.9125→0.90，MRR 0.9542→0.9421）。
  这不是 bug，是反推出题的必然：题就是从 gold chunk 原文反推的，RRF 已经把 gold 排进
  前 1–2 位，rerank 没有可提升空间；而 reranker 对"照抄原文"的题排序偏好与 RRF 略有差异，
  导致个别题从第 1 掉到第 2。**rerank 的真实价值要拿改写题（措辞不再照抄）才测得出来**，
  那种题向量相似度下降、BM25 也匹配不上，语义重排才发力。
- rerank 的诚实定位：它是**兜底再排一遍**，不是万能增益。反推题集上打平=正常；
  答辩时要么配一套人工改写题证明它的价值，要么如实说明"在本语料上 rerank 未带来指标提升"。

**人工改写题集三档消融（2026-10-21，18 题，`eval/math_18_rewritten.jsonl`）**

换措辞、不照抄原文的手工出题，字面重合度 0.32（反推题为 0.53），用于对冲反推题的乐观偏差：

| 模式 | Recall@5 | Recall@1 | MRR | 平均检索耗时 |
|---|---|---|---|---|
| `vector` | 0.6111 | 0.2778 | 0.4259 | 912 ms |
| `hybrid` | 0.6111 | 0.2778 | 0.3815 | 993 ms |
| `hybrid+rerank` | 0.6111 | 0.2778 | 0.3815 | 1017 ms |

- **Recall@5 从反推题的 100% 掉到 61%**，这才是"真实用户换说法提问"的难度。反推题的
  100% 确实含水（字面泄漏），答辩必须同时给两组数字，不能只报 100%。
- **rerank 在改写题上仍无提升**。根因不是 rerank 无效，而是**召回阶段已经把 gold 丢了**：
  18 题里只有 4 题（r005/r010/r011/r016）gold 完全没进 top20 召回池（rerank 的输入），
  其余 14 题里 12 题已进 top20、11 题已进 top5——rerank 只重排 top20，能救的题几乎为 0。
  **瓶颈在召回（向量相似度 + BM25 够不到改写后的语义），不在重排**。这是比"rerank 提升 X%"
  更硬的结论：它指明下一轮优化方向是改进召回（如 query 改写、增大召回候选数 top_k、
  多路召回），而不是继续在重排上做文章。
- 改写题集里还有少量**标注噪声**：库里存在内容几乎相同的重复切片（如"二重积分=面积"性质
  在多份文档重复出现），个别 gold 指到了重复切片而非检索返回的那条，会轻微低估指标。
  这不影响"召回是瓶颈"的定性结论，但说明 A 侧去重有改进空间（见 §8）。

> 语料已随仓库分发（`knowledge/raw/` 171 篇，2026-10-21 由 A 提交），
> 上表是在本机重新入库后的实测结果，可复现：`ingest.py` → `check_consistency.py` → 上述命令。

### 6.1 标定拒答阈值（B8）

`RELEVANCE_THRESHOLD=0.35` 原本是拍的。现在有脚本可复现：

```bash
python scripts/calibrate_threshold.py --kb kb_xx --limit 40          # 出报告
python scripts/calibrate_threshold.py --kb kb_xx --limit 40 --review # 加逐题分数
```

它取两类样本的 `top_score` 分布：**正样本**=chunk 反推题（该答），**负样本**=12 条域外问题
（问做饭/历史/编程，该拒），然后：

- 判可分性（完全可分 / p90-p10 基本可分 / 大幅重叠不可分）
- 给建议阈值 + 回测 `false_refusal_rate`（该答却拒）与 `false_accept_rate`（该拒却答）
- **不可分时明确报"不可分"**，不硬给数字——那说明是 embedding 没区分力，换阈值救不了

**真实语料实测（bge-m3 + 2519 chunk，2026-10-21）**

| 样本 | n | min | p10 | median | p90 | max |
|---|---|---|---|---|---|---|
| 正样本（该答） | 40 | 0.509 | 0.691 | 0.801 | 0.968 | 0.998 |
| 负样本（域外，该拒） | 12 | 0.483 | 0.500 | 0.500 | 0.559 | 0.565 |

判读：`基本可分`，重叠区间 0.509–0.565，建议阈值 **0.625**，落地取 **0.62**。

**这次标定的关键发现**：原默认值 0.35 在 bge-m3 上 `false_accept_rate = 100%`——
域外问题最低 0.483 也远高于 0.35，等于**拒答防线完全失效，任何问题都会被硬答**。
改成 0.62 后：误放 0%，误拒 2.5%（1/40 条正样本被拒）。
这不是调参问题，是换 embedding 后**必须**做的迁移动作。

对照（旧的 dev 哈希向量）：负样本 0.00–0.21、正样本 0.41–0.97，建议 0.31。
两套分布完全不同，所以 `config.py` 里的默认值和 `.env.example` 都已改成 0.62，
并注明"dev 模式需自行下调"。

## 7. 交给 C 的三个点

1. **鉴权**：`api/chat.py` 用的是 `app.api._dev_user.dev_current_user`（A 的临时替身，签名 `(db, authorization) -> User`）。C 换成 JWT 依赖时签名保持一致即可，B 不用改。
2. **会话接口**：`conversations` / `messages` 两张表由 B 写入、C 读取（`messages.citations` 是 JSON 字符串）。C 的 `GET /api/conversations`、`GET /api/conversations/{id}/messages` 直接查这两张表，字段名见 `db/chat_models.py`。
3. **机器可读契约**：`docs/api/openapi.json`（全量 schema，可直接 `openapi-typescript` 生成类型）
   + `docs/api/mock/chat_stream.txt`（SSE 帧样例，给解析器写单测）。
   后端改动后跑 `python scripts/dump_openapi.py` 重新导出并一起提交，防止契约漂移。
4. **渲染判定**：正文一律按 Markdown 渲染（含 `$...$` / `$$...$$` LaTeX）；
   `refused or declined` → 走"无依据"样式；citation 的 `page` 对 Markdown 语料恒为 `null`，
   此时用 `char_start/char_end` 定位（详见 §3）。

## 8. 已知限制（写进答辩"局限"章）

- `MOCK_LLM=true` 只是模板拼装，**不可用于效果评估**。
- Rerank 默认走**本地**模型（`RERANK_PROVIDER=local`，bge-reranker-v2-m3 约 2.3GB）；
  设 `none` 则按 RRF 顺序截断（消融"纯向量 / +BM25"两档用），设 `api` 走 OpenAI 兼容接口。
  任何 provider 失败都会静默降级回融合顺序，不阻断问答。
- 只做上下文拼接、不做问题改写：指代特别绕的追问仍可能跑偏（范围基线明确砍掉改写）。
  这条与改写题集暴露的"召回瓶颈"呼应——见 §6，下一轮优化方向是召回而非重排。
- 无停止生成：SSE 单向，C 侧只能 abort 后重新生成（ADR 04）。
- 单进程：BM25 索引是进程内缓存，多 worker 会各建一份（一期单机够用）。
- 回答正确率无法自动判定，只能人工抽检；脚本给的是检索指标与引用命中率。

**环境与升级（2026-10-21 实测，A 换底座后暴露）**

| 现象 | 原因 | 处理 |
|---|---|---|
| 向量路 0 命中，但库里有向量 | Chroma collection 名绑定 embedding 模型：`local` 模式取模型目录名（`math_chunks_bge-m3`）、`api` 模式取 `EMBED_MODEL`（`math_chunks_BAAI-bge-m3`）。旧数据在别的名字下，新代码只查当前名字，**历史向量静默不可见** | 换 embedding 模型或升级后必须 `python scripts/rebuild_index.py` 重建；`data/chroma` 下旧 collection 会残留占空间 |
| `rebuild_index.py` 报 `no such column: documents.tags_json` | A 给 `documents` 加了 `tags_json / difficulty`，但项目用 `create_all` 建表，**不会 ALTER 已存在的旧库** | 升级时删掉旧 `data/app.db` 重建（或让 A 补迁移脚本） |
| `pip install rapidocr_onnxruntime` 失败 | 该包所有版本要求 Python <3.13，本项目 README 推荐 3.13 | 装不上不影响 B（B 不用 OCR）；A 的 `test_ocr.py` 会因此红一条，属 A 侧依赖问题 |
| `EMBED_PROVIDER=dev` 时 `EMBED_DIM` **不生效** | `HashEmbedding` 的维度写死 `dim=256`，不读 `settings.embed_dim`。开发者在 `.env` 写 `EMBED_DIM=1024`（bge-m3）后再切 dev，向量是 256 维而库认为 1024 维 | 属 A 侧代码；B 已在 `tests/conftest.py` 把测试环境的 `EMBED_DIM` 钉成 256 隔离，避免开发者 `.env` 污染测试。**生产要切 dev 兜底时须同步把 `EMBED_DIM` 改回 256** |
| **向量快照（`data/chroma/vectors/*.json.gz`）拿不到就用不上** | A 只实现了 `snapshot_vectors()` **导出**，没有对应导入；且快照以 A 的 `chunk_id` 为键，而 `indexer.py` 用 `new_id("ch")` **随机生成** chunk_id，重新入库后 id 全变，快照里的向量挂不到新 chunk 上 | 正路仍是 `ingest.py` 重新入库（实测 2519 chunk 在本机 CPU 约 67 分钟）。若要让快照真正可分发给 B/C，需 A 把 chunk_id 做成内容相关（如 `hash(doc_id+seq+content)`），或提供带正文的完整恢复脚本 |
| **语料存在重复切片** | 同一知识点（如"二重积分=面积"的性质、"实对称矩阵"性质）在多个文档里出现，切片后产生内容几乎相同的多个 chunk，检索命中任一条都对但 gold 只能标一条 | 属 A 侧语料去重问题（入库前按文档指纹去重，或切片时对高度重合块合并）。B 侧评估时表现为改写题的 Recall 被轻微低估，不影响"召回是瓶颈"的定性结论 |

> 上面前两条对 B 的现实含义：**纯向量模式在"换模型/升级"场景下不可靠，`HYBRID_ENABLED=true` 的
> BM25 是兜底**。实测在向量路全空的旧库上，`--mode hybrid` 仍拿到 Recall@5=1.0，`--mode vector` 为 0。
> 这条既是融合检索的价值证据，也提醒上线前必须跑一次重建索引。

## 9. 验证记录

### 2026-10-21（人工改写题集：召回是瓶颈，重排无米下锅）

反推题集的 100% 有水（字面泄漏），补齐 **18 题人工改写题**（`eval/math_18_rewritten.jsonl`，
换措辞、不照抄原文，字面重合度 0.32 vs 反推题 0.53）做对照。

| 模式 | Recall@5 | Recall@1 | MRR |
|---|---|---|---|
| `vector` | 0.6111 | 0.2778 | 0.4259 |
| `hybrid` | 0.6111 | 0.2778 | 0.3815 |
| `hybrid+rerank` | 0.6111 | 0.2778 | 0.3815 |

- Recall@5 从 100% 掉到 **61%**，这是真实用户换说法提问的难度，答辩必须两组数字一起报。
- rerank 仍无提升的根因：18 题里 14 题 gold 已进 top20 召回池、11 题已进 top5，只有 4 题
  （r005/r010/r011/r016）gold 没进召回池。rerank 只重排 top20，能救的题≈0。
  **瓶颈在召回阶段（改写后语义向量 + BM25 都够不到），不在重排**——下一轮优化方向是
  query 改写 / 增大 top_k / 多路召回，而不是继续调 rerank。
- 少量标注噪声：库内存在内容重复的切片（如"二重积分=面积"多份文档重复），个别 gold 指到
  重复切片，轻微低估指标，不影响定性结论。

### 2026-10-21（Rerank 落地：本地 bge-reranker-v2-m3）

补上此前一直空着的 `hybrid+rerank` 消融档，走**本地模型**，不依赖任何第三方 key。

| 模式 | Recall@5 | Recall@1 | MRR | 平均耗时 |
|---|---|---|---|---|
| `hybrid` | 1.0000 | 0.9125 | 0.9542 | 439 ms |
| `hybrid+rerank` | 1.0000 | 0.9000 | 0.9421 | 446 ms |

- rerank 在反推题集上**无提升甚至微降**（见 §6 的完整分析），这是反推出题的必然，不是 bug。
  已如实记录，不谎报"重排增益"。
- 模型：`BAAI/bge-reranker-v2-m3`，本机 CPU 加载 13s、单题推理 0.24s、区分度极强
  （相关片段 0.99 vs 无关 0.00）。
- 新增 `RERANK_PROVIDER`（`local`/`api`/`none`），默认 `local`；失败降级回融合顺序。
- `rerank_enabled: true, provider: local` 已在报告里确认生效（不是 fallback）。

### 2026-10-21（真实模型 deepseek-chat 接入验收）

`.env` 配 `DEEPSEEK_API_KEY` 后，全部结论从 `MOCK_LLM` 切到真实生成。
脚本：`python scripts/verify_generation.py --dataset eval/math_80.jsonl --limit 12`。

**延迟（12 题，已排除冷启动）**

| 指标 | p50 | p90 | mean | max |
|---|---|---|---|---|
| 首 token | **982 ms** | 1287 ms | 953 ms | 1331 ms |
| 端到端 | **2088 ms** | 3032 ms | 2312 ms | 3404 ms |
| 输出长度 | 197 tok | 367 tok | 241 tok | 450 tok |

稳态吞吐 **104 tok/s**。首 token ~1s 意味着"用户打完问题，1 秒内开始出字"，这是体验的关键指标；
端到端 2s 左右，`max_tokens=2048` 没有成为瓶颈（实际最长只用到 450 tok）。

| 项 | 结果 | 说明 |
|---|---|---|
| 引用编号越界率 | **0 / 12** | 第三层幻觉防线（`sanitize_citations`）一次都没触发，说明 prompt 的编号约束在真实模型上被遵守 |
| 引用命中率 | **12 / 12** | 每条答案的引用里都含该题 gold chunk |
| 域内拒答率 | 0 / 12 | 没有把该答的题误拒 |
| 域外拒答率 | **12 / 12** | 做饭/历史/编程等 12 题全部 `refused`，`citation=0`，且 `first_token_ms=0` 证实**未调用模型**（不花钱、不耗延迟） |
| 引用标记数 | p50 5.5 / max 15 | 答案正文平均带 6 处 `[n]`，来源可逐条核对 |
| 测试 | `pytest -q` **73 passed** | |

**冷启动是唯一的延迟风险**：预热那一次 173 tok 用了 **17.3 s**（首 token 仍 1.07 s，
但流在中途长时间停顿），预热后同样的题 1.6–3.4 s。生产上如果服务冷启动后才有人提问，
第一个用户会等十几秒。建议 C 侧首个请求给更宽松的超时（≥30s），或服务启动时打一次预热请求。

**发现的答案形态问题（已修）**：2 / 12 题检索过了阈值、引用了 5 条资料，但模型判断
"资料只是笔记/待办条目，答不了这个问题"，于是正文直接以"未找到依据"开头拒答——
此时 `refused=false`，C 侧会把拒答当正常答案渲染。已追加 `done.declined` 区分（见 §3），
且判定只认正文开头，避免误杀"真答案 + 结尾小注"（洛必达那题就是后者）。

### 2026-10-21（真实语料全链路验收）

语料从 A 公开的两个源仓库按 `prepare_*.py` 自己重建，本机独立入库，**不依赖 A 的机器**。

| 项 | 结果 |
|---|---|
| 语料 | 生成 176 篇 → 剔除 5 篇 GitHub 模板（2 个 ISSUE_TEMPLATE、README、欢迎页）后 **171 篇**，与 A 分发的版本逐文件比对一致；另发现 1 篇《伴随矩阵》内容有差异，不影响规模 |
| 入库 | 首轮 2526 chunk → 删除模板文档后 **2519 chunk**，与 A 的向量快照 2519 条完全对齐 |
| 对账 | `check_consistency.py`：db 2519 = vector 2519，`missing_in_store=[]`、`orphan_in_store=[]` |
| 类型分布 | concept 1752 / example 616 / theory 93 / exercise 64 / caption 1（模板文档删除前） |
| **真实检索指标** | `vector` Recall@5 0.9625 → `hybrid` **1.0000**；MRR 0.9167 → 0.9542（详见 §6） |
| **拒答标定** | 0.35 → **0.62**；原阈值下域外问题误放率 100%，新阈值 0%（详见 §6.1） |
| 拒答实测 | 域外 3 题（红烧肉/唐朝皇帝/Python GIL）top_score 0.50–0.52 → **全部拒答且 0 引用**；域内 2 题 0.68/0.72 → 正常答，各 5 条引用 |
| 端到端 SSE | `POST /api/chat/stream` → HTTP 200 `text/event-stream`，事件 `meta(1) → citation(5) → delta(10) → done(1)` |
| 测试 | `pytest -q` **67 passed** |

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
| **阈值标定（B8）** | 新增 `scripts/calibrate_threshold.py`：示例语料上正样本 0.41–0.97 / 负样本 0.00–0.21 完全可分，建议 0.31，当前 0.35 的误拒/误放均为 0；两类分不开时明确报"不可分"而非硬给数字 |
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

**仍缺的验证（答辩前必须补）**

1. **真实模型**：`DEEPSEEK_API_KEY` 为空，全部走 `MOCK_LLM`。首 token 延迟、引用命中率、
   拒答措辞都未实测——这是目前唯一挡住"完整答辩"的硬缺口。
2. **Rerank 一档**：没配 `RERANK_API_BASE/KEY`，`hybrid+rerank` 实际等于 `hybrid`。
   要报"重排有没有用"，必须配一个 bge-reranker 兼容接口再跑一次。
3. **人工改写题集**：~~只有反推出的题~~ 已补 18 题改写题（`eval/math_18_rewritten.jsonl`，
   字面重合度 0.32），结论见上方"人工改写题集"小节。若要进一步坐实，可扩到 30–50 题并
   让 A 同步做语料去重（当前存在重复切片噪声）。
4. **回答正确率**：脚本只能给检索指标与引用命中率，答案对不对仍需人工抽检 20 条左右。

> 已完成（原计划卡外部资源的两项）：真实语料指标与拒答阈值标定，
> 见上方"真实语料全链路验收"。语料与向量快照 A 已随仓库分发，换机器可直接复现。
