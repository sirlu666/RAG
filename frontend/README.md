# MathRAG 前端 · 第 1 天

当前实现：首页、真实账号、个人知识库、拖拽批量上传/进度/正文预览/确认删除、SSE 问答、公式及引用定位，以及会话历史打开/追问/改名/删除。操作见 [账号练习](../docs/C-AUTH.md)、[知识库练习](../docs/C-KNOWLEDGE-BASES.md)、[文档练习](../docs/C-DOCUMENTS.md)、[批量上传练习](../docs/C-BATCH-UPLOAD.md)、[删除练习](../docs/C-DOCUMENT-DELETE.md)、[问答练习](../docs/C-CHAT.md) 和 [历史练习](../docs/C-HISTORY.md)。TXT／Markdown 正文编辑和同格式文件新版本替换已接入。

新增 TXT／Markdown 原始正文编辑、版本校验、旧版备份及索引更新，操作见 [正文编辑练习](../docs/C-TEXT-EDIT.md)。

文档改名、手动分类与名称/分类组合筛选已接入，操作见 [分类筛选练习](../docs/C-DOCUMENT-METADATA.md)。

同格式文件新版本替换已接入，支持 PDF／DOCX／MD／TXT，操作见 [新版本替换练习](../docs/C-FILE-REPLACEMENT.md)。

公共知识库确认公开/撤销、游客问答及登录公共引用已接入，操作见 [游客权限练习](../docs/C-PUBLIC-QA.md)。现有知识库默认私有；游客不保存服务器历史，不返回引用片段与正文入口。

引用高亮/原文件、静态图片 OCR 已接入；最新中文高亮和短图片门槛修复已测试通过，实际图片流程仍待浏览器验收，接续见 [审查修复交接](../docs/C-REVIEW-FIXES.md)。

使用 Vue3、Element Plus 和 Vite；精确安装版本记录在 package-lock.json。依赖已由教师安装，无需重复执行 npm install。

## 启动

保持后端 PowerShell 窗口运行，在**另一个** PowerShell 窗口逐条执行：

```powershell
Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG\frontend'
npm.cmd run dev
```

看到 Local 地址后打开 http://127.0.0.1:5173 。服务器持续运行时该窗口也不能输入普通 PowerShell 命令。停止前端按 Ctrl+C，不会停止另一窗口的后端。

预期：显示“数学答疑工作台”。后端运行时，应用运行中、数据库已连接，向量数来自实际接口。模拟服务显示模拟模式、模型尚未配置，不代表真实问答验收通过。

若提示 5173 已占用，可能是已有前端在运行：先访问上面地址确认；不要终止未知进程或不断启动副本。前端固定端口且 strictPort=true，不会悄悄改端口。

## 验证

1. 点击“重新检查”，检查时间应更新。
2. 当前练习上传了 2 个片段时，向量记录应为 2；后续上传会改变它，不写死数量。
3. 点击“打开接口文档”，在新标签页打开后端 Swagger。
4. 缩窄窗口，确认内容仍可读、按钮可用。
5. 可选：在后端窗口 Ctrl+C 后重新检查，预期显示连接失败；然后在同一后端窗口重新运行启动脚本，再点重新检查，预期恢复。只需正常停止进程，不删除文件或数据。

## 连接方式

浏览器通过 `/api/health` 向 Vite 发请求，Vite 开发代理转给 `http://127.0.0.1:8000`。前端端口 5173，后端端口 8000。这个代理只用于开发；最终发布时由 Nginx 接替，不能把 Vite dev 当作正式发布。

## 打包

执行位置：frontend 目录。

```powershell
npm.cmd run build
```

成功后生成 dist/，不提交 node_modules/ 和 dist/。该命令只验证构建，不能替代浏览器交互验收；独立静态预览也不会自动获得开发代理。

## 本课独立练习

不用背代码，试着解释：浏览器为什么访问 5173，而后端日志里仍然出现 8000 的请求？反馈首页截图和你的理解即可。

参考：[Vite 官方入门](https://vite.dev/guide/)、[Element Plus 官方快速开始](https://element-plus.org/en-US/guide/quickstart.html)。
