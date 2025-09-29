# 使用说明

## 环境准备
- Python 3.8+
- Docker / Podman / Nerdctl（可选，但推荐至少安装一个容器后端）
- Windows 用户建议使用 WSL2 + Ubuntu 20.04+（WSL2 支持 Docker Desktop 或 Podman）
- Linux 用户建议安装 Docker 或 Podman
- Mac 用户建议安装 Docker Desktop 或 Podman
- 本地运行时不做容器隔离，适合无容器环境的回退/开发调试

## 自动选择运行时
由 `sandbox/execution_layer/runtime_factory.py` 控制：
- 优先级：Docker → Podman → Nerdctl → Local
- 可通过config.py中的 SANDBOX_RUNTIME 常量强制指定运行时

## 启动 API 服务
- Linux / Mac
```bash
./scripts/start_api.sh             # 自动创建 .venv 并安装依赖后启动
```
