# 本机 Nginx、日志与回滚

更新：2026-10-28，实机验证和受控后端重启均已完成。仅供本机使用，不涉及远程部署。以本节最新状态为准，完整证据见 `C-NGINX-RESTART-VALIDATION-2026-10-28.md`。

## 实际运行与控制方式（最新）

- Nginx站点 http://localhost:8086/ 已运行，原5174开发入口保留；8002已受控重启并加载历史推荐字段。
- 已从官方独立下载Nginx Windows1.31.8，未修改项目依赖或全局PATH。可执行文件在 `%LOCALAPPDATA%/MathRAG/runtime/nginx-1.31.8/nginx.exe`。
- Windows版本不能直接读取中文工作区前缀，实测报1113。实际实例使用英文目录 `%LOCALAPPDATA%/MathRAG/runtime/mathrag-local/`，只复制构建产物和配置，静态root改为html，不复制数据库、上传文件或密钥。
- 实际日志是上述实例目录内的 `logs/mathrag-access.log` 和 `logs/mathrag-error.log`；后端启动日志与状态在独立联调目录 `nginx-restart-20261028/`。
- 配置检查、启动、重载、静态/API路由、Cookie/CSRF、真实TCP的SSE分段、上传限制和访问日志检查均已通过。下文未安装/未重启状态为历史记录。

当前worktree根目录使用：

```powershell
./scripts/local-nginx.ps1 -Action Check
./scripts/local-nginx.ps1 -Action Start
./scripts/local-nginx.ps1 -Action Reload
./scripts/local-nginx.ps1 -Action Stop
```

Check同步当前frontend/dist并检查配置；Start只在8086空闲时启动；Reload和Stop核对master身份后操作。本次已在运行，不必再Start。前端有新改动时先构建，再Reload。

以后确需重启后端，可启动本机隐藏密钥输入窗口：

```powershell
../../.venv/Scripts/pythonw.exe -X utf8 scripts/restart-c-integration-local.py
```

提交前旧服务继续运行；取消窗口不停止服务。提交后核对进程、端口、工作区和前置条件，通过原受控启动器恢复。密钥通过子进程环境传递，不写文件或命令参数。新聊天不重启、不重置预算。

## 当前状态

- 开发页面仍为 http://localhost:5174/，受累计预算保护的后端仍为 http://127.0.0.1:8002。
- 8002已受控重启，历史推荐字段及真实页面已验证；5174保留原进程。
- 8086 Nginx已运行，配置测试、重载及真实网络SSE验证通过。使用前述英文实例目录，不能直接用中文工作区作Nginx前缀。

## 启动准备与配置

配置：`deploy/nginx-local.conf`。绑定 `127.0.0.1:8086`，静态根目录为当前工作区 `frontend/dist`，API 转发到 `8002`。SPA 回退只用于静态页面；API 错误不回退 HTML。保留带端口的 Host，以兼容 Cookie 与同源 CSRF 校验。

流式设置：HTTP/1.1、关闭代理缓冲/请求缓冲/缓存/压缩、600 秒代理读写超时。上传入口上限 55MB（包含 multipart 开销），后端仍执行各自大小限制，题图为 10MB。静态内容设置 no-cache，API 设置 no-store。

以后本机已有 Nginx 时，在当前工作区根目录执行（先将路径替换为实际 nginx.exe）：

```powershell
./scripts/local-nginx.ps1 -Action Check
./scripts/local-nginx.ps1 -Action Start
```

访问 http://localhost:8086/；保留原5174入口。首页、深层路径、health及登录已验证，SSE以独立Nginx实例和真实网络夹具验证，不能以浏览器拦截代替反代测试。真实模型调用仍使用同一本账本，不能另起带密钥的普通uvicorn。

配置变更后先 `-t`，再执行：

```powershell
./scripts/local-nginx.ps1 -Action Reload
```

## 日志

- `logs/mathrag-access.log`：方法、无查询串的路径、状态码、响应大小和耗时，不记录请求头、Cookie 或正文。
- `logs/mathrag-error.log`：Nginx warn 级别错误；不要开启 debug。Nginx 内部错误可能包含请求上下文，因此也按本机私有日志保管，不直接上传原文件。
- 当前后端启动/异常信息写入本次重启目录的backend-startup.log。重启状态记录在同目录restart-status.json，路径见前述最新运行说明。
- 预算与用量仍在 `%LOCALAPPDATA%\Temp\mathrag-c-integration-20261028\budget.json` 和 `usage.jsonl`，不重置、不删除、不复制密钥。日志不提交 Git；需归档时先关闭/重开日志文件并检查敏感内容。

## 停止与回滚

只停止由本配置启动且命令行/端口核对一致的 Nginx：

```powershell
./scripts/local-nginx.ps1 -Action Stop
```

随后继续使用 5174。不要依据旧 PID 结束任何进程。配置变更前保留配置及上一个 `frontend/dist`，回滚时恢复这些文件并校验配置；不要对整个 `.tmp` 做清理。

本批代码基点为 `2dc2add`，通过 `git log` 定位本批功能提交。后续若需源码回滚，在保存新增工作后使用针对该提交的 `git revert`，不使用 reset/clean 覆盖工作区；前端重新构建。该批没有数据库迁移，回滚不涉及数据库、上传文件、Chroma 或预算账本。

若确需加载新版后端：先核对 8002 的进程命令和启动终端，安排停止后，在同一工作区按 `C-NEW-CHAT-HANDOFF.md` 的受控启动命令恢复，使用相同数据和模型目录，密钥只在本机隐藏输入。新聊天或重启不能重新计费起算。
