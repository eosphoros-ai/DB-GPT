# 使用说明

## 环境准备
- Python 3.8+
- Docker / Podman / Nerdctl（默认运行模式需要至少安装一个容器后端）
- Windows 用户建议使用 WSL2 + Ubuntu 20.04+（WSL2 支持 Docker Desktop 或 Podman）
- Linux 用户建议安装 Docker 或 Podman
- Mac 用户建议安装 Docker Desktop 或 Podman
- 本地运行时不做容器隔离，仅适合可信开发调试；需要显式设置 `SANDBOX_RUNTIME=local`

## 自动选择运行时
由 `sandbox/execution_layer/runtime_factory.py` 控制：
- 默认 `SANDBOX_RUNTIME=auto`，优先级：Docker → Podman → Nerdctl
- 如果没有可用容器后端，默认会启动失败，避免静默退回宿主机执行
- 可通过环境变量 `SANDBOX_RUNTIME=docker|podman|nerdctl|local` 强制指定运行时

## 启动 API 服务
- Linux / Mac
```bash
./scripts/start_api.sh             # 自动创建 .venv 并安装依赖后启动
```
