import docker

# 镜像与容器名配置
IMAGE_NAME = "vnc-gui-browser"
CONTAINER_NAME = "gui-browser"

# Dockerfile 内容
DOCKERFILE_CONTENT = """
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8
ENV DISPLAY=:0

# 安装基础依赖、桌面环境、VNC/noVNC、浏览器和中文字体
RUN apt-get update && apt-get install -y \
    python3 python3-pip xvfb x11vnc fluxbox xterm wget dos2unix \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    novnc websockify net-tools curl unzip firefox \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    fonts-noto-cjk fonts-wqy-zenhei fonts-wqy-microhei language-pack-zh-hans \
    libgtk-3-0 libdbus-glib-1-2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 geckodriver
RUN GECKODRIVER_VERSION=$(\
    curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest \
| grep "tag_name" | cut -d '"' -f 4) \
    && wget -q https://github.com/mozilla/geckodriver/releases/download/\
    $GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz \
    && tar -xzf geckodriver-*.tar.gz -C /usr/local/bin \
    && rm geckodriver-*.tar.gz

# 安装 Selenium
RUN pip3 install selenium

# 设置 VNC 密码
RUN mkdir -p /root/.vnc && \
    x11vnc -storepasswd 123456 /root/.vnc/passwd

# 拷贝启动脚本和 Selenium 示例
COPY startup.sh /startup.sh
COPY demo_selenium.py /demo_selenium.py
RUN chmod +x /startup.sh && dos2unix /startup.sh

EXPOSE 80 5900

CMD ["/startup.sh"]
"""

# 启动脚本内容
STARTUP_SCRIPT = """#!/bin/bash
set -e

# -----------------------------
# 函数：查找未被占用的 DISPLAY
# -----------------------------
find_free_display() {
    for i in $(seq 0 99); do
        if [ ! -e "/tmp/.X${i}-lock" ]; then
            echo ":$i"
            return
        fi
    done
    echo ":1"
}

# -----------------------------
# 清理遗留锁文件
# -----------------------------
cleanup_locks() {
    echo "[INFO] Cleaning up old X lock files..."
    rm -f /tmp/.X*-lock || true
}

# -----------------------------
# 启动服务
# -----------------------------
start_services() {
    DISPLAY_ID=$(find_free_display)
    export DISPLAY=$DISPLAY_ID
    echo "[INFO] Using DISPLAY=$DISPLAY"

    echo "[INFO] Starting Xvfb..."
    Xvfb $DISPLAY -screen 0 1280x960x24 &

    sleep 1  # 等待 Xvfb 初始化

    echo "[INFO] Starting window manager..."
    fluxbox &

    echo "[INFO] Starting x11vnc..."
    x11vnc -display $DISPLAY -forever -shared -rfbauth \
        /root/.vnc/passwd -rfbport 5900 -auth guess &

    echo "[INFO] Starting noVNC..."
    if [ -d /usr/share/novnc ]; then
        exec websockify --web=/usr/share/novnc/ 80 localhost:5900
    elif [ -d /usr/share/novnc/utils ]; then
        exec websockify --web=/usr/share/novnc/utils/ 80 localhost:5900
    else
        echo "⚠️ noVNC not found, keeping container alive"
        tail -f /dev/null
    fi
}

# -----------------------------
# 后台启动 Selenium 示例（可选）
# -----------------------------
start_selenium_demo() {
    if [ -f /demo_selenium.py ]; then
        python3 /demo_selenium.py &
    fi
}

# -----------------------------
# 主流程
# -----------------------------
cleanup_locks
start_services
start_selenium_demo
"""

# Selenium 示例脚本
DEMO_SELENIUM = """from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import time

options = Options()
options.headless = False   # 必须 False，这样才能在 VNC 桌面看到浏览器动作

driver = webdriver.Firefox(options=options)

try:
    print("🌍 打开网页 https://www.python.org ...")
    driver.get("https://www.python.org")

    time.sleep(5)  # 等待页面加载

    title = driver.title
    print(f"✅ 网页标题: {title}")

    screenshot_path = "/root/screenshot.png"
    driver.save_screenshot(screenshot_path)
    print(f"📸 截图已保存到 {screenshot_path}")

finally:
    driver.quit()
"""

# 写入文件
with open("Dockerfile", "w") as f:
    f.write(DOCKERFILE_CONTENT)

with open("startup.sh", "w", encoding="utf-8") as f:
    f.write(STARTUP_SCRIPT)

with open("demo_selenium.py", "w", encoding="utf-8") as f:
    f.write(DEMO_SELENIUM)

# 获取 Docker 客户端
client = docker.from_env()

# 检查镜像是否存在
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

# 检查容器是否存在
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
print(
    "👉 Selenium will auto-open Firefox, go to python.org, and save screenshot \
        at /root/screenshot.png"
)
