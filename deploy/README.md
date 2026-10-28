# 本地部署包

当前完整前后端共用一个地址，登录、流式问答、文件和静态资源无需另配代理。每个人使用自己的数据目录、账号和API密钥，不复制开发电脑的用户数据库。

## 方式一：Docker（Windows/macOS/Linux）

先安装Docker与Docker Compose，在项目根目录执行：

```sh
cp deploy/deploy.env.example deploy/deploy.env
# 编辑 deploy/deploy.env，填入自己的 DEEPSEEK_API_KEY
docker compose up --build -d
docker compose logs -f app
```

PowerShell复制命令为 `Copy-Item deploy/deploy.env.example deploy/deploy.env`。已有配置时不要覆盖。

首次会构建依赖并下载约5GB模型，受网络速度影响；下载和本地索引不调用付费问答。看到Uvicorn启动后打开 http://localhost:8080/ 。注册自己的账号即可使用，内置“部署示例资料”可立即测试；真实问答按自己的API账号计费。

模型缓存保存在 `runtime/models`，数据在 `runtime/docker-data`。停止使用 `docker compose down`；再次启动 `docker compose up -d`，保留缓存与数据。不要删除runtime目录来升级。

只体验界面和模拟问答、不使用密钥或下载模型：

```sh
docker compose run --rm --service-ports app python deploy/run.py --demo --data-dir /data/demo --models-dir /models --host 0.0.0.0 --port 8000
```

模拟模式需先完成镜像构建；不要与已经占用8080的正式实例同时运行。模板答案不代表真实数学解答质量。

## 方式二：Windows预构建ZIP

安装Python3.12。解压发布包后，在MathRAG目录运行：

```powershell
Copy-Item deploy/deploy.env.example deploy/deploy.env
# 编辑配置，填入自己的密钥
./deploy/setup.ps1
```

脚本使用独立 `.venv-deploy`，不覆盖其他Python环境。ZIP已带前端构建产物，因此不需Node.js；首次仍需安装Python依赖和下载向量/重排模型。源码克隆不带dist，脚本会要求Node.js24并自动构建前端。

不带密钥的模拟体验：`./deploy/setup.ps1 -Demo`。实际入口均为 http://localhost:8080/ ，关闭启动终端停止服务。

Windows原生方式若还需要公式识别：另建 `.venv-formula`，安装 `backend/requirements-formula.txt`，在deploy.env中设 `OCR_FORMULA=rapid_latex`；启动器自动下载公式权重。Docker已配置隔离公式环境。缺少公式模型时界面会明确警告，不能把普通文字OCR当作公式准确识别。

## 资料和边界

- 默认只带新编写的数学示例，不携带开发者私人172份数据库、账号、标签或历史对话。可在网页上传自己的资料。
- 仓库knowledge/raw另有团队语料及来源说明；并非完整私有数据库，不自动恢复旧向量快照或映射旧账号。
- 约16GB内存更适合本地双模型；Docker建议分配至少8GB，磁盘预留约15GB，首次下载需联网。
- 只有首次模型缓存准备需要下载；真实大模型问答仍需联网。不是完全离线大模型应用。
- Docker只将8080绑定本机，不是公网服务器发布。当前电脑未安装Docker，未声称镜像已在本机实跑；已用解压包的独立数据目录验证模拟启动、注册、资料、静态页面及SSE。
- 真实模式使用部署者自己的密钥与账单，不携带开发电脑的预算额度。设置文件不会打进ZIP或Git。

构建发布ZIP：先构建frontend，再运行 `python scripts/build-deployment-package.py`，输出dist/下ZIP及SHA-256清单。模型不塞进Git历史，通过首次自动下载和本地缓存复用。
