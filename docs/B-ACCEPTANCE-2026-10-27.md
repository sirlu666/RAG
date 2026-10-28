# 学生 B 最新交付验收：未通过，需修复及补齐真实证据

日期：2026-10-27。分支 `codex/b-integration-delivery`，提交 `ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e`。验收标准为 B-AGENT-REQUIREMENTS.md，包含“B-01～B-07全部完成后完整交付”，不采用只交部分功能就让C继续工作的安排。

## 1. 总体结论

主要功能已经有实现，但目前不能判定完整交付通过：补充验收复现4类代码/工具问题；真实问答和图片问答证据、人工数学正确性复核仍未完成。

本轮只验收，不改B实现、不创建修复分支、不合并到main或C、不调用付费模型、不写入用户演示资料。独立副本 `.tmp/b-delivery-review-op_q_6m6`，补充复现脚本在该副本的 `reproduce_b_acceptance.py`，所有数据放副本内新建临时目录。

## 2. 已确认进展和测试

- B分支已包含A的 `8cabbfe` 验收修复，无需重复要求B重做A的5项修复。
- 流式网络重试已有MockTransport回归，首连失败、429、401、首token超时和部分正文后中断均有测试。
- 图片识别接口复用A适配器；推荐字段追加到done事件并持久化；标签参与候选排序；增加极值与数列证明few-shot。
- 人工复核表与填充工具已有，并保留未判定状态，没有把agent结果冒充人工数学正确性通过。
- **本机隔离环境148项测试全部通过，无失败、无跳过**。测试使用Python3.12、dev向量与模拟/受控模型调用，并设置 `OCR_FORMULA=none` 避免可选模型隐式加载，不能据此声称真实公式模型/BGE/DeepSeek全部验证。
- B文档记载其环境147通过1失败；本机已安装依赖的环境未复现该依赖失败，因此不把那一项直接判为B代码缺陷。

## 3. 需修复的问题

### F1 / P1：标签微调污染置信度和拒答判定，BM25回退还会被降分

位置：[pipeline.py:132](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/backend/app/rag/pipeline.py#L132)、[pick:246](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/backend/app/rag/pipeline.py#L246)。

`apply_tag_boost()` 直接修改vector_score/rerank_score，这些字段也被confidence/should_refuse使用，无法满足“只排序、不把本应拒答的问题放行”的说明。

隔离复现（重排关闭或失败回退路径，无真实模型调用）：

- 阈值0.62，候选向量分0.61，命中一个知识标签后变0.63；原本refused=true，实际变false。
- 仅BM25召回候选，bm25_norm=1、vector_score=0，原relevance=0.5；标签加分把vector_score改为0.02，relevance改走向量分分支，实际降至0.02。

修复验收：分离排序分与证据分，标签不伪造新的向量/重排证据、不改变拒答门槛语义；纯BM25回退不能因为标签反而丢失证据分。正式重排、无重排、重排失败三种路径都验证标签如何影响排序；不要只测候选数量保留。

### F2 / P1：非流式模型失败被当成成功空答案

位置：[pipeline.py:376](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/backend/app/rag/pipeline.py#L376)、[chat.py:100](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/backend/app/api/chat.py#L100)。

`run()` 在模型失败时产生error并返回；`answer()` 不处理error，也不验证是否收到done，随后非流式API正常落库并返回ok。

隔离复现：检索有正确候选，模型桩抛AppError(4001)；`stream=false`得到HTTP200、code=0、answer为空，还保存了一条空assistant消息。

修复验收：非流式调用正确传播模型/传输错误，不将未完成回答记为正常成功；部分正文后失败有明确状态/错误，不伪装完整答案。增加首段前失败、部分输出失败、正常成功测试，保证与流式错误语义一致。

### F3 / P1：推荐故障会破坏已生成主回答，模型拒答后仍生成推荐

位置：[pipeline.py:349](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/backend/app/rag/pipeline.py#L349)。

问题一：推荐在主答案输出后同步生成，没有失败隔离。为推荐函数注入RuntimeError后，实际SSE为 `meta → citation → delta → error`，没有done；已生成的正常答案因此变成失败/部分回答。

问题二：只有管线refused分支清空推荐，模型declined分支没有。模型桩返回“未找到依据：检索到的资料无法支持这个问题。”，结果declined=true，related_questions仍非空。

修复验收：推荐错误降级为空，主答案仍正常产生done并持久化；refused/declined等无依据情况均按约定返回空推荐。补推荐故障、模型拒答、正常推荐、推荐历史恢复测试。

### F4 / P2：复核工具没有传入追问历史，不能验证多轮能力

位置：[fill_review_answers.py:42](https://github.com/sirlu666/RAG/blob/ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e/scripts/fill_review_answers.py#L42)。

`_answer_one()` 每题独立调用pipeline.answer(question,kb_ids)，未构建历史。h011写“接上题第二步为什么”，h012问“第二种解法”，实际上没有上题或答案传入。隔离捕获实际调用参数，history_passed=false。

修复验收：为追问用例定义可复现的首轮问题、答案/资料及上下文，再执行追问；明确指定测试知识库，而非默认拿数据库第一个库。报告保留实际资料ID/版本和用量/错误，不让空库或错误库的拒答替代正确性验收。

注意：本项针对评估工具，不表示现有会话load_history完全没实现。

## 4. 需补齐的交付材料和说明

### D1：真实证据与人工复核尚未完成

仓库 `eval/human_review_template.csv` 当前20行，model_answer非空0行、human_verdict非空0行，状态均pending。B交付说明也承认真实DeepSeek、真实图片识别链路及人工复核待C配置后执行。

按用户要求，这些不能转成“C先工作，B以后补齐”：B应提供已获准调用条件下的真实文本/图片问答证据和逐题复核记录；没有真人判定时继续标未完成，不要求agent自行填人工通过。团队凭据和费用归属通过私密渠道明确，不要求C另购账号。

### D2：LLM推荐开关与文档不一致

`RELATED_QUESTIONS_LLM=true` 被配置和交付说明宣称为可切换模型推荐，但pipeline实际仅调用规则函数，没有读取该开关。应实现并测试，或删除该开关承诺、明确仅支持规则推荐。规则方案本身属于允许实现，不要求为完成验收强行增加模型费用。

### D3：运行材料还需要明确

重排模型目前只有模型名称和目录，需提供可复现获取方式及版本/revision或校验信息；真实调用凭据的团队提供方式尚未落地。单凭health.configured或provider=local不能证明成功调用DeepSeek/加载重排。

现有分支仍使用dev_current_user；C完整认证成果尚未提交，这是已知集成边界，不能据此一概判B越权实现错误。B应保留可替换依赖与契约，后续集成C时验证Cookie/CSRF/游客引用隔离；本轮未做C集成。

## 5. 按任务书逐项判定

| 项 | 判定 | 说明 |
|---|---|---|
| B-01 真实问答运行交付 | 部分完成 | 配置/入口存在；真实样例与调用条件待交接 |
| B-02 重试与错误一致性 | 流式回归通过，整体未通过 | 网络重试已修；F2非流式仍吞错误 |
| B-03 图片问答 | 接口实现通过，完整链路待真实验收 | 复用A适配器，但缺真实图题识别→解答证据 |
| B-04 推荐 | 未通过 | F3影响主回答/无依据推荐，D2开关承诺失效 |
| B-05 标签消费 | 未通过 | F1改变拒答/证据分，需要正确分离排序与依据 |
| B-06 Prompt/追问 | Prompt基本实现，追问待验 | 极值/数列few-shot已有，真实追问证据不足 |
| B-07 正确性评估 | 未完成 | F4工具缺上下文，20份答案及人工判定尚空 |

## 6. 整改后复验要求

1. 在B交付分支修复F1～F4，补对应回归；同步D2配置/文档与实际实现。
2. 补D1/D3实际材料或准确标明阻塞条件，不把148项mock/桩测试作为真实数学质量证据。
3. 提供新提交号、逐项状态、验证命令和脱敏结果；不修改C前端、不使用demo资料做测试，不擅自调用付费模型。
4. 用户已授权将本报告同步GitHub供B接收；本次仅交付整改报告，不修改B实现、不代替整改，也不恢复C联调。

结论：有明显进展，现有148项测试通过，但B完整交付尚未通过；不合并、不恢复C联调。
