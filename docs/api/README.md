# docs/api —— B → C 的契约文件

C 开工只需要这三个，按顺序看：

| 文件 | 用途 | 怎么用 |
|---|---|---|
| `openapi.json` | 全量接口 schema：A 的 6 个 `/api/docs/*`、B 的 `/api/chat/stream`、`/api/health` | `pnpm dlx openapi-typescript docs/api/openapi.json -o src/api/types.ts`，字段名不靠猜 |
| `mock/chat_stream.txt` | SSE 逐帧样例（meta → citation×3 → delta×5 → done） | 喂给 vitest：按 `\n\n` 分帧 → 逐帧断言，解析器写完就能自测 |
| `mock/samples.jsonl` | 4 条真实端到端样例（问题 + 完整事件/答案） | 看四种典型场景的效果：正面回答 / declined 拒答 / refused 拒答 / 非流式 |
| `../B-接口与边界.md` | 人读：事件顺序、错误码、配置项、拒答与降级、已知限制 | 联调前先读 §3（接口）与 §7（交接点） |

## 四种典型场景（真实数据跑通，样例见 `mock/samples.jsonl`）

| id | 问题 | 结果 | 关键字段 |
|---|---|---|---|
| s1 | 两个重要极限分别是什么 | ✅ 正面回答 | `refused:false, declined:false`，答案带 `[2]` 引用 |
| s2 | 判断 f(x)=x²+2x 的单调性 | ❌ 拒答（declined） | `confidence:0.99` 但 `declined:true`，有 citation 仍拒答 |
| s3 | 今天北京天气怎么样 | ❌ 拒答（refused） | `confidence:0.03`, `refused:true`, `first_token_ms:0`（未调模型） |
| s4 | 什么是洛必达法则 | ✅ 正面回答（非流式） | `stream:false` 返回一次性 JSON `{code,message,data}` |

> s2 是**最容易误判**的一条：检索分数 0.99、citation 有 2 条，但答案是拒答。
> 所以 UI 判定只能看 `refused or declined`，绝不能看 citation 数量。

## C 侧最容易踩的两个点

1. **引用定位**：`citation.page` 只在 PDF 来源有值，当前语料全是 Markdown，`page` 恒为 `null`。
   逐字定位要用 `char_start / char_end`（该 chunk 在原文全文的字符区间），或按 `seq` 翻条。
2. **拒答有两种**：`done.refused=true` 是管线没调模型就拒（无 citation）；
   `done.declined=true` 是模型读了资料仍说"未找到依据"（有 citation）。
   UI 判定条件写 **`refused or declined`**，不要用 citation 数量判断。

## 重新生成 openapi.json

后端接口有改动时（新增字段、改路径），跑一次并一起提交：

```bash
python scripts/dump_openapi.py
```

生成器读的是真实 `app.openapi()`，所以它反映的是**代码当前的样子**，不是手写的文档。
SSE 的事件体不进 OpenAPI（流式响应只能声明 `text/event-stream`），因此事件字段以
`docs/B-接口与边界.md` §3 与 mock 文件为准，后端有 `backend/tests/test_sse_contract.py`
保证这两处不漂。

## 联调顺序建议

1. 起后端：`cd backend && uvicorn app.main:app --reload --port 8000`，打开 `/docs` 直接试调。
2. 没有模型 key 也能联调：`MOCK_LLM=true`，回答是模板但事件流、引用、错误码都是真的。
3. 鉴权先用临时替身：`Authorization: Bearer dev`（或 `Bearer dev:<name>` 切用户）；
   JWT 上线后替换 `app/api/_dev_user.py`，B 侧代码不用改（签名保持一致）。
4. 越权自测：用 `Bearer dev:other` 请求别人的 `kb_id`，应拿到 HTTP 403 + `code=1003`，
   且**不会**建立 SSE 流（错误是 JSON 信封，不是流里的 error 事件）。
