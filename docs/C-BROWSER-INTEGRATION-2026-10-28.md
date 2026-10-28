> 本轮浏览器联调已由用户确认通过，详见[C-CURRENT-STATUS.md](C-CURRENT-STATUS.md)。下方首次启动时的pending及70次额度是历史快照，不再作为当前待办。

# C本机真实联调（2026-10-28）

当前已启动独立联调页面：**http://localhost:5174/**。后端为`127.0.0.1:8002`，仅本机开放。原C工作区、原演示数据及服务没有切换；当前服务运行`codex/c-main-integration`的整合代码。

## 本轮结果

- 本地BGE-M3、1024维向量及本地重排实际加载，混合检索/重排失败时禁止继续付费生成。
- 171份团队资料恢复到独立目录，2519切片/向量ID及账号归属一致。通过A接口重建洛必达、重要极限两份勘误，核对内容和版本。
- 通过真实前端代理验证登录、CSRF、未登录资料访问受限、预览及原文；四次真实问答均正常结束，两个真实追问正确关联首轮。AI数学复核通过，h012是等价表述，不是独立证明。
- 四份回答公式渲染错误0；启动/预算/勘误相关26项测试通过（1条依赖警告）。此前整合的370项全量与37项前端测试保留，本轮没有无故重跑全量。
- 累计70/100次，费用保守预留上界**0.4497072美元**，授权1美元；单次4096总输出Token、低强度思考、自动重试0、推荐无额外模型调用。页面继续可用，后续提问也受持久化账本保护。
- 接口文档改走当前页面的`/docs`代理，已核对页面、Vue编译、接口文档、OpenAPI及健康检查HTTP 200。

## 现在只做一个浏览器复核

打开上述地址，用账号`c_integration`登录。密码仅在本机`%LOCALAPPDATA%/Temp/mathrag-c-integration-20261028/browser-account.json`中，未提交Git；教师会在聊天中提供本次专用测试密码。

选择“数学真实联调资料”，打开历史中“判断 f(x)=x^2+2x 的单调性”的会话，检查已保存的首题、追问、公式显示与引用的“查看原文”。读取已有记录不新增模型调用。用户确认前，浏览器验收标记pending，不冒称已验收。

## 运行与恢复

数据与实时预算位于`%LOCALAPPDATA%/Temp/mathrag-c-integration-20261028`；旧`.tmp/c-demo`及B验证目录保持原样。密钥仅隐藏输入进入后端内存，不落文件；重启后需再次隐藏输入，不在命令参数中携带密钥。

在隔离worktree根目录启动后端：

```powershell
..\..\.venv\Scripts\python.exe -X utf8 scripts/start-c-integration.py --port 8002 --data-dir "$env:LOCALAPPDATA\Temp\mathrag-c-integration-20261028" --embedding-dir '..\b-final-models\bge-m3' --reranker-dir '..\b-final-models\bge-reranker-v2-m3' --prompt-key
```

前端在该worktree的frontend目录启动：

```powershell
$env:MATHRAG_FRONTEND_PORT='5174'
$env:MATHRAG_API_TARGET='http://127.0.0.1:8002'
$env:MATHRAG_LAN_HOST='localhost'
npm.cmd run dev
```

当前服务已经运行，不要重复启动。启动前检查端口，遇占用不杀未知进程。两种启动都只本机运行；未部署、未推送。不要重新运行快照恢复覆盖已有联调数据，也不要重跑已完成的付费smoke脚本；新增模型请求使用现有受控页面。

完整证据见[本轮记录](../eval/validation/2026-10-28-c-integration/README.md)。启动与预算源码提交为`d8dabc4`；后续前端代理修正及本记录另作本地提交。
