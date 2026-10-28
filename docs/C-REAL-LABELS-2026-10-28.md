# 当前知识库模型标签交付

2026-10-28：用户明确授权由本聊天代替 A 完成标签产物。此前“不由 C 生成标签”的分工限制已被本次授权取代。

## 来源与产物

本机没有发现 A 的 `label_export.json`，没有可用的 LABEL/VLM/DeepSeek 环境凭据。未读取正在运行的后端内存、未重启服务，也未寻找旧聊天密钥。

本次由 **Codex 当前会话模型**读取当前关系库中真实解析正文的片段并生成标签，再由工具执行校验与版本绑定导入。标签不是按文件名规则拼接、不是手工测试夹具，也不是 A 原来声称的 GLM 产物。没有独立提供商 API 请求 ID、模型权重 revision 或调用回执，不冒充这些信息；精确服务模型版本未对本任务公开。

覆盖实际现状：`c_integration` 账号的 172 份 ready 资料，其中团队库 171 份 Markdown，另一库 1 份 TXT。没有为了凑基线重建、替换或删除任何资料。标注基于标题和正文摘要片段，不表示对全文逐题完成数学正确性复核，`human_reviewed=false`。

私有产物目录：

```text
%LOCALAPPDATA%\Temp\mathrag-c-integration-20261028\labels-codex-20261028
```

- `label_export.json`：172 份标签、文档 ID、文件名、内容哈希、源更新时间、完整解析正文 SHA-256、摘要及模型来源。
- `manifest.json`：导出文件 SHA-256 为 `1e787e1076d436d07c68a4be11961a5dff23e4382b4ae496e5384059cdf436b6`。
- `source-snapshot.json`、`model-labels-*.json`：来源与本会话模型输出留档。
- `label-fields-backup.json`：写入前的标签/难度字段及恢复条件，不是整库快照。
- `dry-run.json`、`import-report.json`、`integrity.json`：预检、实际导入与未改动内容的指纹核对。
- `browser-result.json`、`real-tag-filters.png`、`retriever-read-result.json`：真实页面/接口与 B 读取验证。

产物和恢复文件保留在本机私有数据目录，不提交 Git，不包含密钥或账号密码。

## 写入与验证结果

- 172/172 标签结构通过校验：知识点最多6项、每项40字；题型最多5项、每项24字；难度为基础/进阶/困难。
- 先只读预检，再事务导入：文档归属、ready 状态、内容哈希、更新时间、原标签值、解析正文 SHA-256 均匹配；有活动入库任务或版本变化则跳过。此次成功172、跳过0。
- 仅修改 `documents.tags_json`、`difficulty` 和版本时间 `updated_at`。其他文档字段与全部 chunk 字段指纹一致；仍为172文档、2520切片，用户、库、任务、会话、消息数量不变，未重建向量。
- B 的候选回表读取 `documents.tags_json`，不依赖 Chroma 的冗余标签。只读调用现有 `load_chunk_records`，2520条均带标签；“伴随矩阵”命中22条记录，现有标签匹配分为正。没有发起检索/嵌入/LLM 请求，没有改算法或主排序。
- 真实后端 `GET /api/docs` 返回团队库171份带标签资料；无头浏览器使用实际接口、没有注入假标签，知识点“伴随矩阵”+题型“计算题”+难度“基础”组合筛选得到1份；“已有标签”筛选返回171份，页面错误0。
- 新导入工具6项测试通过；另有执行期隔离数据库检查覆盖预检不写入、错误归属、版本/正文变化、活动任务、非法结构、应用、重复导入、备份保护与字段回滚。未重跑无关全量测试或前端构建。
- 付费提供商调用0，预算仍76/100、保守预留上界0.4926795美元。8002/5174原进程保持运行，标签展示已生效。

## 使用与恢复

页面进入知识库后打开“管理资料”，点击“刷新文档”，即可使用自动知识点、题型和难度筛选。筛选不改变问答范围；新上传、正文编辑或替换后的资料仍需对新版本重新标注，不会复用失效旧标签。

`scripts/import_label_export.py` 默认只读预检，不调用模型；必须显式 `--apply` 才写入。重跑不会覆盖已变化的数据。

在当前 worktree 根目录，以下为只读恢复预检（不执行回滚）：

```powershell
$labelDir = "$env:LOCALAPPDATA\Temp\mathrag-c-integration-20261028\labels-codex-20261028"
..\..\.venv\Scripts\python.exe -X utf8 scripts/import_label_export.py --db "$env:LOCALAPPDATA\Temp\mathrag-c-integration-20261028\app.db" --labels "$labelDir\label-fields-backup.json" --user c_integration --rollback
```

确需恢复标签字段时才追加 `--apply`；仅版本、正文指纹和导入标签仍一致的文档会恢复，发生后续编辑的文档会跳过。不要恢复整库、删 Chroma 或清空预算。

## 已记录的来源问题

`张宇30讲原稿__第13讲-多元函数微分学.md` 的解析正文存在历史乱码。模型结合可读/解码查看后的主题片段给出较宽泛标签，在导出中单独标明 `quality_notes`；源文件和切片未修复。此项是正文质量待复核，不是标签导入失败，不据此宣称整库内容已校对无误。
