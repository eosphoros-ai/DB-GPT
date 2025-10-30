import docker

# 镜像与容器名配置
IMAGE_NAME = "python-vnc-gpu"
CONTAINER_NAME = "vnc-gpu-demo"

# Dockerfile 内容
DOCKERFILE_CONTENT = """
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖和 VNC/图形组件
RUN apt-get update && apt-get install -y --no-install-recommends \\
    x11vnc \\
    xvfb \\
    fluxbox \\
    novnc \\
    websockify \\
    wget \\
    net-tools \\
    xterm \\
    dos2unix \\
    pciutils \\
    gnupg2 \\
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 NVIDIA GPU 工具（如 nvidia-smi）
RUN apt-get update && apt-get install -y nvidia-utils-525 || true

# 设置 VNC 密码
RUN mkdir -p /root/.vnc && \\
    x11vnc -storepasswd 123456 /root/.vnc/passwd

# 拷贝启动脚本
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh && dos2unix /startup.sh

EXPOSE 80 5900

CMD ["/startup.sh"]
"""

# 启动脚本内容
STARTUP_SCRIPT = """#!/bin/bash

Xvfb :0 -screen 0 1280x960x24 -listen tcp -ac +extension GLX +extension RENDER &

export DISPLAY=:0

fluxbox &

x11vnc -display :0 -forever -shared -rfbauth /root/.vnc/passwd -rfbport 5900 &

websockify --web=/usr/share/novnc 80 localhost:5900
"""

# 写入 Dockerfile 和 startup.sh
with open("Dockerfile", "w") as f:
    f.write(DOCKERFILE_CONTENT)

with open("startup.sh", "w") as f:
    f.write(STARTUP_SCRIPT)

# 获取 Docker 客户端
client = docker.from_env()

# 构建镜像
try:
    client.images.get(IMAGE_NAME)
    print(f"✅ Image '{IMAGE_NAME}' already exists, skipping build.")
except docker.errors.ImageNotFound:
    print("🔧 Building Docker image...")
    image, logs = client.images.build(path=".", tag=IMAGE_NAME)
    for line in logs:
        if "stream" in line:
            print(line["stream"], end="")
    print(f"\n✅ Image '{IMAGE_NAME}' built successfully!")

# 启动容器
try:
    container = client.containers.get(CONTAINER_NAME)
    if container.status != "running":
        print(f"🔄 Container '{CONTAINER_NAME}' exists but not running. Restarting...")
        container.start()
    else:
        print(f"✅ Container '{CONTAINER_NAME}' is already running.")
except docker.errors.NotFound:
    print(f"🚀 Starting new container '{CONTAINER_NAME}'...")
    try:
        container = client.containers.run(
            IMAGE_NAME,
            name=CONTAINER_NAME,
            ports={
                "80/tcp": 6080,
                "5900/tcp": 5900,
            },
            detach=True,
            tty=True,
            device_requests=[
                docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
            ],
        )
        print(f"✅ Container '{CONTAINER_NAME}' is now running.")
    except docker.errors.APIError as e:
        print(f"❌ Error starting container: {e}")

print("👉 Access GUI via browser: http://localhost:6080/vnc.html (Password: 123456)")
