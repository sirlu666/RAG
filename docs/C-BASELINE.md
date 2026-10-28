# Windows 本机基线

日期：2026-10-23。原始提交 a43d959；工作分支 codex/c-platform。未推送远程。

## 环境

- Windows PowerShell，项目路径含中文；使用明确引号及 LiteralPath。
- 已有 Python 3.12.4，项目虚拟环境 .venv；保留系统 Python 3.9.7。
- CPU：i5-13500H；内存约 15.7 GB。
- 包与缓存位于 D 盘，未下载 BGE 或重排模型权重。
- Python 3.12 静态语法检查：backend/app 与 backend/tests 共 47 个文件通过。

## 安装与复现

仅在没有虚拟环境时创建，不覆盖已有环境：

```powershell
# 执行位置：项目 RAG 根目录；环境已由教师创建，无需重复运行。
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install --cache-dir .tmp\pip-cache -r backend\requirements.txt
```

初次未带 -X utf8 时，pip 24.0 使用 GBK 读取中文注释并报 UnicodeDecodeError；改用 UTF-8 命令后继续。不改 requirements.txt 或系统编码。

## 测试

执行位置：RAG/backend。

```powershell
..\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

测试夹具显式使用 backend/tests/.pytest_data、哈希向量、模拟回答及无重排模式。不要在该测试临时目录保存个人数据。测试不调用真实付费问答 API，也不能证明实际模型质量。

实测结果：**80 passed，0 skipped，0 failed，1 warning，6.78 秒**。警告是 Starlette 测试客户端使用了 AnyIO 的弃用别名，不影响本次通过；没有为消除警告修改 A/B 代码。

安装完成后 `python -m pip check` 返回 `No broken requirements found`。当前 Windows 环境的具体依赖版本保存于 `requirements-windows-baseline.txt`（基线快照，不代表跨平台通用锁文件）。

## 启动隔离模拟 API

执行位置：RAG 根目录。

```powershell
.\scripts\start-c-demo.ps1
```

预期：访问 http://127.0.0.1:8000/docs 可见交互文档；GET http://127.0.0.1:8000/api/health 返回信封，data.db 为 up、data.llm.mock 为 true。初始库为空时 vectors 为 0 正常。

该脚本仅监听 127.0.0.1；强制使用 .tmp/c-demo 独立数据和模拟模型，不读写真实 data，也不改 .env。启动后会等待请求，这是正常现象。Ctrl+C 停止，脚本在退出时恢复当前进程的环境变量。脚本未开启公网访问。

若端口占用，先检查占用者，不结束未知进程；可用 `-Port 8010`，同时把访问地址改为 8010。若脚本被执行策略阻止，反馈错误，不修改全局策略。

HTTP 冒烟验证：通过。使用相同的模拟/隔离原则，在随机空闲的回环端口启动 Uvicorn，`/api/health` 返回 code=0、db=up、mock=true、configured=false、vectors=0；`/docs` 返回 HTTP 200。验证进程已停止，没有遗留服务器。启动脚本已通过 PowerShell 语法解析；HTTP 检查使用了直接 Uvicorn 子进程，未逐项执行交互脚本。两者用于不同的 .tmp 子目录，不写真实 data。

## 当前交付边界

这是开发环境与测试基线，不是 C 功能交付。真实模型调用、语料索引、登录、前端、图片问答等仍需按 C-DELIVERY.md 实现与验收。
