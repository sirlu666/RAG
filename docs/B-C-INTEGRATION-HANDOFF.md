# B → C 集成交付说明（B-01 ~ B-07）

> 本文件是 B 侧对任务书「MathRAG 问答引擎补齐与交付」的交付说明。
> 交付分支：`codex/b-integration-delivery`（基于 main 合并 A 的 `codex/a-acceptance-fixes` 后）。
> 所有命令可复制执行；密钥与大模型权重不进 Git，见 §5。

---

## 0. 交付总览与逐项状态

| 项 | 状态 | 关键改动 |
|---|---|---|
| B-01 让 C 运行真实 DeepSeek 问答 | ✅ 实现就绪，真实调用待 C 本机配 key | 运行材料与配置模板见 §1 |
| B-02 连接失败重试 | ✅ 已修 + 回归测试 | `rag/llm.py` 网络异常转可重试；`tests/test_llm_retry.py` 6 条 |
| B-03 图片→识别→解答 | ✅ 接口已交付（识别待 A 的 rapidocr 就位） | `POST /api/chat/image/recognize`；复用 A 的 `recognize_question_image` |
| B-04 相似问题与资料推荐 | ✅ 已实现 + 持久化 | `done` 追加 `related_questions/related_materials`；`messages.related` 落库 |
| B-05 消费 A 的知识标签 | ✅ 已实现可解释微调 | `rag/pipeline.py` 知识点命中加分，不排除未标注资料 |
| B-06 Prompt 补题型 | ✅ 已补极值/数列证明 | 三套 → 五套 few-shot，关键词优先级修正 |
| B-07 评估与人工复核表 | ⚠️ 评估就绪，人工复核 **pending** | `eval/human_review_template.csv` 20 条骨架 + 填充工具 |

> **未完成/待真实调用项**（如实标记，不冒充完成）：
> 1. B-07 人工复核表 20 条的 `human_verdict` 尚未由真实的人判定——这是**必须人工**的项，agent 不能自标通过。
> 2. B-03 真实识别、B-01 真实问答证据，均需 C 本机配 `DEEPSEEK_API_KEY` + rapidocr（<3.13）后复现。

---

## 1. 运行材料（B-01）

### 1.1 环境与配置模板

```bash
# .env 追加（B 侧，密钥不进 git）
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MOCK_LLM=false                    # 必须 false 才走真实生成
LLM_MAX_RETRIES=2                 # 连接失败/429/5xx 有界重试（不含首次尝试）
LLM_FIRST_TOKEN_TIMEOUT_S=10      # 首 token 超时退避重试
```

- 团队凭据通过**私密渠道/本机 .env**交接，不进聊天、Git、日志、文档。费用额度归属由团队约定，不默认要求 C 自购账号。
- 没配 key 时设 `MOCK_LLM=true` 可跑通 SSE 链路（回答为模板，**不可评估**）。

### 1.2 本地 rerank 模型

`BAAI/bge-reranker-v2-m3`，目录 `data/models/bge-reranker-v2-m3`（约 2.3GB，可私下传权重）。
`RERANK_PROVIDER=local` 默认启用；加载失败会在日志留痕并降级回融合顺序，**不能仅凭 provider=local 声称真正运行了重排**（诊断看日志 `rerank failed, fallback`）。

### 1.3 一条有依据的数学问题（真实证据，待 C 本机复现）

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" -H "Authorization: Bearer dev" \
  -d '{"kb_ids":["<kb_id>"],"question":"两个重要极限分别是什么"}'
# 期望：meta → citation* → delta* → done；done.model=deepseek-chat，引用可回表
```

---

## 2. 接口契约（B-03 / B-04 新增，均只加不改）

### 2.1 图片识别（B-03）

```
POST /api/chat/image/recognize
multipart: file（png/jpg/jpeg/bmp/webp/tiff，≤10MB，≤16MP）
响应: {code, message, data:{text, latex, warnings}, request_id}
```

- `text`：识别出的完整题目正文（独立公式 LaTeX 已并入正文位置）；
- `latex`：附加抽取的独立公式，**不替代 text**；
- `warnings`：低质量/识别失败/公式未转换，如实返回，不伪造答案。
- C 校对 `text` 后，把最终文字作为 `question` 走既有 `/api/chat/stream`（本接口不落知识库、不改用户资料）。
- 错误码：2002 类型非法 / 2001 过大 / 1001 空 / 2003 缺 OCR 依赖。

### 2.2 推荐（B-04）：`done` 事件追加字段

```json
{
  "...既有字段不变...": "...",
  "related_questions": ["第6讲-一元函数微分学：这题还有哪些不同的解法？"],
  "related_materials": [{"doc_id":"doc_xx","chunk_id":"ch_xx","doc_name":"xx.md","page":null,"seq":12,"char_start":0,"char_end":0,"content_type":"example"}]
}
```

- 默认 `[]`；各 ≤3 项；`related_materials` 来自真实可回表资料（doc_id/chunk_id 可对上 A 的 preview），不编造。
- 相关问题是**可解释规则生成**（锚定命中资料的内容类型+文档主题），非固定三句；`RELATED_QUESTIONS_LLM=true` 可切换为模型生成（默认关，避免额外费用）。
- 旧客户端不读这两个字段也能正常渲染回答（纯追加）。
- 持久化：存 `messages.related`（JSON），历史读取可恢复；`init_db` 已加幂等补列（老库自动 ALTER）。

---

## 3. 标签消费约定（B-05）

B 优先读 `documents.tags_json`（结构体），用 `knowledge_points` 与问题做**子串匹配加分**（0.02~0.05，可解释），只做轻微前移、**绝不排除未标注资料、绝不绕过 kb_ids 权限**。未标注资料照常召回（加分 0）。Chroma metadata 里的 `tags_json`（JSON 字符串）只作冗余备份。

> 诚实边界：标签加分量级很小，主要在 rerank 分数接近时影响 tie-break；**不要把标签微调宣传成"显著提升检索"**——它只提供可解释的路由依据。

---

## 4. 已知限制

- 本地 bge-m3 CPU 编码约 30 条/分钟，全量 2519 条约 90 分钟（A 侧语料）；rerank CPU 每 batch 数十秒。
- B-03 图片识别对复杂手写/任意排版不做准确率承诺（沿用 A 的 A-04 边界）。
- B-04 相关问题默认规则生成，质量不如模型生成；需要更好可切 `RELATED_QUESTIONS_LLM=true`（产生额外 Token 费用）。
- `confidence` 表示检索/重排依据强度，**不是校准后的答案正确概率**，不要把 0.9 渲染成"90% 数学正确"。

---

## 5. 交付物清单

| 文件 | 说明 |
|---|---|
| `backend/app/rag/llm.py` | B-02 网络异常重试 |
| `backend/app/api/chat.py` | B-03 `/image/recognize` + B-04 related 持久化 |
| `backend/app/api/schemas.py` | `ImageRecognizeOut` + `DoneEvent` 追加字段 |
| `backend/app/rag/pipeline.py` | B-04 推荐生成 + B-05 标签微调 |
| `backend/app/rag/retriever.py` | `ChunkRecord.tags_json`（B-05 读标签） |
| `backend/app/rag/prompt.py` | B-06 五套 few-shot |
| `backend/app/db/chat_models.py` | `Message.related` 字段 |
| `backend/app/db/session.py` | `messages.related` 幂等补列 |
| `backend/app/core/config.py` | `related_max` / `related_questions_llm` |
| `docs/api/openapi.json` | 重新导出（含新接口/字段） |
| `eval/human_review_template.csv` | B-07 20 条人工复核骨架（pending） |
| `scripts/fill_review_answers.py` | B-07 真实模型填充 model_answer 工具 |
| `backend/tests/test_{llm_retry,image_recognize_api,recommend,tags_consume,prompt_shots}.py` | B-02~B-06 回归测试 |

---

## 6. 验证命令与结果

```bash
cd backend && pytest -q
# 结果：147 passed，1 failed（test_recognize.py::test_result_shape_contract，
#   因 rapidocr_onnxruntime 全版本要求 Python<3.13，本机 3.13 装不上——A 侧环境依赖，非 B 代码问题）
```

B-02 重试测试（网络桩隔离，不访问真实服务）：

```bash
pytest tests/test_llm_retry.py -q   # 6 passed：首连失败重试/持续失败到上限/429重试/401不重试/首token超时/吐字后不重试
```

真实/模拟证据区分：上述均用 `httpx.MockTransport` 桩 + `MOCK_LLM`，**未**驱动真实 DeepSeek；
真实生成证据见 B-07 复核表（待 C 本机配 key 后由 `scripts/fill_review_answers.py` 产出，人工判定 pending）。

---

## 7. C 需要执行的最少步骤

1. 合并本分支（`codex/b-integration-delivery`），本机配 `.env` 的 `DEEPSEEK_API_KEY`、关 `MOCK_LLM`。
2. 确认 `data/models/bge-reranker-v2-m3` 就位（或从队友拷）。
3. 起服务后 `GET /api/health` 看 `llm.configured=true`、`retrieval.rerank=true`。
4. 联调 `POST /api/chat/image/recognize` 与 `POST /api/chat/stream`（图片校对后把 text 当 question）。
5. B-07 人工复核表：真实人逐条填 `human_verdict`/`verdict_reason`（20 条），填完才算 B-07 关闭。
