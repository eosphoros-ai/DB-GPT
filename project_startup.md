# Stargazer (DB-GPT) 项目启动指南

## 环境要求

- Python >= 3.10
- uv 包管理器
- Docker（运行 MySQL）
- DeepSeek API Key

## 启动命令

```bash
cd /Users/tuwan/java_project/Stargazer

# 1. 确保 MySQL Docker 容器运行
docker start mysql8

# 2. 首次启动：安装所有 workspace 依赖
uv sync --all-packages --extra hf

# 3. 首次启动：初始化 MySQL 数据库表
docker exec -i mysql8 mysql -u root -p123456 dbgpt < assets/schema/dbgpt.sql

# 4. 启动服务
.venv/bin/python3 .venv/bin/dbgpt start webserver -c configs/dbgpt-proxy-deepseek.toml > /tmp/dbgpt.log 2>&1 &
```

## 访问地址

- 主页：`http://127.0.0.1:5670`
- 应用列表（选择 Chat DB 开始 NL-to-SQL）：`http://127.0.0.1:5670/data_index`
- Database 管理：`http://127.0.0.1:5670/construct/database`

## 注意事项

- 不使用 `uv run` 启动（可能锁死），直接用 `.venv/bin/python3 .venv/bin/dbgpt`
- 日志输出到 `/tmp/dbgpt.log`
- 端口 5670

## 数据库查询（NL-to-SQL）

`game_analytics` 数据库有 15 张表、约 35 万行游戏测试数据（见 `database_info.md`）。

使用流程：
1. 访问 `http://127.0.0.1:5670/data_index`
2. 点击 "Chat DB" 卡片
3. 在聊天输入框上方选择 `game_analytics` 数据库
4. 输入自然语言问题即可
