# 学生 A 最新交付验收：未通过，需整改后复验

后续更新：用户授权直接修复，5项已复现代码缺陷及快照/下载说明问题已在 `8cabbfea17de5b7d739d627a5ec9dcbb3af768a7` 修复，119项后端测试通过。已上传修复分支并创建 https://github.com/sirlu666/RAG/pull/3 ，目标为A交付分支，尚未合并。真实标签包、配套关系数据和旧快照生成时模型revision仍待A交接/确认。本报告以下内容保留为原 `9d0c0a1` 的验收记录；修复说明见远端 `docs/A-ACCEPTANCE-FIXES.md`。

验收日期：2026-10-26。验收对象：`codex/a-integration-delivery`，提交 `9d0c0a1665213eae4a402ed110de3a1c29c390c5`。

## 1. 结论与范围

目前不能接受“ A-01～A-04 全部完成”的交付结论。95项现有测试通过，但隔离补充验收复现5项阻塞缺陷；运行材料与快照恢复说明还需补齐。

本轮只做验收：通过 GitHub 读取最新提交、fetch 分支至对象库、导出独立副本；没有 checkout/merge 到 C，没有修改 A 实现、C 代码或用户资料，没有代替 A 修复。

独立副本：`.tmp/a-delivery-review-th44_689`。C 分支仍为 `codex/c-platform`，默认暂存区保持原样。等待 A、B 全部完成后才恢复 C 开发/联调的约定继续有效。

## 2. 已确认进展

- 新增独立 LABEL 配置、标签输出校验、列表字段、Chroma标签标量序列化。
- 导入脚本新增数据库/上传/向量目录及用户名参数，图片识别已有独立适配器。
- 原先“新覆盖文件解析过短导致旧文档被删”的专门回归通过；说明有实际修复，下面的问题针对其他未覆盖路径。
- 95项后端测试通过。复验显式设置 `OCR_FORMULA=none`，避免测试自动加载/下载可选公式模型；此结果不等于默认公式配置或真实BGE/打标全部验收。未调用真实打标服务或付费模型。

复验命令在独立副本执行，环境固定为独立测试路径、dev向量、mock回答。额外复现只用临时数据库、哈希向量及OCR/VLM/标签返回桩，未触碰 demo 数据。

## 3. 阻塞缺陷：请 A 修复并补回归

### F1 / P1：成功重建后残留旧向量

位置：[doc_service.py:61](https://github.com/sirlu666/RAG/blob/9d0c0a1665213eae4a402ed110de3a1c29c390c5/backend/app/services/doc_service.py#L61)。

原因：`_delete_chunk_ids()` 传入 chunk_id，却调用 `store.delete_doc(cid)`；Local/Chroma 的 delete_doc 都按 metadata.doc_id 删除，无法删除目标旧切片向量。随后关系库旧 chunk 被删，形成孤儿向量。

复现：

1. 上传一个正常MD，入库后1条关系切片、1条向量。
2. 对该文档调用 reindex，等待成功。
3. 结果：新旧关系切片ID不同，关系库仍1条，向量库却2条；旧ID还存在。

验收实测：`old_chunk_ids_replaced=true, stale_vectors_remaining=1, relational_chunks=1, vector_count=2`。

修复验收：按切片ID准确删除旧向量，不能为了清理旧切片把同文档的新向量一起删掉。Local与Chroma均补成功重建、连续重建与对账测试，要求零孤儿、零缺失。

### F2 / P1：同内容覆盖导致旧文档永久隐藏

位置：[doc_service.py:140](https://github.com/sirlu666/RAG/blob/9d0c0a1665213eae4a402ed110de3a1c29c390c5/backend/app/services/doc_service.py#L140)。

原因：同名旧对象先在ORM中标记superseded；当前Session是autoflush=False，查重仍命中数据库旧ready行。恢复用bulk update时，数据库尚无superseded行；commit再把ORM中的superseded写入，之后返回重复错误。

复现：上传一份正常MD，再用完全相同文件名、相同字节及overwrite=true上传。

验收实测：第二次HTTP409，但旧文档状态变为superseded，列表中不可见，而不是保留ready。

修复验收：重复内容拒绝或幂等返回均可，但旧文档必须保持原状态、正文/文件/索引/可见性；不得波及同知识库其他同名更新任务。补同内容覆盖、内容撞另一文档、并发覆盖回归。

### F3 / P1：重建失败后旧切片虽保留，但旧资料不可用

位置：[doc_service.py:261](https://github.com/sirlu666/RAG/blob/9d0c0a1665213eae4a402ed110de3a1c29c390c5/backend/app/services/doc_service.py#L261)。

原因：失败把原文档标成rejected/failed；`_rollback_superseded()` 只恢复其他superseded文档，对当前文档reindex无效。预览和检索均要求ready。

复现：正常文档入库后，对reindex流程注入解析失败；原文件未改变。

验收实测：`status=rejected, retained_chunks=1, retrievable_chunks=0, preview_http=422`。

修复验收：区分本次任务失败与已发布旧版本的可用状态。重建失败时旧版仍可预览、检索，任务错误可单独查询；解析失败、向量写失败、清理失败分别验证。不能只证明旧chunk仍留在表里。

### F4 / P1：标签没有版本并发保护，旧结果能写回新文档

位置：[auto_label.py:209](https://github.com/sirlu666/RAG/blob/9d0c0a1665213eae4a402ed110de3a1c29c390c5/scripts/auto_label.py#L209)。

原因：文档注释声称绑定content_hash，但任务没有携带并核对源版本；落库仅filter(Document.id == doc_id)，没有版本条件。

复现：

1. 标签任务读取旧版正文后，模拟等待模型返回。
2. 同一文档content_hash已变化，标签被清空。
3. 返回旧版标签。

验收实测：文档已是新content_hash，旧版知识点仍被写入并统计为成功。复现使用本地桩，没有外部模型调用。

修复验收：使用任务源版本进行原子条件更新；更新行数为0时记为过期/跳过，不算成功。补版本过期、文档被删除、重复任务及正常成功回归。不要通过给C恢复旧标签来解决。

### F5 / P1：VLM路径把独立公式从题目正文删除

位置：[recognize.py:164](https://github.com/sirlu666/RAG/blob/9d0c0a1665213eae4a402ed110de3a1c29c390c5/backend/app/services/parsing/recognize.py#L164)。

复现：VLM返回 `已知 $$x^2-3x+2=0$$，求实根。`，调用图片适配器。

验收实测：返回 `text="已知 ，求实根。"`，公式只在latex字段中，原文位置丢失。与适配器注释“text含文字与独立公式、保持顺序”的约定不符；B若将text作为question，将失去题目关键条件。

修复验收：text保留完整数学题与公式顺序，latex仅作附加抽取。补纯公式题、多公式穿插文字、行内/块级混合、Rapid/VLM返回一致性测试；不需要额外模型调用来测试此逻辑。

## 4. A-01 运行材料与说明的待补项

### D1：快照恢复说明会导致关系ID不匹配

交付说明 §2.3 / §7 表示先用ingest重建关系库，再用既有快照，靠vector.id==chunks.id对齐。实际上ingest调用new_id生成新的doc/chunk/kb ID，旧快照保存的是旧ID，不能自动对齐。

请提供匹配关系数据/显式映射方案，或明确禁止将旧快照与新建关系数据混用、统一重新向量化；同时提供对指定独立目标目录执行的对账命令。不能把“这次重新生成的向量与这次新关系库一致”作为旧快照可复用的证据。

### D2：模型下载路径和版本说明不够可复现

交付说明先 `cd backend`，随后用 `local_dir='data/models/bge-m3'` 下载，会落到backend/data/models，而项目配置按仓库根目录解析data/models。后面又使用根目录下scripts命令，执行位置不一致。

请修正文档的工作目录、Windows可复制命令和模型解包路径，给出固定revision/版本或校验信息，而不仅是可变的模型名称。

### D3：真实标签产物尚未实际交接到 C

说明声称171篇已重打并导出 `data/label_export.json`，但本机未收到此文件；仓库中只有标签文字样例，没有可核对的完整版本绑定产物。此项记为“交付说明宣称完成、实际材料待接收”，不等于判定 A 没有运行过模型。

请按约定私下交接脱敏标签包/版本与文档映射、模型版本及校验信息；不必把密钥或私有数据库上传GitHub。MD/PDF/DOCX三格式真实结果现为文档记录，收到对应证据后再核对，不以模拟用例替代。

## 5. 按任务书逐项判定

| 项 | 本轮判定 | 原因 |
|---|---|---|
| A-01 | 部分通过、材料待补 | 参数化导入已实现；快照ID方案、模型路径/revision和材料交接仍需补齐 |
| A-02 | 未通过 | F4版本保护缺失；真实标签产物待实际接收 |
| A-03 | 未通过 | F1/F2/F3，现有单一覆盖失败回归未覆盖这些路径 |
| A-04 | 未通过 | 适配器已存在，但F5破坏公式题正文；现有测试主要验证输入失败与白图返回结构 |

## 6. 给 A 的整改交付要求

1. 修复F1～F5并补针对性回归；补齐D1～D3的方案/实际交接材料。
2. 在原交付分支提交后给出新提交号及测试结果，指出每项修复对应的代码、用例和验证结果。
3. 不改 C 前端，不覆盖 C 未提交成果，不访问用户demo数据；不要求 C 提前做联调来替代你方验证。
4. 真实模型受凭据/费用条件限制时明确标注，不为消除“待验证”自行增加付费调用。
5. 本报告尚未写入GitHub或发送给A；由用户决定转发。修复并复验通过后才可记A完整交付，C仍需等待B全部完成。
