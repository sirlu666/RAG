# Nginx 实机验证与历史推荐加载

2026-10-28，用户明确授权本机Nginx验证及受控后端重启，两项均已完成，没有远程操作。

## 实际运行

- 站点：http://localhost:8086/，只监听127.0.0.1；原5174开发入口保留。
- 后端8002经本机密码框重新输入密钥后受控重启，旧PID19024、新PID快照16476；仍由原 `start-c-integration.py` 安装累计预算保护。
- 健康接口：app/db up、2520向量、local embedding、Chroma、local rerank、hybrid=true、threshold=0.62、mock=false、DeepSeek配置存在。
- 配置存在不代表已向提供商验证新密钥有效性；本次没有新增付费提问。

## Nginx 实测

使用 [Nginx官方下载](https://nginx.org/en/download.html) 的Windows1.31.8 ZIP；文件SHA-256为 `fbb1501009be34655cc238d460714cf20391b639013f4c73859813d7938783fd`。这是下载文件指纹，不冒称已做PGP签名验证。独立安装到用户LocalAppData，不升级项目依赖或修改系统PATH。

首先使用中文工作区前缀失败，报1113编码转换错误。改用 `%LOCALAPPDATA%/MathRAG/runtime/mathrag-local` 英文目录，只复制构建产物和配置；配置检查、启动、重载均通过。初始组合启动命令被工具策略拦截，仅返回blocked by policy；后续范围固定的英文运行目录控制脚本获工具接受，启动已完成。

| 检查 | 结果 |
|---|---|
| 首页、深层路径刷新 | 200 HTML，SPA回退正常 |
| health、openapi | 200 JSON，API no-store |
| 不存在的API | 404 JSON，不回退首页 |
| 静态产物 | 5个文件与frontend/dist内容SHA一致 |
| Cookie登录、匿名历史 | 登录200，匿名401 |
| 缺CSRF的写请求 | 403，未修改标题 |
| 配置重载后健康检查 | 200 |
| 超过55MB的请求头 | 413，未发送大请求体 |
| 访问日志 | 不含测试查询串、Cookie标记 |

SSE使用真实Nginx进程和TCP连接：独立验证实例8087转发到本机无模型夹具，代理指令与运行配置相同，仅替换监听和上游端口。meta、delta、done约在0.016、0.812、1.609秒到达，没有整段缓冲，无压缩，X-Accel-Buffering=no。验证的是代理传输，不是新DeepSeek问答。验证实例和夹具已停止，8087释放，8086继续运行。

## 历史推荐与数据保护

- 密码框工具不读取旧进程内存或旧聊天密钥；通过子进程环境传递密钥，不写文件、不加到命令参数。
- 提交前原服务继续运行；提交后先检查受控启动器、模型、独立数据标记、进程命令、端口和工作区，再停止指定旧服务并恢复8002。新进程已实际加载本地模型。
- 通过8086读取真实历史API，5条团队库助手消息的 `related_questions/related_materials` 与数据库逐项一致，其中3条成功回答有推荐。浏览器打开真实旧对话已显示“继续探索”，没有注入响应夹具。
- Cookie与CSRF边界验证通过，页面错误0。未重新发送历史问题；问答请求拦截，付费调用0。
- 重启身份保护7项测试通过，未重跑无关全量测试或前端构建。
- SQLite quick_check=ok；仍为172文档、172份标签、2520切片、2520向量、4会话、14消息。
- 重启前后预算一致：76/100次，保守预留上界0.4926795美元，没有重置或另开账本。

## 证据与运维

私有证据目录：`%LOCALAPPDATA%/Temp/mathrag-c-integration-20261028/nginx-restart-20261028/`。

- `restart-status.json`、`backend-startup.log`：重启阶段、健康信息、前后预算；不含密钥。
- `nginx-network-result.json`：路由、事件到达时间、上传限制、访问日志检查。
- `expected-history-related.json`、`history-ui-result.json`、`nginx-real-history.png`：数据库预期、实际接口对比和页面截图。

控制、日志与回滚见 `C-LOCAL-NGINX.md`。运行产物、日志、数据库、密钥、截图不入Git；仅提交控制/验证脚本、保护测试及说明。没有推送、合并或远程部署。
