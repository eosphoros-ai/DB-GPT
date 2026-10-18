---
id: runtime
title: Sandbox 运行时配置
sidebar_position: 1
description: 配置 DB-GPT Agent 执行使用的 LocalRuntime 和容器运行时。
---

# Sandbox 运行时配置

本文说明 DB-GPT 应用侧 Python 和 Shell Agent 工具使用的运行时选择方式。主 Agent 和子
Agent 共用以下执行入口：

- packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/_execution.py
- packages/dbgpt-sandbox/src/dbgpt_sandbox/sandbox/execution_layer/runtime_factory.py

## 运行时选择规则

运行时选择顺序如下：

1. 调用方显式传入的运行时参数。
2. SANDBOX_RUNTIME 环境变量。
3. 默认使用 LocalRuntime。

| 配置 | 使用的运行时 |
| --- | --- |
| 未设置、空值或 local | LocalRuntime |
| SANDBOX_RUNTIME=docker 且 Docker 可连接 | DockerRuntime |
| SANDBOX_RUNTIME=podman 且 Podman 可用 | PodmanRuntime |
| SANDBOX_RUNTIME=nerdctl 且 Nerdctl 可用 | NerdctlRuntime |
| 配置的容器运行时或会话无法初始化 | 报错，不在本地执行 |
| 未知的运行时名称 | 配置错误 |

即使机器已经安装 Docker，也不会自动启用 Docker。Docker 是显式选择的：

~~~bash
export SANDBOX_RUNTIME=docker
~~~

如果不设置这个环境变量，DB-GPT 使用当前应用环境执行，不需要 Docker 镜像。

LocalRuntime 是默认值，不是故障兜底。显式选择 docker、podman 或 nerdctl 后，
必须使用指定的后端。初始化、镜像拉取、容器创建或输入文件传输失败时，直接返回
错误，不会在宿主机上执行代码。该策略不需要额外的配置开关。

## LocalRuntime

LocalRuntime 是默认运行时，目的是保证 DB-GPT 启动后即可执行 Agent 工具。

本地模式下：

- Python 使用 DB-GPT 应用当前的 Python 解释器。
- 可以直接使用当前应用环境中已安装的 pandas、numpy 等依赖。
- Shell 命令在服务所在主机执行。
- 不需要 Docker 镜像。
- 本地模式不提供容器隔离，部署时应结合操作系统权限和网络策略进行控制。

也可以显式选择本地模式：

~~~bash
export SANDBOX_RUNTIME=local
~~~

## DockerRuntime

Docker 模式同时需要可连接的 Docker daemon 和可用的镜像。应用侧 Agent 执行器使用
SANDBOX_AGENT_IMAGE，默认值为：

~~~text
dbgpt-sandbox-agent:latest
~~~

仓库提供了一个 Agent 镜像构建文件，预装 code_interpreter 常用的数据分析依赖：

~~~bash
cd /path/to/DB-GPT
docker build -f packages/dbgpt-sandbox/src/docker_images/Dockerfile.agent -t dbgpt-sandbox-agent:latest packages/dbgpt-sandbox/src/docker_images
~~~

如果部署环境使用私有镜像仓库或需要额外系统依赖，可以指定其他镜像：

~~~bash
export SANDBOX_RUNTIME=docker
export SANDBOX_AGENT_IMAGE=registry.example.com/dbgpt/agent:2026-09
~~~

如果希望 Docker 模式具备与本地数据分析环境接近的能力，建议使用自定义 Agent 镜像。
python:3.11-slim 这类基础镜像可以运行基础 Python 和 Shell，但默认不包含 pandas、
numpy、matplotlib、Excel 依赖以及所有 Agent 工作流可能需要的系统命令。

## 执行生命周期

当前应用侧 Agent 集成为每次 Python 或 Shell 工具调用创建一个短生命周期执行 session：

1. 选择运行时。
2. 创建 session；Docker 模式下同时启动容器。
3. 按需把工作目录和显式输入文件传入容器。
4. 执行 Python 代码或 Shell 命令。
5. 把普通输出文件和生成的产物回收到宿主机。
6. 销毁 session 并删除容器。

因此，Agent 工具调用结束后看不到容器是正常现象。宿主机工作目录中的文件可以在后续
调用中继续使用，但短生命周期容器中安装的依赖不会跨调用保留。需要长期存在的依赖应
预装到 Agent 镜像中。

每次工具调用成功创建会话后、执行代码前，会以 INFO 级别记录实际使用的运行时：

~~~text
Sandbox execution: runtime=docker language=python session_id=agent_...
~~~

这是每次工具调用的执行日志，不是项目启动日志；运行时或会话初始化失败时不会输出
该日志。

如果配置的容器运行时、镜像拉取、session 初始化或输入文件传输失败，工具会返回
错误，不会在本地执行用户代码。代码已经开始执行后的错误、超时、取消或产物回收
失败，也不会切换到其他运行时重跑。

## 文件和工作目录

应用执行器会在 DB-GPT 配置的临时目录下维护当前会话的宿主机工作目录。Docker 模式会
把工作目录和显式输入文件传入容器，执行结束后再回收普通文件。

如果存在，以下变量会传递给子进程：

- PLOT_DIR
- FILE_PATH
- FILES_JSON

容器不会自动获得宿主机的完整文件系统。需要执行的文件必须通过工作目录或显式输入文件
机制传入。

## 验证

不依赖 Docker 的运行时和应用测试：

~~~bash
.venv/bin/python -m pytest packages/dbgpt-sandbox/tests packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/subagent/tests -q
~~~

构建 Agent 镜像后运行真实 Docker 测试：

~~~bash
DBGPT_TEST_DOCKER_IMAGE=dbgpt-sandbox-agent:latest .venv/bin/python -m pytest packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/test_execution_docker_integration.py -q
~~~

## 常见问题

### pull access denied for dbgpt-sandbox-agent

说明当前 Docker daemon 找不到配置的镜像，并且公共镜像仓库中也无法拉取该镜像。请
先构建仓库提供的镜像，或者把 SANDBOX_AGENT_IMAGE 改成 Docker daemon 可以访问的镜像。

### 配置的容器运行时不可用

检查选择的后端、daemon 连接、镜像和报错涉及的输入文件。工具会停止执行，不会悄悄
切换到宿主机执行。如果确实希望在本地执行，请主动设置 SANDBOX_RUNTIME=local 并
重启 DB-GPT；本地模式不提供容器隔离。

### docker ps 看不到容器

Agent 工具调用成功后会在清理阶段删除容器，所以这是正常现象。可以用下面的命令观察
容器的短生命周期：

~~~bash
docker events --filter type=container --format '{{.Time}} {{.Status}} {{.Actor.Attributes.name}}'
~~~

然后触发一个执行时间较长的工具调用。

### 已安装 Docker 但仍然使用本地运行时

确认启动 DB-GPT 服务的同一个 shell 环境中设置了 SANDBOX_RUNTIME=docker，修改环境变量
后重启服务。然后触发一次 Python 或 Shell 工具调用，检查其 INFO runtime 日志；
项目启动时不会打印这条日志。
