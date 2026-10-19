# api/ · 契约与 Mock

## 真源在哪里

**唯一真源是后端代码生成的 OpenAPI**：`app/api/schemas.py` → `GET /openapi.json`。
本目录只放两类东西：约定说明 + 无后端联调用的 mock 数据。

```bash
# 后端起来后，前端生成 TS 类型（字段名不用猜）
cd frontend
pnpm dlx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/schema.d.ts
```

## mock 文件

| 文件 | 用途 |
|---|---|
| `mock/kbs.json` | 知识库列表响应 |
| `mock/docs.json` | 文档列表响应（含 pending/ready/failed 三种状态） |
| `mock/chat_stream.txt` | SSE 完整事件流，可直接被前端的帧解析器消费 |

前端用 MSW 拦 `/api/*`；或在 `src/api/http.ts` 里判断 `VITE_USE_MOCK=1` 直接返回 mock。

## SSE 联调技巧（C 用）

```ts
// 把 mock 的文本变成一个 ReadableStream，前端解析逻辑一行不用改
const text = await (await fetch('/mock/chat_stream.txt')).text()
const stream = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode(text)); c.close() } })
```

## 变更流程

1. 改 `schemas.py` → 本地起服务 → `openapi.json` 变了
2. 群里说明 + 更新 `../01-架构与接口契约.md` §5
3. C 重新生成 `schema.d.ts`，`tsc --noEmit` 报错的地方就是要改的地方
4. 涉及破坏性变更（改字段名/删字段）→ 必须当天对齐，不许"明天再说"
