# DB-GPT Sandbox Agent 架构

本项目实现了一个可扩展的多容器/本地沙箱执行框架，支持 Python、Shell、Node.js 等多语言代码的有状态执行，统一接口、插件化扩展、依赖安装、环境变更等能力。

- 多运行时：Docker、Podman、Nerdctl、本地进程（Local）。
- 统一抽象：会话生命周期、代码执行、状态查询、依赖安装（可选）。
- 有状态：同一会话内多次执行共享环境，安装的依赖后续可用。
- 配置选择：默认 LocalRuntime；通过环境变量/创建参数显式选择容器后端，不可用时报错，不回退本地。
- 插件化：新增语言/依赖管理/沙箱类型时，仅需最小改动，接口清晰。

## 分层设计

- sandbox/execution_layer（执行层）
  - base.py：统一抽象（SandboxRuntime、SandboxSession、ExecutionResult、SessionConfig）
  - docker_runtime.py / podman_runtime.py / nerdctl_runtime.py / local_runtime.py：具体运行时实现
  - runtime_factory.py：创建参数 > SANDBOX_RUNTIME > Local；显式配置的容器初始化失败时报错
  - utils.py：资源、路径、进程、安全、环境检测工具
- sandbox/control_layer（控制层）
  - control_layer.py：跨任务会话管理、依赖安装、执行调度、状态查询
- sandbox/display_layer（显示层）
  - display_layer.py：DisplayResult 用于容器型运行时的结果封装（包含 GUI / 文件 等）
- sandbox/user_layer（用户层）
  - service.py/schemas.py：对外 API 统一调度，面向产品接口

注意：LocalRuntime.execute 返回 ExecutionResult；容器运行时返回 DisplayResult。若需在控制层统一结果，可在控制层进行适配（将 DisplayResult 映射为 ExecutionResult 或在 API 层做多态支持）。

## Agent 工具接入

主 Agent 和子 Agent 共用工具工厂，通过 dbgpt-app 的 tools/_execution.py 选择运行时、
创建会话、执行一次、规范化结果、回收文件并清理会话。数据分析保留原有 runner 接口。

Docker 使用归档传输显式输入和工作目录，回收普通文件时校验路径并拒绝链接越界。
Local 使用当前 Python 解释器，环境变量仅传给子进程，不修改服务进程的 os.environ。
Agent Python 保持原先接受任意 Python 的行为，不启用与其前置代码冲突的字符串黑名单；
其他 Local 会话的默认代码检查保持不变。本地执行不是安全隔离。

Local 是默认值而非故障兜底。显式配置容器后端时，运行时/会话创建或输入传输失败
均返回错误，不在宿主机执行代码；执行、超时、取消或产物回收失败也不会切换后端重试。

## 会话与有状态依赖

- 会话（SandboxSession）在 start 后进入活跃状态（is_active=True），同一会话内：
  - 多次 execute 共享同一环境/容器实例
- 运行时负责具体的依赖安装策略：
  - Python：pip install --no-input --disable-pip-version-check
  - JavaScript：npm init -y + npm install 包

## 支持语言

- Docker/Podman/Nerdctl：python、python-vnc、bash、javascript、java、cpp、go、rust
- Local：运行时探测系统可用语言，至少保证 python

## 安全与资源

- 超时、内存限制（容器通过参数、Local 通过 psutil 监控）
- 安全检查（SecurityUtils.validate_code）对常见危险操作进行告警
- 网络可禁用（network_disabled），适配安全隔离场景
