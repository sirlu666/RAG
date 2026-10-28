# 本机 Nginx、日志与回滚

更新：2026-10-28。仅供本机使用，不涉及远程部署。

## 当前状态

- 开发页面仍为 http://localhost:5174/，受累计预算保护的后端仍为 http://127.0.0.1:8002。
- 本次未重启这两个服务。前端开发入口会热更新；后端历史推荐字段需后续受控重启才生效，旧进程不会自行加载 Python 改动。实时推荐、图片识别使用已存在的接口，可直接使用。
- `8086` 检查时未监听；未在 PATH 和常见安装目录发现 Nginx，没有安装、启动 Nginx，不能声称配置语法或代理链路已经实机验证。

## 启动准备与配置

配置：`deploy/nginx-local.conf`。绑定 `127.0.0.1:8086`，静态根目录为当前工作区 `frontend/dist`，API 转发到 `8002`。SPA 回退只用于静态页面；API 错误不回退 HTML。保留带端口的 Host，以兼容 Cookie 与同源 CSRF 校验。

流式设置：HTTP/1.1、关闭代理缓冲/请求缓冲/缓存/压缩、600 秒代理读写超时。上传入口上限 55MB（包含 multipart 开销），后端仍执行各自大小限制，题图为 10MB。静态内容设置 no-cache，API 设置 no-store。

以后本机已有 Nginx 时，在当前工作区根目录执行（先将路径替换为实际 nginx.exe）：

```powershell
$nginxExe = 'C:\tools\nginx\nginx.exe'
$prefix = (Get-Location).Path.Replace('\', '/') + '/'
New-Item -ItemType Directory -Path './logs' -Force | Out-Null
# frontend/dist 应为本次 npm.cmd run build 的产物。
Get-NetTCPConnection -State Listen -LocalPort 8086 -ErrorAction SilentlyContinue
& $nginxExe -p $prefix -c deploy/nginx-local.conf -t
# 仅在 -t 通过、端口空闲、8002 健康时启动。
Start-Process -FilePath $nginxExe -ArgumentList @('-p', ('"' + $prefix + '"'), '-c', 'deploy/nginx-local.conf') -WindowStyle Hidden
```

访问 http://localhost:8086/；保留原 5174 入口。先检查首页、刷新深层路径、`/api/health` 与登录，再以浏览器拦截的测试 SSE 验证事件逐段到达。真实流式反代验收若需模型调用，仍使用同一本账本，不能另起带密钥的普通 uvicorn。

配置变更后先 `-t`，再执行：

```powershell
& $nginxExe -p $prefix -c deploy/nginx-local.conf -s reload
```

## 日志

- `logs/mathrag-access.log`：方法、无查询串的路径、状态码、响应大小和耗时，不记录请求头、Cookie 或正文。
- `logs/mathrag-error.log`：Nginx warn 级别错误；不要开启 debug。Nginx 内部错误可能包含请求上下文，因此也按本机私有日志保管，不直接上传原文件。
- 后端启动/异常信息沿用现有启动终端；本次没有迁移日志或重启进程。
- 预算与用量仍在 `%LOCALAPPDATA%\Temp\mathrag-c-integration-20261028\budget.json` 和 `usage.jsonl`，不重置、不删除、不复制密钥。日志不提交 Git；需归档时先关闭/重开日志文件并检查敏感内容。

## 停止与回滚

只停止由本配置启动且命令行/端口核对一致的 Nginx：

```powershell
& $nginxExe -p $prefix -c deploy/nginx-local.conf -s quit
```

随后继续使用 5174。不要依据旧 PID 结束任何进程。配置变更前保留配置及上一个 `frontend/dist`，回滚时恢复这些文件并校验配置；不要对整个 `.tmp` 做清理。

本批代码基点为 `2dc2add`，通过 `git log` 定位本批功能提交。后续若需源码回滚，在保存新增工作后使用针对该提交的 `git revert`，不使用 reset/clean 覆盖工作区；前端重新构建。该批没有数据库迁移，回滚不涉及数据库、上传文件、Chroma 或预算账本。

若确需加载新版后端：先核对 8002 的进程命令和启动终端，安排停止后，在同一工作区按 `C-NEW-CHAT-HANDOFF.md` 的受控启动命令恢复，使用相同数据和模型目录，密钥只在本机隐藏输入。新聊天或重启不能重新计费起算。
