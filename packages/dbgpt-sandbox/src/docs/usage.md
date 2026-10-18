# 使用说明

## 环境准备
- Python 3.10+
- Docker / Podman / Nerdctl（可选，但推荐至少安装一个容器后端）
- Windows 用户建议使用 WSL2 + Ubuntu 20.04+（WSL2 支持 Docker Desktop 或 Podman）
- Linux 用户建议安装 Docker 或 Podman
- Mac 用户建议安装 Docker Desktop 或 Podman
- 本地运行时不做容器隔离，是未配置容器后端时的默认模式，适合开发调试

## 配置运行时

运行时统一由 RuntimeFactory 选择，优先级为：创建参数 > SANDBOX_RUNTIME 环境变量 > local。

| 配置 | 行为 |
| --- | --- |
| 未设置、空值或 local | 使用 LocalRuntime，即使机器上已安装 Docker |
| docker | Docker SDK 和 daemon 可用时使用 DockerRuntime |
| docker，但 SDK/daemon 不可用 | 报错并停止，不回退到 LocalRuntime |
| podman / nerdctl | 显式选择对应后端，不再自动探测并切换 |
| 显式配置的容器后端初始化或会话创建失败 | 报错并停止，不在宿主机执行代码 |
| 未知运行时名称 | 报配置错误，避免拼写错误被掩盖 |

LocalRuntime 是默认值，不是容器故障时的兜底。显式配置容器后端后，需修复连接、
镜像或输入文件问题才能执行；只有部署方主动改为 local 并重启服务，才会切换到本地。

不再需要 SANDBOX_ALLOW_LOCAL_RUNTIME；旧配置中的该开关不再控制本地执行。
本地模式沿用服务进程的权限，不提供容器隔离。运行时配置应由部署方设置，
不是聊天请求参数。本次运行时接入不替代接口认证和权限控制。

### Agent 工具使用 Docker

主 Agent、子 Agent 的 Python/Shell 工具，以及共享 Python runner 的数据分析工具，
统一经过 RuntimeFactory。默认本地模式使用服务当前的 Python 解释器及已安装依赖，
无需准备 Docker 即可执行。

Docker 模式需要包含数据分析依赖的镜像。在仓库根目录构建：

    docker build -f packages/dbgpt-sandbox/src/docker_images/Dockerfile.agent \
      -t dbgpt-sandbox-agent:latest packages/dbgpt-sandbox/src/docker_images

启动 DB-GPT 服务前配置：

    export SANDBOX_RUNTIME=docker
    export SANDBOX_AGENT_IMAGE=dbgpt-sandbox-agent:latest

SANDBOX_AGENT_IMAGE 可指向自定义镜像；镜像至少需要 Python、bash、pandas、numpy，
图表及 Excel 分析还需要 matplotlib、openpyxl 等。Docker 连接沿用 Docker SDK
的配置（例如 DOCKER_HOST）。修改环境变量后需要重启服务。

- 显式选择容器后端后，初始化、镜像拉取、容器创建或输入文件传输失败时，工具返回错误，
  不回退本地执行。
- 代码开始执行后，错误、超时、取消或文件回收失败均不会触发本地重跑。
- Docker 通过归档传输会话目录和显式输入文件，支持远程 daemon；不挂载宿主整个临时目录。
- 文件在容器中保留原路径，包括 FILE_PATH、FILES_JSON 及文件映射中的路径。
- 调用结束时将工作目录中的普通文件回收，保持图片及下载文件的现有协议。
- Agent 每次工具调用使用独立执行会话；工作目录文件保留，但容器内安装的临时依赖
  不跨调用保留。需要长期使用的依赖应放入镜像。
- Podman/Nerdctl 的 Agent 工作目录使用本机路径挂载，需能访问服务所在主机的文件。

每次工具调用成功创建会话后、执行代码前，会输出 INFO 日志：

    Sandbox execution: runtime=docker language=python session_id=agent_...

这不是项目启动日志；初始化或会话创建失败时不会输出该执行日志。

### 验证

基础测试不需要 Docker。真实容器测试显式指定已构建的镜像：

    DBGPT_TEST_DOCKER_IMAGE=dbgpt-sandbox-agent:latest .venv/bin/python -m pytest \
      packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/test_execution_docker_integration.py

## 启动 API 服务
- Linux / Mac
```bash
./scripts/start_api.sh             # 自动创建 .venv 并安装依赖后启动
```
