# B → C 集成交付说明（B-01 ~ B-07）

> 本文件是 B 侧对任务书「MathRAG 问答引擎补齐与交付」的交付说明。
> 交付分支：`codex/b-integration-delivery`（基于 main 合并 A 的 `codex/a-acceptance-fixes` 后）。
> 所有命令可复制执行；密钥与大模型权重不进 Git，见 §5。

---

## 0. 交付总览与逐项状态

> 2026-10-27 按 C 验收报告（`docs/B-ACCEPTANCE-2026-10-27.md`）修复 F1~F4 + 补 D2/D3/D1，
> 详见本文件末尾「§7 验收整改记录」。

| 项 | 状态 | 关键改动 |
|---|---|---|
| B-01 让 C 运行真实 DeepSeek 问答 | ✅ 实现就绪 | 运行材料与配置模板见 §1；真实调用证据见 D1 |
| B-02 连接失败重试 | ✅ 已修 + 回归（含 F2 非流式错误传播） | `rag/llm.py` 网络异常转可重试；`pipeline.answer()` 传播 error；`tests/test_llm_retry.py` + `test_answer_error_semantics.py` |
| B-03 图片→识别→解答 | ✅ 接口已交付（识别待 A 的 rapidocr 就位） | `POST /api/chat/image/recognize`；复用 A 的 `recognize_question_image` |
| B-04 相似问题与资料推荐 | ✅ 已实现 + F3 失败隔离/拒答清空 | `done` 追加 `related_questions/related_materials`；推荐失败降级为空、declined/refused 清空推荐；`messages.related` 落库 |
| B-05 消费 A 的知识标签 | ✅ F1 已修：证据分与排序分分离 | `tag_rank` 只做排序 tie-break，不改 vector_score/rerank_score/拒答判定 |
| B-06 Prompt 补题型 | ✅ 已补极值/数列证明 | 三套 → 五套 few-shot，关键词优先级修正 |
| B-07 评估与人工复核表 | ⚠️ 评估就绪，人工复核 **pending** | `eval/human_review_template.csv` 20 条骨架 + 填充工具（F4 已补多轮上下文） |

> **未完成/待真实调用项**（如实标记，不冒充完成）：
> 1. B-07 人工复核表 20 条的 `human_verdict`：3 条「无依据」已由脚本做**机制行为判定**（auto:pass/fail，非数学对错），其余 17 条数学正确性**必须真人判定**，agent 不自标通过。
> 2. B-03 真实图片识别证据：需 C 本机装 rapidocr（Python <3.13）后复现；B 侧接口与复用逻辑已就绪。

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

### 1.2 本地 rerank 模型（可复现信息，D3）

- 模型：`BAAI/bge-reranker-v2-m3`（许可 apache-2.0），本地目录 `data/models/bge-reranker-v2-m3`。
- **版本 / revision**：`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`（HuggingFace 官方 commit）。
- **权重校验**：`model.safetensors` 大小 `2,271,071,852` 字节（2.27 GB），
  sha256 `d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`
  （与 HF 官方 Xet hash 一致，可校验下载是否完整/被篡改）。
- **下载方式**（换机器复现）：
  ```bash
  # 直连 HF（或设 HF_ENDPOINT=https://hf-mirror.com 走镜像）
  pip install -U "huggingface_hub[cli]"
  huggingface-cli download BAAI/bge-reranker-v2-m3 \
      --revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e \
      --local-dir data/models/bge-reranker-v2-m3
  # 校验：
  sha256sum data/models/bge-reranker-v2-m3/model.safetensors
  ```
- `RERANK_PROVIDER=local` 默认启用；加载失败会在日志留痕并降级回融合顺序，**不能仅凭 provider=local 声称真正运行了重排**（诊断看日志 `rerank failed, fallback`）。
- 真实调用凭据（DeepSeek key、可选 rerank API key）通过**私密渠道/本机 .env**交接，不进聊天、Git、日志、文档；费用额度归属由团队约定，不默认要求 C 自购账号。

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
- 相关问题是**可解释规则生成**（锚定命中资料的内容类型+文档主题），非固定三句；不提供 LLM 生成开关（规则方案是既定实现，避免承诺与实现漂移）。
- 旧客户端不读这两个字段也能正常渲染回答（纯追加）。
- 持久化：存 `messages.related`（JSON），历史读取可恢复；`init_db` 已加幂等补列（老库自动 ALTER）。

---

## 3. 标签消费约定（B-05）

B 优先读 `documents.tags_json`（结构体），用 `knowledge_points` 与问题做**子串匹配**，得到排序键 `tag_rank`（0~0.05）。`tag_rank` 只作为**排序第二键**做 tie-break，**绝不修改 vector_score/rerank_score/confidence/拒答判定**（证据分与排序分分离），也**绝不排除未标注资料、绝不绕过 kb_ids 权限**。未标注资料照常召回（tag_rank=0）。Chroma metadata 里的 `tags_json`（JSON 字符串）只作冗余备份。

> 诚实边界：标签只做排序 tie-break，**不改变"是否拒答"**（0.61 的候选命中标签后仍是 0.61，不会越过 0.62 阈值误放行）；**不要把标签微调宣传成"显著提升检索"**——它只提供可解释的路由依据。

---

## 4. 已知限制

- 本地 bge-m3 CPU 编码约 30 条/分钟，全量 2519 条约 90 分钟（A 侧语料）；rerank CPU 每 batch 数十秒。
- B-03 图片识别对复杂手写/任意排版不做准确率承诺（沿用 A 的 A-04 边界）。
- B-04 相关问题用可解释规则生成，质量上限低于模型生成（这是既定取舍：不额外调用付费模型，保证零费用与确定性）。
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
| `backend/app/core/config.py` | `related_max` |
| `docs/api/openapi.json` | 重新导出（含新接口/字段） |
| `eval/human_review_template.csv` | B-07 20 条人工复核骨架（pending） |
| `scripts/fill_review_answers.py` | B-07 真实模型填充 model_answer 工具 |
| `backend/tests/test_{llm_retry,image_recognize_api,recommend,tags_consume,prompt_shots}.py` | B-02~B-06 回归测试 |

---

## 6. 验证命令与结果

```bash
cd backend && pytest -q
# 结果：158 passed，1 failed（test_recognize.py::test_result_shape_contract，
#   因 rapidocr_onnxruntime 全版本要求 Python<3.13，本机 3.13 装不上——A 侧环境依赖，非 B 代码问题）
```

B-02 重试测试（网络桩隔离，不访问真实服务）：

```bash
pytest tests/test_llm_retry.py -q              # 6 passed：首连失败重试/持续失败到上限/429重试/401不重试/首token超时/吐字后不重试
pytest tests/test_answer_error_semantics.py -q  # 4 passed（F2）：首段前失败传播/部分输出失败传播/正常成功/拒答非错误
pytest tests/test_recommend_failure_isolation.py -q  # 4 passed（F3）：推荐故障降级/declined清空/refused清空/正常推荐
pytest tests/test_tags_consume.py -q            # 9 passed（F1）：tag_rank 不污染证据分/不翻转拒答/不降 BM25
```

真实/模拟证据区分：上述均用 `httpx.MockTransport` 桩 + `MOCK_LLM`，**未**驱动真实 DeepSeek；
真实生成证据见 B-07 复核表（`scripts/fill_review_answers.py` 用真实 key 产出 model_answer，人工判定 pending）。

---

## 7. C 需要执行的最少步骤

1. 合并本分支（`codex/b-integration-delivery`），本机配 `.env` 的 `DEEPSEEK_API_KEY`、关 `MOCK_LLM`。
2. 确认 `data/models/bge-reranker-v2-m3` 就位（见 §1.2 可复现信息，含 revision + sha256）。
3. 起服务后 `GET /api/health` 看 `llm.configured=true`、`retrieval.rerank=true`。
4. 联调 `POST /api/chat/image/recognize` 与 `POST /api/chat/stream`（图片校对后把 text 当 question）。
5. B-07 人工复核表：真实人逐条填 `human_verdict`/`verdict_reason`（数学正确性项），填完才算 B-07 关闭。

---

## 8. 验收整改记录（2026-10-27，回应 C 验收报告 F1~F4 / D1~D3）

| 编号 | 问题 | 修复 | 回归测试 |
|---|---|---|---|
| F1/P1 | 标签微调污染证据分与拒答判定 | `Candidate` 新增 `tag_rank` 排序键；`apply_tag_boost` 不再改 `vector_score`/`rerank_score`；`relevance`（证据分）不含 tag_rank；rerank 排序键改为 `(rerank_score, tag_rank)` | `test_tags_consume.py` 9 条 |
| F2/P1 | 非流式模型失败被当成成功空答案 | `pipeline.answer()` 记录 error 事件，未收 done 即抛 `AppError`（保留原 code/message），不再落库返回 ok | `test_answer_error_semantics.py` 4 条 |
| F3/P1 | 推荐故障破坏主答案 / declined 仍生成推荐 | 推荐生成包 try/except 降级为空；declined 与 refused 一样清空推荐；主答案 done 照常产出 | `test_recommend_failure_isolation.py` 4 条 |
| F4/P2 | 复核工具不传追问历史 | `fill_review_answers.py` 加 `FOLLOWUP_CONTEXT`（h011/h012 首轮上下文）+ `--kb` 显式指定知识库，报告使用库与错误 | 脚本层，`ast` 语法校验 + MOCK 拒绝执行验证 |
| D2 | `RELATED_QUESTIONS_LLM` 开关承诺与实现不符 | 删除该开关（config/.env.example/文档），明确仅支持规则推荐 | — |
| D3 | 重排模型缺可复现信息 | §1.2 补 revision `953dc6f6...` + sha256 `d9e3e081...`（与 HF 官方一致）+ 下载命令 | — |
| D1 | 真实证据与人工复核未完成 | `fill_review_answers.py` 用真实 key 填 20 题 model_answer；「无依据」3 题做机制行为判定 auto:pass/fail；其余 17 题 pending 待真人 | — |

> D1 的「人工数学正确性判定」仍是必须真人的项，本整改只补齐了真实调用证据 + 客观行为判定，未冒充人工通过。
