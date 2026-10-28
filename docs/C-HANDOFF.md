> 最新：按用户要求优先整理前端，主页仅留知识库与问答，账号/服务改为侧栏工作空间入口，资料管理改为可关闭抽屉，桌面双栏直接对话。构建及定向浏览器检查通过，新增模型调用0，等待用户体验反馈。见[C-COMPACT-WORKSPACE.md](C-COMPACT-WORKSPACE.md)。图片问答入口待此项收尾后继续。

> 最新收尾：用户已确认真实问答、追问、拒答、刷新恢复、资料上传/替换/删除后的检索通过；双账号权限复用自动化，不再重复人工验收。当前剩余任务及顺序见[C-CURRENT-STATUS.md](C-CURRENT-STATUS.md)，下一小任务是问答区图片识别入口对接。额度只读快照74/100次、费用保守上界0.4803645美元；本次未测试、未调用模型或重启服务。下方旧pending和额度为历史。

> 最新：已修复分界点追问漏识别，原会话复验相关度0.9798，阈值仍0.62，29项相关回归通过。累计73/100次、费用保守上界0.4742070美元；网页仍在localhost:5174，原失败记录保留。见[C-BOUNDARY-FOLLOWUP-FIX-2026-10-28.md](C-BOUNDARY-FOLLOWUP-FIX-2026-10-28.md)。下方70次等是此前快照。

> **2026-10-28 最新：独立真实联调已运行 http://localhost:5174/，后端8002。** 已完成4次真实问答/追问、引用和历史核对，累计70/100次、费用保守上界0.4497072美元/1美元；预算持久化并在请求前保护。当前仅等待用户浏览器复核。见[真实联调说明](C-BROWSER-INTEGRATION-2026-10-28.md)。下方旧授权、等待联调、未启动及旧验收状态为历史。原C工作区和.tmp/c-demo保留，未推送或部署。

> **2026-10-28 最新：C已在隔离分支codex/c-main-integration中整合main@d9c7013。** 原工作区124份成果已保存到快照f1c687f且指纹未变；本轮后端370项、前端37项及构建通过。仅本地整合，未推送、未切换网页、未部署或新增模型调用。下一步准备独立网页联调，详见[C整合交接](C-MAIN-INTEGRATION-2026-10-28.md)。下方“未合并/等待A/B/旧额度及旧失败”属于历史，以本条为最新状态；PR #5已合并，累计仍66/70次、费用保守上界0.4175985美元。

> 2026-10-28：B最终修复合并前检查完成。隔离分支codex/b-final-fixes，PR #5；后端227项、C前端兼容12项通过，17项AI复核/3项自动检查/两类图片问答通过。累计66/70次、费用保守上界0.4175985美元；已停止调用和临时验证服务。未合并、未部署、未修改C前端。最终证据位于隔离worktree的eval/validation/2026-10-28-premerge；原C未提交成果及.tmp/c-demo保留。

# MathRAG 项目交接说明

**2026-10-28 本轮已收尾，整体验收未通过，不部署。** 独立分支 `codex/b-final-fixes` 的RRF排序、追问检索、示例/真实引用隔离、格式化拒答与流式截断错误处理已修复，完整回归219 passed。20题记录齐备，3项自动拒答全部通过；17项AI复核为10通过、2保留、5未通过，详见 [最终AI复核](../.tmp/b-final-fixes/eval/validation/2026-10-28-final/AI-REVIEW.md) 与 [交付状态](../.tmp/b-final-fixes/docs/B-FINAL-FIXES.md)。累计保守计入40次调用（含昨日在途预留），费用预留上界0.2066091美元；次数额度已到，临时服务已停止，不能重置额度或继续付费复验。PR #5 保持草稿，未合并或部署；原C工作区及`.tmp/c-demo`保留。下方运行中/暂停条目均为历史，以本条为准。

**2026-10-28 用户已要求继续，并批准累计最多40次模型调用，总费用仍最多0.30美元、每次2048输出Token，不重试、不增加模型推荐调用。** 当前恢复记录见 [B恢复记录](../.tmp/b-final-fixes/docs/B-FINAL-RESUME-2026-10-28.md)。新增示例/真实引用编号隔离及跨运行累计预算检查，完整回归215 passed。昨日19次加本日三题复验3次，已累计22次、保守预留0.1117500美元；run-08正以低强度思考模式刷新20题，最多再18次，不重复图片OCR验收。原工作区、数据及草稿PR均保留；未合并或部署。下方昨日暂停说明为历史，不能重置额度。

**2026-10-27 用户要求暂停项目，已停止 B 最终修复的临时验证进程，不自动继续。** 保存于独立 worktree `.tmp/b-final-fixes`、分支 `codex/b-final-fixes`；完整恢复入口见 [B 暂停检查点](../.tmp/b-final-fixes/docs/B-FINAL-PAUSE-2026-10-27.md)。代码最新完整回归 207 passed。真实调用累计保守计入 19 次，预留费用上界 0.0967605 美元（含暂停时在途调用），原授权 26 次最多还剩 7 次，恢复时不能重置。两条追问及两类匹配语料图片已有结果，但完整20题、17项AI复核尚未完成，部分引用/数学推导仍有问题。用户已要求由agent自行判定数学正确性，结论须标记AI复核，不伪填人工验收。PR #5 为草稿，未合并或部署；原C分支和 `.tmp/c-demo` 保留。更早条目中缺模型/未调用等状态已由此条更新，不能重复下载或重新启动验证。

2026-10-27 B第二轮验收：最新B分支268fb3e4dc3eb040eaed0a46f67872bd7942463a，远端main已是01bb637包含本轮B成果，但C本机未合并。独立副本.tmp/b-reacceptance-5meq_cz6，159项测试通过；上轮F1～F4独立复现通过，D2开关删除、D3模型revision/SHA已补并核对官方元数据。新增F5：无标签时apply_tag_boost仍按relevance排序覆盖RRF，影响无重排/失败回退。CSV20条答案已填，8条拒答、3条auto行为判定，17数学项无人判定；h011/h012真实追问仍以0.31/0.32低于0.62拒答，真实图题链路证据尚缺。报告docs/B-REACCEPTANCE-2026-10-27.md，旧4缺陷代码闭合但完整验收未通过。B文档提议延后验收仅为第三方建议，不改变用户节奏；未修改实现、付费调用、上传报告或恢复C工作。

2026-10-27：用户授权将B整改报告同步GitHub供B接收。仅上传docs/B-ACCEPTANCE-2026-10-27.md，分支codex/b-acceptance-report，提交90db3306689745bb1bd9962a1c86c468719a713e；远端内容已与本地核对。报告PR#4：https://github.com/sirlu666/RAG/pull/4 ，目标codex/b-integration-delivery，未自动合并。使用独立暂存区，未修改B实现或C代码/数据，等待B整改后复验。

2026-10-27 B最新交付验收：用户授权验收，远端codex/b-integration-delivery=ffda8cf3e079a724a3c84962e2081b1cc9a0ad5e，已包含A的8cabbfe修复。仅fetch并导出.tmp/b-delivery-review-op_q_6m6，148项后端测试通过（OCR_FORMULA=none），未合并或改动C。额外复现：标签加分把0.61提至0.63越过0.62拒答线，BM25证据0.5反降0.02；非流式模型异常HTTP200/code0/空答案并正常存空assistant；推荐异常破坏主回答done，declined仍给推荐；复核工具追问不带history。20条复核答案与人工判定均空，真实文本/图题证据仍待交接；RELATED_QUESTIONS_LLM开关有声明无实际读取。报告docs/B-ACCEPTANCE-2026-10-27.md，结论未通过，未自动修复/上传或通知B；等待用户后续指示，C联调不恢复。

2026-10-26：用户明确授权合并PR#3，已成功合入远端codex/a-integration-delivery，合并提交5715b49add97df4c0560ba08c9ce320bd3a200fb，GitHub确认merged=true。合并前核对head=8cabbfe、base=9d0c0a1、mergeable=true；无已注册commit status，本地已有119项通过记录。连接器写入403后使用本机已有Git凭据完成，未输出或保存凭据。只合并到A交付分支，未合入main/C、未切换本机服务。真实标签包等材料仍待交接，继续按约定等待A/B完整交付。

2026-10-26 用户授权直接修复A验收问题并上传：独立worktree .tmp/a-acceptance-fixes、分支codex/a-acceptance-fixes，基于A的9d0c0a1，提交8cabbfea17de5b7d739d627a5ec9dcbb3af768a7。5项缺陷已修（精确向量删除、同内容覆盖、重建失败恢复、标签CAS、VLM完整正文），显式快照导入增加关系ID/正文/归属校验，补模型revision/根目录命令与171语料及快照SHA清单。原95+新增24=119项测试通过，Local/Chroma均覆盖，测试关闭可选公式加载，无付费调用。已推送，PR#3 https://github.com/sirlu666/RAG/pull/3 目标codex/a-integration-delivery，尚未合并；main/A原分支未直接更新。C原工作树/默认暂存区/资料/服务未变。真实标签包与旧快照配套库/原权重revision仍待A确认，不能标A整体通过。B和C联调继续等待完整交付。

2026-10-26 A最新交付验收：用户明确授权验收，不代表恢复C开发。远端A分支codex/a-integration-delivery=9d0c0a1665213eae4a402ed110de3a1c29c390c5，main仍a43d959。已fetch但未合并，独立副本.tmp/a-delivery-review-th44_689中95项测试通过（OCR_FORMULA=none，避免可选模型加载）。额外复现5项阻塞：重建旧向量删错ID导致孤儿；同内容覆盖使旧文档superseded隐藏；重建失败旧文档不可检索/预览；标签旧任务写回新版本；VLM题目text丢独立公式。A-01另有快照ID匹配说明、模型下载cwd/revision和真实标签包交接问题。报告docs/A-ACCEPTANCE-2026-10-26.md可转给A，当前判未通过；未修算法、未触碰C数据、未自动发送或上传报告，继续等待双方全部完成。

2026-10-26：用户明确授权上传A/B需求文档。已仅将 docs/A-AGENT-REQUIREMENTS.md、docs/B-AGENT-REQUIREMENTS.md 上传到远端 codex/ab-agent-requirements，提交471b742d304bbc8c6bbc4331268d283e258d9c61，PR：https://github.com/sirlu666/RAG/pull/1（未合并）。两份远端内容已与本地逐一核对一致；通过独立暂存区提交，C分支仍为codex/c-platform，未包含其他代码、配置或数据。连接器写入403后使用本机已有Git凭据完成上传与PR；未保存/输出凭据。按用户约束，继续等待A/B全部完成后再开展C开发联调。

2026-10-26 最新用户约束（优先于下方历史安排）：A、B 工作全部完成前，C 不继续工作。已修改 A-AGENT-REQUIREMENTS.md 与 B-AGENT-REQUIREMENTS.md，删除 P0 单独先交付和提前启动 C 联调的要求，改为各自全部完成后完整交付，C 等双方均完成后再接续。同步交接单和当前计划。A/B 内部可拆分实现/提交并相互协调，但不要求 C 提前配合；存在缺项如实记未完成。此次只修改文档，完成后停止项目推进，等待双方完整交付。

2026-10-26：用户要求分别给A/B撰写便于coding agent执行的需求文档，已完成 docs/A-AGENT-REQUIREMENTS.md 与 docs/B-AGENT-REQUIREMENTS.md，均可独立转发。包含基线/已有实现/责任边界/P0现成成果交接/P1缺陷/P2原分工补齐、接口兼容、隔离验证、真实证据及PR交付要求。标明A/B不覆盖C未提交成果，图片识别A适配B编排，推荐优先追加done字段不引入C无法识别的唯一SSE事件；不强制框架重写、不默认付费调用。仅写本地文档，未通知队友或提交推送。

2026-10-26：用户在A/B审查后要求下一步。已整理可执行交接单C-AB-NEXT-TASKS.md：默认沿用本机统一后端，先接收A的模型/一致数据/真实标签，以及B的DeepSeek调用条件和重排模型/参数，开展真实文本联调；缺陷、图片问答和推荐等由A/B后续补齐，C只做平台集成。未要求另起A/B服务，未默认让C自行购置密钥。没有向队友发送消息、修改算法、下载或调用模型。当前待第一批运行材料交接；下一次继续时先检查是否有材料回复，不重复审查已确认版本/模型。

2026-10-26 A/B GitHub 审查完成：用户要求先核对A/B原始分工是否完成。已通过GitHub插件及ls-remote确认远端main=a43d959，与本地基线一致；隔离导出原提交，80项原后端测试通过（mock，不代表真实数学质量）。报告见C-AB-REVIEW.md。A主要解析/切片/BGE/Chroma已交付，自动标签有离线脚本但消费闭环不足；B文本RAG/DeepSeek/基础记忆/检索评估已有，图片提问链路、相似问题推荐缺实现，数学正确率验收未完成。隔离复现A旧overwrite先删旧再失败导致旧文档404，以及B连接错误不按配置重试。向量快照2519条/1024维/171文档，不含知识标签；未将本地C新增功能算作A/B成果。未改算法、未用用户资料复现、未下载或调用模型。先厘清A/B补项及运行服务交付方式，再真实联调与部署。

2026-10-26：用户确认“是最新成果；使用deepseek”，版本/模型问题已解决。已准备独立真实联调入口 scripts/start-c-integration.py 和本机忽略文件 .env.c-integration（密钥为空），使用 .tmp/c-integration 隔离原 demo；固定 local BGE-M3/1024维+Chroma+local rerank+mock=false，保留 B 的阈值0.62等待语料复核。预检、配置隔离断言、Git忽略及差异检查通过；当前缺DeepSeek密钥和两个BGE模型，未下载/调用模型/切换服务。下一小步由用户本机填写密钥，不发聊天；随后准备已有A/B模型和真实语料，导入时归属可登录账号。见 C-AB-INTEGRATION.md。

2026-10-26：已执行 A/B 真实联调前置核对，见 C-AB-INTEGRATION.md。当前 HEAD a43d959，接口已调用仓库内 A/B 代码，但在线仍为 dev/local/mock，4 文档11切片无标签。无 .env，无已配置模型密钥，无 BGE 向量/重排模型，data/app.db 不存在；已有依赖不代表模型就绪。历史 A/B 验收记录不能代替本机验证。尚需确认 A/B 最新交付是否就是本仓库，以及最终模型为当前实现 DeepSeek 还是原分工 qwen。未调用模型、未下载或改动 demo 数据，暂不部署。

2026-10-26 执行顺序纠正：用户质疑 A/B 尚未真实接通就开始部署。核对现有启动脚本仍使用 EMBED_PROVIDER=dev、VECTOR_BACKEND=local、MOCK_LLM=true；前端已调用仓库内 A 的文档接口和 B 的问答接口，但目前运行的是开发向量与模拟回答，不能记为真实 A/B 联调完成。自行上传是个人知识库正常入口，仍须验证 A 的正式解析/向量/标签产物与 B 的真实模型问答链路。下一步优先核对 A/B 当前交付版本、接口契约及运行配置，再进行真实数据与模型联调；本机 Nginx 集成交付排在真实联调验收之后，暂不执行部署。不替 A 生成标签、不替 B 开发模型封装，不改动现有 demo 数据。

2026-10-26：用户在字体验收步骤后回复“继续下一步”，按约定记为验收通过。本轮完成电脑端页面文案复核：移除首页过时的“接下来完成”“本次练习”，替换为现有功能使用指南；个人空间提示改为账号隔离说明。保留真实的模拟模式标识，不宣称 A/B 真实问答已验收。仅静态文案修改，经 Vue 模板编译及差异检查通过；电脑端外观由用户复核，不扩展手机适配。剩余为 A/B 真实接口与标签数据联调、本机 Nginx 交付及最终验收。

2026-10-26：用户在主题验收步骤后要求“进入字体设置”，未报告异常，按约定进入下一小任务。已实现默认/宋体/楷体的预览、保存和账号恢复，新增 user_fonts 表避免改动原有偏好表。34 项相关后端测试及前端构建通过，后端已重启；字体等待用户浏览器验收，见 C-PROFILE-FONT.md。之后进行电脑端界面复核；继续只做 C、本机交付，无手机适配。

2026-10-26：头像已由用户明确验收通过。本轮已实现默认/浅色/深色主题切换与账号持久化，新增 user_appearance 表保留原账号和资料；28 项相关后端测试及前端构建通过，后端已重启。主题等待浏览器验收，步骤见 C-PROFILE-THEME.md；下一小任务为字体设置。继续只做学生 C，电脑端、本机部署。

2026-10-26：用户明确反馈“头像验收成功”，头像设置记为浏览器验收通过。下一小任务为默认/浅色/深色主题切换与账号偏好保存，字体设置后续单独推进。继续只做 C 的平台工作；标签由 A 生成，C 负责展示筛选及接口联调。

2026-10-26 分工纠正（以此为准）：用户明确学生 A 负责利用大模型生成知识点、题型、难度标签，供 B 检索路由与 C 前端使用。用户为学生 C，仅负责读取 A 的标签、展示与分类筛选。撤回上一轮“由 C 接入模型生成标签”的建议；C 不负责模型打标，也不增加本机规则标注作为替代。标签来源不足时等待 A 提供真实标注数据，再进行联调，不向用户资料注入假标签。本轮只检查过模型配置，未新增生成接口、未配置密钥或调用模型。

2026-10-26 最新：用户明确要求做自动知识标签展示与筛选增强项。已有标签的展示与名称/手动分类/知识点/题型/难度/有无标签组合筛选已实现，20 项相关后端、4 项前端及构建通过，待浏览器验收，见 C-AUTO-TAGS.md。只读检查当前 demo 4 份资料均未标注，本次未注入假标签、未调用模型生成标签；正向标签显示已在隔离测试验证，真实标签浏览器场景待相应数据。头像仍待用户验收，主题/字体待实施。

2026-10-26 最新：用户在昵称验收后要求下一步，昵称记为已验收。头像上传/预览/保存/恢复默认已实现，等待浏览器验收，见 C-PROFILE-AVATAR.md。最终 32 项相关后端、9 项前端接口及构建通过；头像为仅当前账号可读的 256×256 PNG，存于新增 user_avatars 表，不改变用户资料归属。后续继续主题/字体设置，保持一次一个小任务、仅电脑端本机交付。

2026-10-26 用户确认“我自己的截图也识别成功了，这部分结束，进入下一部分”。按用户验收反馈关闭本轮公式识别任务，先前自截图片错误不再列为待排查；不据此宣称所有公式或手写内容均可靠。 个人设置第一个小任务“昵称修改与持久化”已实现，25 项相关后端及构建通过，等待浏览器验收，见 C-PROFILE-NICKNAME.md。下一步按用户反馈推进头像等设置，仍仅电脑端与本机交付。

2026-10-26 用户浏览器验收：用户反馈“你给的图片识别成功了”，截图显示正文中已保存 x^{2}-3x+2=0。提供的清晰印刷示例的识别与保存验收通过；正文预览仍按原始文本显示 LaTeX，不代表公式渲染验收。用户自截公式图此前输出错误，尚未收到该原图，问题仍待复现；不将示例成功扩大为通用公式准确率通过。

2026-10-26 最新接续：已实现“识别公式截图 → LaTeX 建议 → 预览 → 人工追加/保存”的第一个公式识别小任务，等待用户浏览器验收，见 C-FORMULA-OCR.md。采用独立 .venv-formula + 本地 ONNX，真实印刷示例及隔离链路通过；最终 43 项相关后端、12 项前端及构建通过。当前仅电脑端交付，手机适配/实拍不再要求。复杂公式与广泛准确率尚未验收，不将整个公式专项记为全部完成。后端已重启加载新接口，未提交、推送或远程部署。

2026-10-26 范围调整：用户明确“不需要进行手机适配”。后续以电脑端为交付与验收范围，不再将手机布局适配、手机实拍或局域网访问验收作为必须任务；保留已实现的图片选择/拍照入口代码，不主动删除既有成果。本次新增的 WLAN 前端已停止，电脑端 127.0.0.1 前后端保留。下一功能为公式专项识别，之后继续个人设置、自动标签、电脑端联调、真实模型与正式检索及本机发布。

2026-10-26 最新接续：用户在电脑拍照入口验收后回复“继续”，已配置单独 WLAN 前端 http://10.34.90.55:5173/，后端仍仅本机监听；手机连通与真实拍照待验收。见 C-LAN-CAMERA.md。修复局域网 HTTP 的 randomUUID 兼容与代理 Host；构建及 5 项相关前端测试通过，未改变防火墙或网络类别。

2026-10-26 最新：用户在识别文字校对验收步骤后回复“继续”，按约定推进；拍照识题入口已实现，待电脑浏览器验收，见 C-CAMERA-ENTRY.md。当前仍仅监听 127.0.0.1，手机实拍与局域网访问配置尚未验收。前端构建及 4 项原上传测试通过。

## 2026-10-26 接续更新（优先于下方历史状态）

用户已反馈中文高亮复核、真实短图 OCR 上传/正文/引用/原图及正常图片替换通过；在过短替换验收步骤后要求继续，按当前合作偏好进入下一任务，未另行提供具体错误原文。图片识别文字校对已实现，等待浏览器验收，见 C-OCR-CORRECTION.md。拍照入口与公式专项识别仍未实施。本轮相关后端最终 33 项、前端构建通过；没有提交、推送或远程部署。技能 minimal-change 已更名为 chat-optimization（聊天优化），保持一次一个小任务，减少重复确认。

交接日期：2026-10-25（Asia/Shanghai）。用途：在同一台 Windows 电脑的新 Codex 聊天中接续开发。以当前本地文件、用户验收反馈和运行时检查为准。

## 1. 新聊天先读这段

用户是编程新手，负责三人项目中的学生 C（平台、前端和系统集成）。学生 A/B 的数学知识工程和 RAG 后端已经在仓库中。本聊天在其基础上补齐 C 功能，采用“实现一个小任务 → 给出浏览器验收步骤 → 用户反馈成功 → 下一任务”的方式，同时学习 Codex。

**最新状态：引用/原文件功能已有用户成功反馈，静态图片 OCR 已实现但仍待真实浏览器验收。本轮审查发现的短图片门槛/切片问题、中文高亮问题已修复，相关测试与构建通过，后端已重启；修复后的浏览器效果尚未重新验收。新聊天先读 C-REVIEW-FIXES.md。**

不要重新询问项目选题、技术栈、时间安排或已确认的权限方案，也不要从头克隆或重建项目。先读取本文件，检查本地 Git 状态和服务，再继续下一步。

**全部 C 开发成果主要保留在当前工作区，尚未提交或推送。不能用 GitHub 当前分支内容替代本地文件。**

## 2. 项目位置与 Git 状态

| 项目 | 交接时的值 |
|---|---|
| Codex 工作区 | `D:\我的文档\文档\ChatGPT\codex学习` |
| 实际应用仓库 | `D:\我的文档\文档\ChatGPT\codex学习\RAG` |
| 课程记录目录 | `D:\我的文档\文档\ChatGPT\codex学习\codex-course` |
| GitHub remote | https://github.com/sirlu666/RAG.git |
| 当前开发分支 | `codex/c-platform` |
| 当前 HEAD | `a43d959be6aad38767e8b3a737f3bb648df3beb6` |
| 本地改动 | 大量已修改和未跟踪文件，包含整个 frontend、新增账号/知识库/历史/公共接口、测试和课程文档 |
| 提交/推送情况 | 本轮未创建新的 Git 提交，未推送 |

外层工作区也存在 Git 仓库。操作应用代码时先进入 RAG，避免在外层仓库误操作、误暂存嵌套仓库。

安全检查命令（PowerShell，只读）：

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG'
git branch --show-current
git status --short
git diff --check
```

不要执行 reset --hard、clean、重新克隆覆盖、强制 checkout、自动 stash/pop 或直接拉取后覆盖本地成果。先审查现有改动；不要擅自提交 .env、数据、密码或令牌。

## 3. 已确认的合作约定

- 使用中文，面向新手解释。每课只聚焦一个可独立验收的小任务。
- Agent 直接实现已授权功能，不反复询问是否继续或要求批准常规实现选择。
- 每次交付给出操作位置、步骤、预期、验证、常见错误与恢复方法。用户常用“成功了”“验收成功”“预期实现”确认完成。
- 完成全部 C 功能，允许补充必要后端。不能只做界面、用假数据或仅隐藏按钮冒充权限实现。
- 原六周、每天两小时安排已经取消。当前五天路线是任务分组，不再按原工时限制执行，也不允许为赶五天而跳过功能。
- 服务器仍在备案，本阶段只要求本机交付，不部署阿里云。
- 流式问答采用已有 SSE，用户已接受；不需要额外实现 WebSocket。
- 不自动发送消息、推送 GitHub 或创建定时提醒。额外付费 API、模型服务或域名先说明用途与费用。
- 保留现有文件和真实练习数据。删除、替换、公开通过明确的应用确认框由用户操作；Agent 不自动删除/替换/公开用户资料。
- 不重装软件、覆盖 .env、修改全局执行策略或自动重置数据。确需破坏性操作时先说明影响、备份和恢复并取得明确确认。
- 不把密码、Cookie、CSRF token、私钥、API key 写入聊天、截图、文档或日志输出。
- 做局部改动，运行相关且有意义的检查；不要每次默认全量测试、升级依赖或重构全项目。
- 此交接不要求新建聊天、调用其他 Agent 或任何定时任务；用户自行迁移聊天即可。

## 4. 产品范围与已验收成果

项目是“基于 RAG 与大模型的数学问题解答系统”。前端使用 Vue 3 + Element Plus，后端复用 A/B 的 FastAPI、文档 ETL、向量检索和 RAG。

| 模块 | 已实现并由用户验收的行为 |
|---|---|
| 本机运行 | Python 虚拟环境、前后端服务、健康检查、Swagger |
| 账号 | 注册、登录、退出、刷新恢复登录、账号隔离、CSRF |
| 个人知识库 | 创建、改名、选择、空库确认删除；非空库拒绝直接删除 |
| 上传 | PDF/DOCX/MD/TXT/PNG/JPG/JPEG，拖拽、多选、串行批量上传、每文件传输进度和错误隔离；图片 OCR 已实现，待验收 |
| 解析 | 独立状态轮询，区分传输 100% 与解析 ready，失败提示、暂停/恢复查询；静态图片使用本地 RapidOCR |
| 文档查看 | 分页显示解析后的正文片段，标注知识概念/例题等类型；PDF/图片可 inline 查看原文件，DOCX/MD/TXT 下载 |
| 文档删除 | 文件名确认，清理文档、片段、任务、向量和该文档版本备份；阻止处理中删除 |
| 正文编辑 | UTF-8 TXT/MD 原始正文编辑，20 万字符限制、版本冲突检查、备份、重新切片/向量化、普通故障回退 |
| 改名分类 | 保留扩展名、同库重名拒绝，手动分类与 A 自动标签分开保存，名称/分类组合筛选 |
| 文件替换 | 同格式 PDF/DOCX/MD/TXT/PNG/JPG/JPEG 新版替换，确认后更新，保留文档编号、展示名称、手动分类、所属库；失败保留旧版 |
| 问答 | SSE 展示、停止接收、部分回答/失败/无依据状态，Markdown、LaTeX/MathJax |
| 引用 | 参考片段展开、按 chunk_id 定位解析正文、提问词安全高亮、登录后的 PDF/图片原文件内联查看和 DOCX/MD/TXT 下载；用户已反馈实现成功 |
| 对话历史 | 登录用户对话列表、打开旧对话、继续追问、改名、确认删除、游标读取更早消息 |
| 公共知识库 | 所有者确认公开/撤销，现有资料默认私有；公开范围包含整库当前及后续上传资料 |
| 游客 | 只问已公开库，服务器不保存历史，不返回 citation 事件或引用正文结构，单次问题，每 IP 每分钟 10 次 |
| 登录公共阅读 | 登录用户可问公开库、保存自己的对话、查看公共引用正文；其他账号仍不能管理他人资料 |

用户最新反馈：引用关键词高亮与查看原文件已实现。此前公共知识库、游客问答和权限功能也已验收成功。

## 5. 尚未完成的工作

按已约定顺序继续，每项可再拆成更小任务：

1. **当前待验收：审查修复的中文高亮，以及 PNG/JPG/JPEG 图片上传、短题切片与新版本替换。** 先按 C-REVIEW-FIXES.md 复核，再按 C-IMAGE-OCR.md 验收实际 OCR、正文、问答引用与原图。配置使用 RapidOCR，真实识别质量仍待验收；尚不覆盖公式专项识别、拍照入口或 OCR 校对。
2. 图片拍照入口、公式专项识别、识别结果校对后接入检索与问答。扫描 PDF OCR 或当前静态图片纯文字 OCR 都不能算这些后续工作已完成。
3. 个人资料：昵称、头像；主题（默认/浅色/深色）、字体与设置持久化。
4. 全面响应式与交互联调。现有组件有局部窄屏样式，但未完成全功能手机验收。
5. 接入真实模型、正式 Embedding/向量检索，验证数学解答、引用质量和多轮效果。不能用 mock 答案验收正确性。
6. 本机 Nginx 集成、生产打包访问、启动说明、日志、版本发布与回滚、最终全功能验收。
7. 穿插完成 Codex 学习实际练习：Git 检查点与恢复、项目 Skill、限定范围 MCP、手动自动检查、多 Agent 分工与整合。尚无这些全部完成的证据；不创建定时提醒。

资料标签还有一项需补齐：目前界面筛选的是手动分类；A 生成的 knowledge_points、question_types、difficulty 标签仍未完整接入前端展示和筛选。不要把手动分类当作自动标签展示已经完成。

原项目希望使用 qwen；当前 A/B 代码使用 deepseek_* 配置名及 LlmClient。未来接入 qwen 或其他兼容服务前需要核对实际接口与配置，不能仅凭配置字段名认定已经支持或已切换。

## 6. 运行环境和启动

既有环境记录：Windows、PowerShell、Python 3.12.4（仓库 .venv）、Node v24.22.0、npm.cmd 11.19.1、Git 2.56、VS Code。系统默认 python 可能仍为 3.9，不能用默认 python 代替项目解释器。

### 后端

先确认 8000 端口是否已有当前项目服务。没有运行时，在 RAG 根目录执行：

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\start-c-demo.ps1
```

执行策略只影响当前 PowerShell；无需管理员权限或修改全局。使用脚本不要漏掉 RemoteSigned 参数。服务运行时会占用这个终端，需要其他命令时打开新终端；Ctrl+C 正常停止。

启动脚本使用项目 `.venv\Scripts\python.exe -X utf8`，设置仅限进程的 demo 环境，退出时恢复，不修改 .env。

### 前端

另一个终端：

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend'
npm.cmd run dev
```

依赖已经安装，不要无理由重跑 npm install。PowerShell 中使用 npm.cmd，避免 npm.ps1 执行策略问题。

| 地址 | 用途 |
|---|---|
| http://127.0.0.1:5173/ | 前端 |
| http://127.0.0.1:8000/docs | 后端 Swagger |
| http://127.0.0.1:8000/openapi.json | 当前接口契约 |
| http://127.0.0.1:5173/api/health | 经 Vite 代理的健康检查 |

Vite 固定 5173 且 strictPort=true，`/api` 代理到 8000。npm preview 在 4173，没有开发代理，不能据此认定后端功能可用。正式本机 Nginx 尚未配置。

最新收尾端口快照：8000 PID 11320；5173 PID 29956。这些 PID 随重启变化，**不能作为新聊天杀进程的依据**。旧聊天的工具 session_id 也不应在新聊天直接复用。本轮修复后端已重启加载，代理健康检查 app=up。

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

若端口已占用，先访问页面/健康检查并核对进程来源，复用现有服务，不重复启动或终止未知进程。后端代码改变后需要正常重启，脚本未启用自动 reload；前端 Vite 支持热更新。

## 7. 数据位置与当前模型模式

当前启动脚本强制：

```text
APP_ENV=dev
MOCK_LLM=true
EMBED_PROVIDER=dev
EMBED_DIM=256
VECTOR_BACKEND=local
RERANK_PROVIDER=none
RELEVANCE_THRESHOLD=0.05
```

数据绝对路径：

```text
D:\我的文档\文档\ChatGPT\codex学习\RAG\.tmp\c-demo\app.db
D:\我的文档\文档\ChatGPT\codex学习\RAG\.tmp\c-demo\uploads
D:\我的文档\文档\ChatGPT\codex学习\RAG\.tmp\c-demo\vectors
D:\我的文档\文档\ChatGPT\codex学习\RAG\.tmp\c-demo\uploads\.versions
```

这些路径虽然在 .tmp 下，却包含用户真实操作形成的账号、知识库、上传文件和历史，**不是可以随意清空的缓存**。

SQLite、上传文件、向量及旧版本备份共同构成数据状态，不能只重建其中一个。原生产/仓库 data 路径保持独立，不要把 demo 数据覆盖进去。

dev Embedding 是哈希向量，mock LLM 常对不同问题返回同一套无关公式。这是已知演示行为，界面有明确标签，不是数学能力已完成。未下载完整模型，也未在本轮配置真实付费模型。启用真实模型前还需调整 demo 启动脚本的强制覆盖方式，不能只改 .env 就宣称已切换。

旧版备份形式：`.versions/<doc_id>/<随机版本目录>/`，保留旧原文件和含旧片段、向量的 index.json。删除文档会按用户确认框一并清理其备份。更新使用进程内锁和故障补偿，不是跨 SQLite、文件与向量库的分布式事务；强制终止、断电或持续磁盘故障可能仍需人工恢复。

## 8. 前端结构

仓库前端目录：`D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend`。

| 文件（均在此前端目录内） | 职责 |
|---|---|
| src/App.vue | 页面外壳、健康检查、静态课程提示；部分静态“本次练习/下一步”文案可能落后于真实进度 |
| src/components/AccountPanel.vue | 登录/注册/恢复/退出，切换账号时清理子组件，承载个人及公共空间 |
| src/components/KnowledgeBasePanel.vue | 所有者知识库管理、公开/撤销确认、选择私有空间 |
| src/components/PublicKnowledgePanel.vue | 公共目录，登录与游客复用 ChatPanel，发布状态改变后刷新 |
| src/components/DocumentPanel.vue | 上传队列、轮询、文档列表/筛选、预览，协调三种编辑面板及 busy 状态 |
| src/components/DocumentTextEditor.vue | 原始正文读写、版本、保存确认、未保存修改提示 |
| src/components/DocumentMetadataEditor.vue | 打开时独立读取最新名称/分类/版本，不能依赖旧列表字段 |
| src/components/DocumentReplacementEditor.vue | 读取替换条件、选文件、确认、传输和处理提示、超时核对 |
| src/components/ChatPanel.vue | SSE、历史、引用及正文定位；guest 模式不发历史请求、不展示来源 |
| src/components/AnswerContent.vue | Markdown/数学渲染结果经 DOMPurify 后展示 |
| src/api.js | JSON、Cookie/CSRF、取消/超时；XHR 上传与新版本替换 |
| src/chat-stream.js | SSE 解析、UTF-8 分片、完成检查、停止；publicOnly 选择游客接口 |
| src/chat-history.js | 服务器消息转为对话展示，保留失败/中断/legacy 等状态 |
| src/document-upload.js | 格式校验、串行队列、单文件失败隔离、401/取消中止 |
| src/document-filter.js | 名称与手动分类组合筛选，不修改原列表 |
| src/answer-markdown.js | markdown-it + MathJax TeX/SVG，支持常用 LaTeX 分隔符 |

重要行为：

- 上传请求使用 FormData，让浏览器设置 multipart boundary，不手动设置 Content-Type。
- 不自动重试上传或替换，网络超时后先核对服务器状态。
- 列表与预览有版本计数和 AbortController，防止切库后旧响应写回。
- 编辑面板打开或文档操作期间，通过 uploading-change 锁定父级知识库切换等操作。
- 公共/个人两个 ChatPanel 可能同时挂载，已用 Vue useId 避免表单 ID 冲突；新增内容不要又写死相同 ID。
- Markdown 禁止原始 HTML；AnswerContent 保留 DOMPurify 清理。新增关键词高亮不要把未转义的用户/资料文本拼成 v-html。
- package-lock 固定依赖，不要顺手升级。当前 Vue 3.5.44、Element Plus 2.14.7、Vite 8.3.5、markdown-it 15.0.3、MathJax 3.2.2、DOMPurify 3.4.17；xmldom 有 0.9.12 override。
- MathJax 异步 chunk 约 1.75MB（gzip 约 623KB），Vite 有体积警告，当前构建成功。不要把该已知警告当成当前功能故障或无理由升级依赖。

## 9. 后端结构与接口

仓库后端目录：`D:\我的文档\文档\ChatGPT\codex学习\RAG\backend`。

关键模块：

- app/main.py：注册 auth/kbs/public/conversations/doc/chat 路由；启动时 init_db。
- app/core/auth.py：PBKDF2 密码、随机会话 token 散列、Cookie、CSRF、Origin 与登录频率限制。
- app/db/auth_migration.py：旧 users 添加 nullable password_hash 前，用 SQLite backup API 备份（含 WAL）；旧 dev 账号不自动变成可登录账号。
- app/db/models.py：User、KnowledgeBase、PublishedKnowledgeBase、Document、DocumentCategory、Chunk、IngestTask。
- app/db/chat_models.py：Conversation、Message、MessageState；后者保存 done/failed/stopped 和拒答标记，旧记录按 legacy 处理。
- app/api/doc.py：文档路由；app/services/doc_service.py：生命周期、所有权与共享入库锁。
- app/services/document_text.py：TXT/MD 编辑及同格式替换，共用先准备新内容/向量、再备份更新的逻辑。
- app/services/doc_service.py 的 minimum_content_chars / split_document_pages：统一上传、替换的内容及切片门槛，图片 5 字，普通文档 50 字且普通片段默认 20 字；不要分别硬编码门槛。
- app/services/document_metadata.py：展示名称、独立手动分类、版本冲突、向量元数据名称同步及 BM25 缓存失效。
- app/rag/vectorstore.py：Local/Chroma，snapshot_doc 与 replacing_doc 支持普通失败补偿；Local 使用锁和整份快照替换。
- app/services/parsing/loader.py：PDF 从 bytes 打开，DOCX 使用显式关闭的源流，避免 Windows 损坏文件残留占用。
- app/api/public.py：游客 stateless RAG、公开列表、引用事件拦截和 done 白名单、每 IP 10 次/分钟。
- app/services/conversation_activity.py：单进程活动对话锁；生成时禁止删除同一对话。
- app/rag/pipeline.py、retriever.py、context.py、llm.py：A/B 问答与检索基础，保留契约，局部扩展。

接口概览：

| 接口 | 当前边界 |
|---|---|
| /api/auth/register、login、me、logout | 真实账号和 Cookie 会话 |
| GET/POST /api/kbs，GET/PATCH/DELETE /api/kbs/{id} | 当前用户管理自己的知识库；删除必须空库 |
| PUT /api/kbs/{id}/visibility | 所有者 + CSRF，整库公开/撤销 |
| GET /api/public/kbs | 无需登录，只返回公开库 id/name |
| POST /api/public/chat/stream | 仅公开库、单次问题、无服务器历史、无引用对象 |
| POST /api/chat/stream | 登录 + CSRF，自己的库或公开库，持久化自己的对话 |
| /api/conversations 及 /{id}/messages | 登录用户自己的历史、改名、确认删除、游标分页 |
| POST /api/docs/upload | 所有者上传，界面始终 overwrite=false |
| GET /api/docs、/{id}/status | 登录，当前所有者文档列表及处理状态 |
| GET /api/docs/{id}/preview | 登录，允许所有者或已公开库的读者；游客 401 |
| GET /api/docs/{id}/file | 登录，允许所有者或当前已公开库的读者；PDF/图片 inline，DOCX/MD/TXT 附件；游客 401 |
| DELETE /api/docs/{id}、POST /{id}/reindex | 所有者 + CSRF，不允许处理中操作 |
| GET/PUT /api/docs/{id}/text | 所有者正文编辑；PUT 带 content 和 version |
| GET/PATCH /api/docs/{id}/metadata | 所有者；PATCH 带 filename/category/version |
| GET/POST /api/docs/{id}/replacement | 所有者；POST multipart file + version，确认替换 |

重要边界：

1. get_document 强制所有权，供维护接口使用；get_readable_document 允许登录后的公开正文阅读。不能把维护接口统一改成可公开读取的权限。
2. 公共阅读正文与原文件都要求登录并复用 get_readable_document；不公开磁盘 uploads 目录，游客仍不能获取原文件。
3. 游客参数模型 extra=forbid，不接受 user_id、conversation_id、include_citations 或 stream=false。不能把认证问答接口直接改成可选登录来省事。
4. 原认证 SSE 是 meta → citation* → delta* → done，done 为最终答案/引用；拒答 done 有时没有 answer，guest 已用累积 delta 兜底。
5. 游客事件只白名单返回 meta、delta、done/error；不返回文档/片段编号、文件名或引用正文结构。答案本身允许包含基于公开资料生成的数学内容。
6. 对话归属、知识库访问、文档维护权限均在后端验证，不能只隐藏按钮。
7. 文档编辑/替换会产生新 chunk_id，旧历史引用可能失效；当前正文定位会核对 chunk_id，不应把新版片段冒充旧引用。
8. 旧 A overwrite=true、reindex 路径仍为契约兼容保留，不等于安全替换。新版本功能使用独立 replacement 接口，不要退回先删旧文档的旧路径。
9. 手动分类独立表，编辑正文后保留；A 自动知识标签因正文改变而清空，需重新生成。改名时不重新 Embedding，但需同步向量名称及使 BM25 名称缓存失效。
10. 修改路由后，需同步仓库根目录 docs/api/openapi.json；有契约测试检查一致性。

## 10. 测试与已知验证范围

没有在每次任务后反复运行全量测试。以下是最近一次相关验证，**不同批次有重叠，不能相加当作总测试数**：

| 阶段 | 实际验证 |
|---|---|
| 原 A/B 基线 | 早期 80 项通过 |
| 账号阶段 | 当时 98 项全量通过；不代表后续所有代码做过最新全量 |
| 改名分类阶段 | 37 项相关后端、2 项前端筛选、构建通过 |
| 版本号遗漏修复 | 15 项相关后端与构建通过 |
| 文件替换阶段 | 43 项相关后端、8 项前端接口、构建通过；真实生成 PDF/DOCX/MD/TXT 测试 |
| 公共权限阶段 | 19 项公共/知识库/账号 + 23 项原问答/历史/文档/契约，共 42 项相关后端；8 项 SSE 前端测试；构建通过 |
| 新聊天改动审查 | 修复前 39 项相关后端及当时 30 项前端通过，另复现中文高亮和短图门槛问题 |
| 审查修复（最新） | 34 项相关后端、3 项新增高亮测试、构建、diff 检查通过；图片 OCR 推理使用模拟输出，不是识别质量验收 |

浏览器验收由用户手动完成并反馈成功。没有配置自动浏览器测试环境，不要声称已做自动浏览器截图、跨浏览器或全手机测试。

测试命令示例（按当前改动选择相关文件，不默认全部重跑）：

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG\backend'
..\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_public.py tests/test_kbs.py tests/test_openapi_contract.py
```

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend'
node --test tests/chat-stream.test.js
npm.cmd run build
```

后端 tests/conftest.py 在导入应用前强制设置 mock/hash/local 和测试 SQLite，清理的目录是：

```text
D:\我的文档\文档\ChatGPT\codex学习\RAG\backend\tests\.pytest_data
```

只可用于测试，不要往这个目录存真实资料。不要让测试指向 demo 或生产数据库。

conftest 中旧 dev 身份只注入原 A/B 的几个测试模块，保持其原有边界；运行中的后端没有 dev 身份绕过。不能为通过测试在生产代码里新增 APP_ENV=test 免鉴权逻辑。

更新 OpenAPI 时在仓库根目录运行 scripts/dump_openapi.py，必要时把 DATABASE_URL 暂时指向独立 .tmp/contract/app.db，执行完恢复进程环境，避免导入时碰真实数据。不要覆盖用户 .env。

## 11. 历史问题与已经解决的坑

- 用户在服务占用的 PowerShell 窗口无法输入命令：这是前台服务正常运行，另开终端；不要让用户停服只为输入其他命令。
- Windows 中文路径与旧 pip GBK：使用项目 python -X utf8，不改用户文件编码来迁就安装。
- metadata 保存曾因旧列表缺少 version 失败：编辑器现已在打开时 GET 最新元信息，读取成功后才允许保存。保持这个设计。
- 损坏 PDF 曾在 Windows 保留句柄导致清理失败：loader 已改为 bytes 打开，DOCX 也显式管理文件流。不要改回直接依赖库自行关路径。
- 预览正文是 OCR/文档解析片段；查看原文件返回当前存储版本，旧引用仍需先按 chunk_id 验证。
- 模拟回答对不同题目相同：是已标注的 mock，不应修改前端硬编码出正确答案来“修复”。
- 不要把未知旧记录状态强行改成成功，也不要把中断/部分回答算完整回答。
- C-BASELINE 等旧课次部分文字保留最初阶段；最新进度以本文件、PROGRESS 和用户反馈为准。

## 12. 下一步的具体接续建议

先阅读 C-REVIEW-FIXES.md，按其步骤复核修复后的中文高亮、短图入库和替换，然后继续静态图片真实 OCR 浏览器验收。两项问题已经修复，不要重复实施。验收后再单独开发识别校对或拍照入口，不同时开展主题或部署。

建议先读：

```text
D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend\src\components\ChatPanel.vue
D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend\src\components\AnswerContent.vue
D:\我的文档\文档\ChatGPT\codex学习\RAG\backend\app\api\doc.py
D:\我的文档\文档\ChatGPT\codex学习\RAG\backend\app\services\doc_service.py
D:\我的文档\文档\ChatGPT\codex学习\RAG\backend\tests\test_public.py
```

实施要点：

- 从当前问题提取适量有意义的关键词，在引用 snippet 中做安全的文字高亮，不破坏 LaTeX 或用不受控 v-html。
- 原文件读取必须登录，允许所有者或公开知识库读者，拒绝游客和其他私有库用户。
- 文件路径来自已授权 Document.stored_path，不接受客户端任意磁盘路径。
- PDF/PNG/JPG/JPEG 使用浏览器原生查看；DOCX 浏览器通常不能直接排版预览，可提供原文件下载并保留当前解析正文。TXT/MD 不作为可执行 HTML 提供。
- 文档替换后旧 chunk_id 可能失效，要说明当前文件/引用的版本关系，不能让旧回答引用悄悄指向不相干新版内容。
- 保持现有引用正文定位、登录/公共权限、取消与错误展示。测试覆盖越权、文件类型/下载响应以及安全高亮的相关行为。
- 新课仍提供清晰浏览器操作、预期和恢复方式，交付后等用户验收。

## 13. 课程文档索引

最新进度：`D:\我的文档\文档\ChatGPT\codex学习\codex-course\PROGRESS.md`。

路线：`D:\我的文档\文档\ChatGPT\codex学习\RAG\docs\C-DELIVERY.md`。

课次文档都在 `D:\我的文档\文档\ChatGPT\codex学习\RAG\docs`：

```text
C-BASELINE.md              环境和运行基线
C-AUTH.md                  账号
C-KNOWLEDGE-BASES.md       个人知识库
C-DOCUMENTS.md             最初单文件上传/轮询/预览
C-BATCH-UPLOAD.md          批量拖拽上传
C-CHAT.md                  流式问答/公式/引用
C-HISTORY.md               历史对话
C-DOCUMENT-DELETE.md       删除确认
C-TEXT-EDIT.md             正文编辑
C-DOCUMENT-METADATA.md     改名/分类/筛选和版本修复
C-FILE-REPLACEMENT.md      新版文件替换
C-PUBLIC-QA.md             公共库/游客/登录权限
C-CITATIONS.md             引用关键词高亮/原文件查看（已验收）
C-IMAGE-OCR.md             图片上传/本地文字 OCR（待浏览器验收）
C-REVIEW-FIXES.md          最新审查修复、验证边界与接续步骤
C-HANDOFF.md               本交接说明
```

可用练习文件：`D:\我的文档\文档\ChatGPT\codex学习\RAG\docs\samples\数学资料-替换练习-v2.txt`。

原六周课程材料保留但不再代表当前排期。初期 grilling 需求澄清已结束，不要重新审问用户。项目局部功能开发延续 minimal-change 原则；若后续教授 Codex 当前产品功能、安装配置、Skills/MCP/Automations，届时读取适用技能并核对官方资料。

## 14. 迁移范围提醒

同机换聊天不需要迁移文件或重建环境，只要新聊天打开同一个本地工作区并读取此文档。

若实际换电脑，事情不同：必须另外处理未提交代码、SQLite 一致备份、上传/向量/版本数据和必要本机配置；不要仅克隆 GitHub。不要把 .venv/node_modules 当作可直接跨机器复用的环境，也不要把密钥粘贴到新聊天。当前交接没有执行异机搬迁、Git 提交或远程推送。
