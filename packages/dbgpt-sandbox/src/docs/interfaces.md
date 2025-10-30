# 接口说明

本文档描述了 dbgpt-sandbox-agent 的主要接口设计与使用说明。

## 会话管理接口
- `create_session(user_id: str, task_id: str, image_type: str) -> str`
  - 创建一个新的会话，返回 session_id。
  - 参数：
    - user_id: 用户标识
    - task_id: 任务标识
    - image_type: 运行时类型（如 python、javascript）

- `configure_session(session_id: str, config_info: dict) -> bool`
  - 配置会话参数，如依赖、资源限制等。
  - 参数：
    - session_id: 会话标识
    - config_info: 配置字典，支持 keys:
      - language: 语言（默认 python）
      - dependencies: 依赖列表（仅容器运行时支持自动安装 pip/npm）
      - max_memory: 如 "512m"（容器）
      - max_cpus: 整数
      - network_disabled: 是否禁网（默认 False）
      - env: 环境变量字典

- `execute_code(session_id: str, code_type: str, code_content: str) -> dict`
  - 在指定会话中执行代码，返回执行结果。
  - 参数：
    - session_id: 会话标识
    - code_type: 代码类型（如 python、javascript）
    - code_content: 代码内容字符串
  - 返回值：包含输出、错误、耗时、退出码等信息的字典

- `get_session_status(session_id: str) -> dict`
  - 查询会话当前状态与资源使用情况。
  - 参数：
    - session_id: 会话标识
  - 返回值：包含状态、内存、CPU 使用等信息的字典

- `disconnect_session(user_id: str, task_id: str) -> bool`  
  - 停止并销毁指定用户任务的会话。
  - 参数：
    - user_id: 用户标识
    - task_id: 任务标识
  - 返回值：操作是否成功  