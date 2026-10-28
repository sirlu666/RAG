# A/B 原始分工与 GitHub 交付核对

核对日期：2026-10-26。结论：A/B 的主要文档处理、检索与生成代码已交付，但对照用户原始分工，不能判定全部完成。最明确的功能缺项为 B 的图片提问问答链路与相似问题推荐；A 的标签消费闭环、B 的回答正确率验收及两处稳定性问题也未闭合。

## 核对范围与证据

- 仓库：<https://github.com/sirlu666/RAG>。
- 经 GitHub 插件读取仓库及模型客户端，并以 git ls-remote 确认 main 为 `a43d959be6aad38767e8b3a737f3bb648df3beb6`，与本地 HEAD 相同。
- 审查使用 `git show HEAD:<path>` 与此提交的隔离导出副本，不把本地 C 未提交的新增功能算作 A/B 交付。
- 判断标准为用户原始 A/B 分工。旧文档将自动标签、拍照问答、相似题列为范围外，不视为用户同意取消。
- 用户已明确当前仓库是最新交付，最终使用 DeepSeek。因此 qwen → DeepSeek 不再列为缺项。
- GitHub 基线全部 80 项后端测试在 `.tmp/ab-audit-0xaoi1lb` 独立副本通过。使用测试夹具的哈希向量、模拟回答；Chroma 相关测试也通过。未加载 BGE 权重、未调用真实大模型。
- 两处缺陷通过额外隔离复现确认。未修改 A/B 实现，未影响当前服务、账号或 `.tmp/c-demo`。

状态解释：“主要完成”表示代码及相关测试存在；不等于数学质量或当前电脑上的真实联调已验收。“部分完成”表示有实际实现但原分工闭环仍不足。“未实现”指该提交的代码和接口中未找到对应实现。

## 学生 A

| 原始职责 | 结论 | 已有实现与实际边界 |
|---|---|---|
| 多格式解析、扫描 OCR、数学公式 LaTeX | 主要完成，有质量限制 | loader.py 支持 PDF、DOCX、MD、TXT；ocr.py 支持扫描 PDF 文字识别、独立公式识别；vlm.py 支持整页图片转录。Rapid 模式的行内公式/复杂排版仍有限制；VLM 的效果依赖对应服务。GitHub 原版文档上传不接受 PNG/JPG，这部分后来由本地 C 补上，不能重复算为 A 原交付。 |
| 数学切片：知识点/例题/习题、保护公式上下文 | 主要完成 | splitter.py 按段落、类型、例题与解答分组，公式占位保护，超长递归切分和 overlap。属于规则实现，并非训练过的语义模型；文档对结构化准确率的抽检状态存在前后不一致。 |
| BGE 向量化、Chroma、集合与索引 | 主要完成 | embedder.py 提供 dev/api/local；vectorstore.py 提供 Chroma、按模型区分 collection、按 kb_id 过滤；indexer.py 提供批处理和重建。依赖和实现齐全，权重需另行交付或下载。 |
| 增量更新、删除、重新索引、避免旧数据污染 | 部分完成，旧路径有缺陷 | 有去重、覆盖、删除、重建及一致性工具，但旧 overwrite 路径先删旧数据再解析新文件；失败无法保留旧文档。reindex 也提前删除旧索引，失败后的恢复能力不足。 |
| 自动标签：知识点、题型、难度，供 B/C 使用 | 部分完成，已有离线自动打标 | scripts/auto_label.py 确实调用模型生成三类标签并写入数据库，不应说 A 完全没做。问题是路径固定 data/app.db、原文件按 UTF-8 文本读取，未复用 PDF/DOCX 解析正文；配置依赖 VLM 接口而非 DeepSeek。上传链路没有自动调度该脚本；是否要求随上传触发需明确，不把手工启动批处理本身判为算法未完成。GitHub 原版 DocOut 不返回标签，B 检索也未读取标签路由。当前 C 已补列表标签展示接口，但需 A 的真实标签数据验收。 |

A 的重点证据：

- [解析入口](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/services/parsing/loader.py)、[切片](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/splitter.py)、[BGE Provider](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/embedder.py)。
- [旧覆盖实现 create_document](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/services/doc_service.py#L72)：旧文档 ready，随后以同名且内容过短的新文件 overwrite，结果新文档 rejected、旧文档查询 HTTP 404。仅隔离样例，不是用户资料。
- [打标脚本](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/scripts/auto_label.py#L85)、[原文档响应模型](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/api/schemas.py)。

注意：当前 C 已有带备份的文件替换流程。上面的旧覆盖问题针对 GitHub 原版接口，不要求重复实现 C 已验收的替换功能；正式联调前需确认旧入口不会绕过新流程。

## 学生 B

| 原始职责 | 结论 | 已有实现与实际边界 |
|---|---|---|
| RAG Pipeline、混合召回、图片→OCR/公式→检索→解答 | 文本 RAG 主要完成，图片问答链路缺失 | retriever/hybrid/pipeline 实现向量+BM25、RRF、重排、拒答与生成。ChatRequest 只接收 question、kb_ids、conversation_id、stream，未找到图片提问参数或调用 OCR 的问答编排。A 的扫描件入库能力和 C 的上传图片交互不等于 B 已完成图片提问链路。原要求指定 LangChain，实际为自写 Pipeline，依赖及调用中无 LangChain；功能可替代，但技术栈是否允许替代需作为偏差记录。 |
| 模型接口：流式、重试、Token、分步/引用/置信度/LaTeX | 主要完成，网络重试不完整 | llm.py 已有真实 DeepSeek HTTP 客户端、流式、usage/估算和部分重试；prompt.py 约束分步与 LaTeX，done 返回 confidence。连接失败没有转成可重试异常，实测一次即退出。置信度是检索/重排分数，不是已校准的答案正确概率。 |
| 常见题型 Prompt 与 Few-shot | 部分完成 | 有方程、函数、证明三套样例与关键词选择；函数样例主要为单调性，未见函数极值和数列证明的专属样例。可算已有基础，但未覆盖原分工举出的全部典型场景。 |
| 多轮记忆与追问澄清 | 基础能力已实现，需真实追问验收 | context.py 读取最近三轮、按字符预算保留，Prompt 带历史；自写实现，无 ConversationBufferMemory。检索仍只用本轮 question，不做上下文改写，像“第二步为什么”能否正确找回资料需实测，不能仅凭历史入库就判全部可靠。 |
| 相似问题与参考资料推荐 | 未实现相似问题推荐 | 有检索引用片段，但没有相关问题生成/推荐接口、事件字段或编排步骤。已有引用不能代替“相似问题推荐”。 |
| 数学测试集、Recall@K、解答准确率和迭代 | 检索评估已交付，回答正确率未闭合 | 有 80 题反推集、18 题人工改写集、三档消融、阈值标定、生成延迟/引用/拒答工具。历史文档记录改写集 Recall@5=0.6111，不能只展示反推集100%。数学回答正确率仍需人工标注/抽检，仓库未见完成的逐题正确性结果。 |

B 的重点证据：

- [问答请求结构](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/api/schemas.py)、[文本 RAG 编排](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/pipeline.py)、[检索器](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/retriever.py#L158)。
- [DeepSeek 客户端](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/llm.py#L54)：隔离模拟 httpx.ConnectError，配置 llm_max_retries=2，实际调用次数1，直接抛出 ConnectError。未发网络请求。
- [Prompt](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/prompt.py)、[上下文](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/backend/app/rag/context.py)、[评估脚本](https://github.com/sirlu666/RAG/blob/a43d959be6aad38767e8b3a737f3bb648df3beb6/scripts/eval.py)。
- B 文档虽将 OCR/拍照/相似题排除，仍应对照用户原始分工将其标为未交付，不按旧文档自行豁免。

## 已交付资产、本机缺项与联调边界

| 项目 | GitHub 已有 | 当前电脑缺什么 |
|---|---|---|
| 语料 | knowledge/raw 下171篇 Markdown | 未导入当前可登录账号知识库，当前网页只有用户上传的4份文档 |
| 向量 | math_chunks_bge-m3.json.gz：实际2519条、1024维、对应171个doc_id | 不是可直接连接的在线服务；还需匹配的关系库记录/ID、可登录账号归属，以及查询向量模型。不能单独导入快照就声称资料可引用 |
| 标签 | 有生成脚本、数据库字段、重建索引合并标签代码 | 分发向量快照中0条带knowledge_points，当前demo数据库也0份标签；需实际标签产物，不重新让C负责打标 |
| 模型权重 | 加载代码、依赖、模型名称和下载说明 | 本机BGE向量/重排权重未就位；大模型权重不随DeepSeek API客户端分发，属正常交付方式 |
| DeepSeek | 完整HTTP调用入口及历史真实调用记录 | 本机无密钥，当前mock=true；可由B提供可用服务，或由团队在本机配置调用凭据。不能据此判B没写模型接口，也不能把本机当前模拟回答说成真实回答 |

## 应补工作的归属和顺序

1. A：闭合标签交付与读取约定，适配配置路径及解析后正文；核对旧覆盖/重建失败后的恢复行为。C 不替 A 开发标签生成。
2. B：补图片提问编排、相似问题推荐和连接错误重试；核对标签用于检索路由的要求；补典型题型样例和逐题数学正确性验收。B 的 LangChain/记忆组件替代方案需在交付说明中说明。
3. 团队交付与 C 联调：明确由B提供运行服务还是本机运行源码。再交接模型/数据/调用凭据，验证真实资料处理、问答、引用和追问。钥匙和权重不应作为C算法工作。
4. 真实链路及必要功能验收后，再进行本机 Nginx 交付。此审查不启动部署、不下载模型、不调用付费服务。

本报告没有把所有“部分完成”都当成必须重写；需区分原始必需功能、实现替代、实际缺陷与尚缺验收证据。
