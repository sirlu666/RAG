# frontend · 前端

## 目录（C 负责，其他人只提 issue 别直接改）

```
src/
├─ main.ts             # 入口：Element Plus / Pinia / Router / KaTeX 样式
├─ App.vue             # 顶栏壳
├─ router/index.ts     # 路由（/ → ChatView）
├─ views/              # ChatView / LoginView / KbView / DocView / SettingView
├─ components/         # MarkdownRenderer / CitationCard / DocUploader / ChatBubble
├─ api/
│  ├─ http.ts          # axios 实例 + 错误码 → 中文文案 + 401 跳登录
│  ├─ sse.ts           # ✅ 已实现：fetch + ReadableStream 的 SSE 解析
│  └─ schema.d.ts      # 由 openapi-typescript 生成，勿手改
├─ stores/             # user / conversation / kb
└─ styles/             # 主题变量（深浅色、字号）
```

## 运行

```bash
pnpm install
pnpm dev          # http://127.0.0.1:5173，/api 已代理到 8000
pnpm typecheck
```

后端没起来也能看页面：`ChatView` 会在请求失败时给出提示，不影响布局调试。

## 三个必须踩过的坑（提前写在代码里，不要重复踩）

### 1. 公式渲染顺序：先保护，再渲染，最后还原
markdown-it 会把 `x_1` 当强调、把 `*` 当列表。正确顺序：

```ts
const math: string[] = []
// 1) 把 $...$ / $$...$$ 换成占位符 \u0000MATH0\u0000
const protectedMd = md.replace(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g, (m) => {
  math.push(m); return `\u0000MATH${math.length - 1}\u0000`
})
// 2) markdown-it 渲染（html: false 或 DOMPurify 二次过滤）
// 3) 还原占位符为 katex.renderToString(m, { throwOnError: false, displayMode: m.startsWith('$$') })
```

### 2. 流式高频 setState 会卡
不要每收到一个 delta 就 `answer += t` 触发渲染。用 buffer + `requestAnimationFrame` 每帧 flush 一次：

```ts
let buf = '', raf = 0
const flush = () => { answer.value += buf; buf = ''; raf = 0 }
onDelta: (t) => { buf += t; if (!raf) raf = requestAnimationFrame(flush) }
```

### 3. SSE 在 Nginx 下会被"攒包"
后端响应头带 `X-Accel-Buffering: no`，Nginx 配 `proxy_buffering off;`。验收标准：**逐字出现**，不是停 5 秒后一次性出现。

## 与后端的协作

- 字段名不看文档猜，跑 `pnpm gen:types`（需后端已启动）。
- 后端未就绪：用 `docs/api/mock/chat_stream.txt` 喂给 `sse.ts` 的解析器（见 `docs/api/README.md`）。
- 21 个接口的归属见 `docs/01-架构与接口契约.md` §5；你负责 #1-7、#16-19。
