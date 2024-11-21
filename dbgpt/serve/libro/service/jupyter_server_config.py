c = get_config()  # noqa
# 为了 dbgpt 页面能 iframe 能正确加载显示 libro 页面
c.ServerApp.tornado_settings = {
    "headers": {"Content-Security-Policy": "frame-ancestors 'self' *"}
}
# 默认启动 libro 不自动打开新的页面
c.ServerApp.open_browser = False

# 默认启动 libro 时的固定端口
c.ServerApp.port = 5671
# 禁用自动寻找空闲端口
c.ServerApp.port_retries = 0
c.ContentsManager.allow_hidden = True
c.ServerApp.token = ""
c.ServerApp.password = ""
