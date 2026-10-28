# 第 1 天 · 注册、登录与退出

已实现：真实注册登录、一天有效的可撤销会话、刷新恢复登录、退出撤销、文档与问答接口权限。公共资料游客问答会在下一阶段接入，目前未登录不能调用原有个人问答接口。

## 学生操作

1. 找到运行后端、不断输出 INFO 日志的 PowerShell 窗口，按 Ctrl+C。等出现 `PS ...>` 提示符再输入命令。
2. 同一窗口执行：

   ```powershell
   .\scripts\start-c-demo.ps1
   ```

   预期：重新出现 `Uvicorn running on http://127.0.0.1:8000`。窗口位置应仍是 RAG 根目录；否则先执行 `Set-Location -LiteralPath 'D:\我的文档\文档\ChatGPT\codex学习\RAG'`。

3. 刷新 http://127.0.0.1:5173/ 。前端会自动更新，无需重复启动。若服务没开，再在另一个终端从 frontend 目录运行 `npm.cmd run dev`。
4. 在“账号与个人空间”点击“创建账号”，填写一个新的用户名和自己保存的练习密码。用户名 3–32 位中文、字母、数字或下划线（英文字母不区分大小写），密码 8–128 位，确认密码相同。
5. 创建后应显示用户名和“已登录”。刷新页面，仍应显示已登录。
6. 点击“检查我的文档权限”，新账号通常显示 0 份，正常。之前 dev 用户上传的资料没有被删除，也没有自动转移给新账号。
7. 退出登录，再用错误密码尝试，应显示“用户名或密码错误”；使用正确密码应可重新登录。不要把密码、Cookie 或接口返回的 csrf_token 发到聊天。

常见错误：看到“后端尚未载入账号接口”表示旧后端还没重启；若数据库迁移失败，不要删除数据库，保留错误反馈。频繁测试触发限流时等一分钟，不要重装依赖。

## API 与实现

沿用统一 `{code, message, data, request_id}` 响应。

| 方法与路径 | 输入 | 成功结果 |
|---|---|---|
| POST /api/auth/register | JSON username/password | 创建账号并登录，返回 user/csrf_token |
| POST /api/auth/login | JSON username/password | 登录，返回 user/csrf_token |
| GET /api/auth/me | 浏览器会话 Cookie | user/csrf_token；未登录或过期 401 |
| POST /api/auth/logout | Cookie + X-CSRF-Token | 撤销服务器会话、清 Cookie |

个人文档与原有问答接口现在必须登录；已登录的修改请求需带 X-CSRF-Token。前端请求通过开发代理，Cookie 自动携带。Swagger 修改请求同样需要 CSRF 校验，旧的免登录上传操作不再适用。

- 密码采用随机盐 PBKDF2-HMAC-SHA256，600,000 次迭代，不存明文；验证参考 [OWASP 密码存储指南](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)。
- 本轮使用随机服务器会话，不使用 JWT：数据库仅存会话凭据的 SHA256 摘要，注销能立即撤销。登录凭据置于 HttpOnly、SameSite=Lax Cookie，不写 localStorage。
- CSRF token 只用于请求校验，不是登录凭据；从登录或 /me 响应获取，前端只存在内存。
- 会话默认 86400 秒；AUTH_SESSION_SECONDS 可配置。HTTP 本机模式使用非 Secure Cookie；未来 HTTPS 部署需要 AUTH_COOKIE_SECURE=true。
- 单进程本机模式按来源 IP 限制注册/登录 20 次/分钟；不是跨进程或公网生产防护方案。
- 不支持 dev:<name> 身份切换。旧 A/B 测试仅在测试夹具中注入旧身份，其业务断言保留；新增鉴权测试没有注入，APP_ENV=test 也不会启用运行时绕过。

## 数据库迁移与恢复

新数据库直接创建 users.password_hash 和 auth_sessions。旧数据库在服务启动时先用 SQLite backup API 制作一致性快照（包括 WAL 中已提交数据），然后仅追加可空 password_hash；第二次启动不重复迁移或覆盖快照。旧账号没有密码，既不能登录也不能被注册抢占。

模拟服务快照目录为 `.tmp/c-demo/backups/`，其他数据库位于其同级 `backups/`。每份备份使用时间和随机标识构造新文件名。迁移不改文档、向量或原始文件。

若需恢复旧数据库：先停止服务，列出要恢复的快照、当前库和关联 WAL/SHM 的准确路径；另做当前状态备份，再经确认执行恢复。不要自行覆盖数据库或删除其 WAL 文件。还原旧代码后才使用旧结构，不能一边运行服务一边复制覆盖数据库。

## 验证结果

账号、迁移自动化测试与原 A/B 回归共 **98 passed，0 failed，0 skipped，1 条已知 AnyIO 弃用警告**；包括保持 WAL 连接时的已提交数据备份验证。HTTP 层另用 `.tmp/auth-http-smoke` 隔离数据实际验证注册、会话恢复、受保护接口、CSRF、退出、错误密码及再次登录；该临时服务已停止。

前端生产打包通过。浏览器中的布局、表单与刷新效果仍需学生按上面步骤验收；用户当前后端进程未由教师停止或替换。

## 本课学习点

登录页面负责收集输入；后端负责验证身份和限制数据访问。页面上显示“已登录”只是结果，能否访问个人资料最终由后端决定。
