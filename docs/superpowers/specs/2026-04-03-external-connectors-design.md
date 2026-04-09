# DB-GPT External Connectors Design Document

> **Date**: 2026-04-03
> **Status**: Draft
> **Author**: DB-GPT Team
> **Target Level**: L3 (Fully Automated Scheduled Analysis + Push)

---

## 1. Executive Summary

DB-GPT 的 ReAct Agent 已经能够执行数据分析、SQL 取数、代码执行和报告生成等任务。但当前分析结果只能在平台内查看或通过分享链接共享，无法自动推送到外部服务。

本方案提出 **"Skills + MCP 双轮驱动"** 架构，使 DB-GPT Agent 能够：
- 从外部服务拉取数据作为分析输入（语雀文档、飞书表格、GitHub Issues 等）
- 将分析结果自动推送到外部服务（钉钉群通知、语雀文档、飞书消息、邮件等）
- 支持 L3 级别的全自动定时分析 + 推送（如"每天早上 8 点执行销售分析，发布到语雀，通知钉钉群"）

---

## 2. Architecture: Skills + MCP 双轮驱动

### 2.1 Core Philosophy

```
Skills = 大脑（认知层）    →  知道"该做什么"、"什么顺序"、"怎么分析"
MCP Connectors = 手脚（执行层）  →  知道"怎么连接外部世界"、"怎么读写外部服务"
```

- **Skills** 提供领域知识和工作流编排能力（分析模式、SQL 模板、报告格式等），通过 `required_tools` 声明连接器依赖
- **MCP Connectors** 提供标准化的外部服务访问能力（读写语雀、发送钉钉消息、操作飞书文档等），遵循 MCP 协议

两者协同：Skill 定义"分析完后把报告推送到语雀"的意图和流程，MCP Connector 提供 `yuque_create_doc` 这个具体工具来执行推送。

### 2.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DB-GPT Platform                          │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     ReAct Agent                           │  │
│  │                                                           │  │
│  │  Thought → Phase → Action → Action Input → Observation    │  │
│  │                        │                                  │  │
│  │                   ┌────┴────┐                             │  │
│  │                   │ToolPack │                             │  │
│  │                   └────┬────┘                             │  │
│  └────────────────────────┼──────────────────────────────────┘  │
│                           │                                     │
│          ┌────────────────┼────────────────┐                    │
│          │                │                │                    │
│    ┌─────┴──────┐  ┌─────┴──────┐  ┌──────┴───────┐           │
│    │ Built-in   │  │  Skill     │  │  Connector   │           │
│    │  Tools     │  │  Tools     │  │  Tools       │           │
│    │            │  │            │  │  (from MCP)  │           │
│    │ sql_query  │  │ load_skill │  │              │           │
│    │ code_interp│  │ exec_skill │  │ yuque_*      │           │
│    │ html_interp│  │            │  │ dingtalk_*   │           │
│    │ shell_inter│  │            │  │ feishu_*     │           │
│    │ knowledge  │  │            │  │ wecom_*      │           │
│    │ Terminate  │  │            │  │ github_*     │           │
│    └────────────┘  └─────┬──────┘  │ email_*      │           │
│                          │         └──────┬───────┘           │
│                    ┌─────┴──────┐         │                    │
│                    │  SKILL.md  │   ┌─────┴──────┐            │
│                    │            │   │ Connector  │            │
│                    │ required_  │   │  Manager   │            │
│                    │  tools:    │   │            │            │
│                    │  - yuque_* │   │ - Catalog  │            │
│                    │  - dingtk_*│   │ - Creds    │            │
│                    │            │   │ - Lifecycle│            │
│                    │ workflow:  │   │ - Confirm  │            │
│                    │  1.Analyze │   └─────┬──────┘            │
│                    │  2.Format  │         │                    │
│                    │  3.Push    │    MCP Protocol              │
│                    └────────────┘    (SSE)              │
│                                          │                    │
└──────────────────────────────────────────┼────────────────────┘
                                           │
              ┌──────────┬──────────┬──────┴───┬──────────┐
              │          │          │          │          │
         ┌────┴───┐ ┌───┴────┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐
         │ 飞书   │ │ 钉钉   │ │ 语雀  │ │ 企微  │ │GitHub │
         │ MCP    │ │ MCP    │ │ MCP   │ │ MCP   │ │ MCP   │
         │Server  │ │Server  │ │Server │ │Server │ │Server │
         │(官方)  │ │(官方)  │ │(社区) │ │(社区) │ │(社区) │
         └───┬────┘ └───┬────┘ └───┬───┘ └───┬───┘ └───┬───┘
             │          │          │          │         │
         ┌───┴──┐  ┌───┴──┐  ┌───┴──┐  ┌───┴──┐  ┌──┴───┐
         │飞书  │  │钉钉  │  │语雀  │  │企微  │  │GitHub│
         │Open  │  │Open  │  │Open  │  │Open  │  │ API  │
         │API   │  │API   │  │API   │  │API   │  │      │
         └──────┘  └──────┘  └──────┘  └──────┘  └──────┘
```

### 2.3 Why Not Native Python? (全 MCP 统一方案)

**早期方案（已废弃）** 曾考虑中国服务使用原生 Python 实现、海外服务使用 MCP。经调研发现：

| 服务 | MCP Server | 来源 | 状态 |
|------|-----------|------|------|
| 飞书 Feishu | `larksuite/lark-openapi-mcp` | **官方** | 稳定 |
| 钉钉 DingTalk | `open.dingtalk.com` MCP Server | **官方** | 稳定 |
| 语雀 Yuque | `yuque-mcp` (PyPI) | 社区 | 可用 |
| 企微 WeChat Work | `wecom-bot-mcp-server` (PyPI) | 社区 | 可用 |
| GitHub | `@modelcontextprotocol/server-github` | 官方 | 稳定 |
| Slack | `@modelcontextprotocol/server-slack` | 官方 | 稳定 |
| Google Sheets | `@anthropic/google-sheets-mcp` | 社区 | 可用 |
| Notion | `@notionhq/notion-mcp-server` | 官方 | 稳定 |
| Email | SMTP MCP servers | 社区 | 可用 |

**结论**：所有目标服务均已有 MCP Server 实现（2026 年 mcp.so 已收录 19,400+ servers），DB-GPT 无需自行编写任何外部服务 API 调用代码。

**全 MCP 统一方案的优势**：
1. **零维护成本**：API 更新由 MCP Server 社区/官方维护
2. **标准化**：统一的 MCP 协议，DB-GPT 只需一套连接管理代码
3. **扩展性**：新服务 = 新 MCP Server 配置条目，无需写代码
4. **生态复用**：直接复用 19,400+ 社区 MCP Servers

### 2.4 Comparison with Industry

| 维度 | Manus | Codex | DB-GPT (本方案) |
|------|-------|-------|----------------|
| 连接器协议 | MCP + 原生 | MCP (OpenAI 生态) | MCP 统一 |
| 认知层 | 内置 Workflow | Prompt | Skills (SKILL.md) |
| 交互模式 | 面板式 + 自动 | 配置文件 | 面板式 + 自动 + 手动触发 |
| 安全确认 | 部分有 | 无 | **连接器写操作确认 + 定时任务事后通知** |
| 定时任务 | 无 | 无 | **L3 Scheduler（核心差异）** |
| 数据分析集成 | 弱 | 无 | **原生 SQL/代码分析 + 外推** |
| 差异化 | 通用 AI Agent | 代码助手 | **数据分析 + 外部协作** |

---

## 3. Core Components

### 3.1 ConnectorManager

ConnectorManager 是连接器的核心管理层，负责凭据管理、MCP Server 生命周期和工具注入。

```python
# packages/dbgpt-core/src/dbgpt/agent/resource/connector/manager.py

class ConnectorManager:
    """管理所有外部连接器的生命周期和凭据。"""

    def __init__(self, system_app):
        self._catalog = ConnectorCatalog()      # 连接器目录（JSON 配置）
        self._credential_store = CredentialStore(system_app)  # 凭据加密存储
        self._active_connections: Dict[str, MCPToolPack] = {}  # 活跃 MCP 连接

    async def get_user_tools(self, user_id: str) -> List[Tool]:
        """获取用户已连接服务的所有工具，注入到 Agent 的 ToolPack。"""
        connectors = await self._credential_store.get_active(user_id)
        tools = []
        for conn in connectors:
            mcp_pack = await self._get_or_create_mcp_pack(conn)
            tools.extend(mcp_pack.get_tools())
        return tools

    async def _get_or_create_mcp_pack(self, conn) -> MCPToolPack:
        """获取或创建 MCP Server 连接（SSE 模式）。"""
        key = f"{conn.user_id}:{conn.connector_type}"
        if key not in self._active_connections:
            catalog_entry = self._catalog.get(conn.connector_type)
            credentials = self._credential_store.decrypt(conn)
            headers = self._map_credentials_to_headers(credentials, catalog_entry)
            mcp_pack = MCPToolPack(
                mcp_servers=catalog_entry.server_uri,  # SSE endpoint URL
                headers=headers                        # Auth token headers
            )
            await mcp_pack.preload_resource()
            self._active_connections[key] = mcp_pack
        return self._active_connections[key]
```

### 3.2 Connector Catalog (JSON Configuration)

新增连接器 = 新增一个 JSON 配置条目，零代码：

```json
// packages/dbgpt-ext/src/dbgpt_ext/connector/catalog.json
{
  "connectors": [
    {
      "type": "feishu",
      "display_name": "飞书",
      "description": "飞书消息、文档、日历集成",
      "icon": "feishu",
      "category": "communication",
      "mcp_server": {
        "server_uri": "http://localhost:3001/sse",
        "transport": "sse"
      },
      "auth": {
        "type": "token",
        "fields": [
          {"name": "app_id", "label": "App ID", "type": "text", "required": true},
          {"name": "app_secret", "label": "App Secret", "type": "password", "required": true}
        ],
        "header_mapping": {
          "app_id": "X-Lark-App-Id",
          "app_secret": "X-Lark-App-Secret"
        }
      },
      "confirm_actions": ["feishu_send_message", "feishu_create_doc", "feishu_update_doc"],
      "read_actions": ["feishu_get_doc", "feishu_list_docs", "feishu_search"]
    },
    {
      "type": "dingtalk",
      "display_name": "钉钉",
      "description": "钉钉群消息推送和机器人通知",
      "icon": "dingtalk",
      "category": "communication",
      "mcp_server": {
        "server_uri": "http://localhost:3002/sse",
        "transport": "sse"
      },
      "auth": {
        "type": "token",
        "fields": [
          {"name": "webhook_url", "label": "群机器人 Webhook URL", "type": "text", "required": true},
          {"name": "secret", "label": "加签密钥", "type": "password", "required": false}
        ],
        "header_mapping": {
          "webhook_url": "X-DingTalk-Webhook",
          "secret": "X-DingTalk-Secret"
        }
      },
      "confirm_actions": ["dingtalk_send_message", "dingtalk_send_card"],
      "read_actions": []
    },
    {
      "type": "yuque",
      "display_name": "语雀",
      "description": "语雀知识库文档读写",
      "icon": "yuque",
      "category": "document",
      "mcp_server": {
        "server_uri": "http://localhost:3003/sse",
        "transport": "sse"
      },
      "auth": {
        "type": "token",
        "fields": [
          {"name": "token", "label": "Personal Access Token", "type": "password", "required": true},
          {"name": "default_namespace", "label": "默认知识库", "type": "text", "required": false}
        ],
        "header_mapping": {
          "token": "X-Auth-Token"
        }
      },
      "confirm_actions": ["yuque_create_doc", "yuque_update_doc", "yuque_delete_doc"],
      "read_actions": ["yuque_get_doc", "yuque_list_docs", "yuque_search"]
    },
    {
      "type": "github",
      "display_name": "GitHub",
      "description": "GitHub Issues、PR、仓库管理",
      "icon": "github",
      "category": "project",
      "mcp_server": {
        "server_uri": "http://localhost:3004/sse",
        "transport": "sse"
      },
      "auth": {
        "type": "token",
        "fields": [
          {"name": "github_token", "label": "Personal Access Token", "type": "password", "required": true}
        ],
        "header_mapping": {
          "github_token": "Authorization"
        }
      },
      "confirm_actions": ["github_create_issue", "github_create_pr", "github_comment"],
      "read_actions": ["github_get_issue", "github_list_issues", "github_get_repo"]
    }
  ]
}
```

### 3.3 Credential Store (凭据加密存储)

复用 DB-GPT 现有的 `FernetEncryption`：

```python
# packages/dbgpt-serve/src/dbgpt_serve/connector/models/models.py

class ConnectorCredentialEntity(Model):
    """连接器凭据实体。"""
    __tablename__ = "connector_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    connector_type = Column(String(64), nullable=False)        # "yuque", "dingtalk"
    connector_name = Column(String(256), nullable=True)         # 用户自定义名称
    encrypted_credentials = Column(Text, nullable=False)        # Fernet 加密的 JSON
    encryption_salt = Column(String(64), nullable=False)        # 独立盐值
    status = Column(String(32), default="active")               # active/expired/revoked
    token_expires_at = Column(DateTime, nullable=True)          # OAuth token 过期时间
    extra_config = Column(Text, nullable=True)                  # JSON 额外配置
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

### 3.4 Human-in-the-Loop Confirmation (Connector Tools Only)

> **原则**：原有 ReAct Agent 的 Skills、内置工具执行流程不受影响。仅对新增的 MCP 连接器写操作加入确认机制。

确认逻辑在 **ConnectorManager 注入的工具包装层** 实现，不在 Agent 核心管道中：

```python
# packages/dbgpt-core/src/dbgpt/agent/resource/connector/confirmation.py

class ConfirmationInterceptor:
    """拦截需要确认的连接器写操作。
    
    仅应用于 ConnectorManager 注入的 MCP 工具，
    不影响内置工具（sql_query、code_interpreter 等）和 Skill 工具。
    """

    def __init__(self, catalog: ConnectorCatalog):
        self._catalog = catalog

    async def should_confirm(self, tool_name: str, tool_args: dict, 
                              context: dict = None) -> bool:
        """判断是否需要用户确认。
        
        - 手动触发（用户在线交互）：写操作需确认
        - 定时任务触发：默认免确认（自动授权）
        """
        if context and context.get("trigger_type") == "scheduled":
            return False  # 定时任务免确认
        for connector in self._catalog.list():
            if tool_name in connector.confirm_actions:  # 命名空间前缀匹配
                return True
        return False

    def format_confirmation(self, tool_name: str, tool_args: dict) -> dict:
        """格式化确认消息，通过 SSE step.confirm 事件发送到前端。
        
        NOTE: step.confirm 是新增的 SSE 事件类型，需在前端新增处理逻辑。
        """
        return {
            "type": "step.confirm",   # 新增事件类型
            "tool": tool_name,
            "args_summary": self._summarize_args(tool_args),
            "message": f"即将执行 {tool_name}，是否确认？"
        }
```

**确认策略**：
- **手动触发（用户在线交互）**：连接器写操作需弹出确认 → 用户确认后继续
- **定时任务触发**：默认自动授权免确认 → 执行后推送通知（见 Section 9.3）
- **原有 Agent 工具**：不受影响，无确认拦截

前端在收到 `step.confirm` 事件（**新增 SSE 事件类型**）时弹出确认对话框，用户确认后 POST `/api/v1/connector/confirm/{confirm_id}` 继续执行。

---

## 4. Agent Integration

### 4.1 Tool Injection Point

**关键改动文件**: `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`

在 `_react_agent_stream()` 函数中，ToolPack 构建阶段注入连接器工具：

```python
# 现有代码（约 line 2827）:
tool_pack = ToolPack(
    [load_skill, load_tools, knowledge_retrieve, execute_skill_script,
     get_skill_resource, execute_skill_script_file, code_interpreter,
     shell_interpreter, html_interpreter, sql_query, Terminate()]
    + business_tools
)

# 新增：注入连接器工具
connector_manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
connector_tools = await connector_manager.get_user_tools(user_id)

tool_pack = ToolPack(
    [load_skill, load_tools, knowledge_retrieve, execute_skill_script,
     get_skill_resource, execute_skill_script_file, code_interpreter,
     shell_interpreter, html_interpreter, sql_query, Terminate()]
    + business_tools
    + connector_tools    # ← 新增
)
```

### 4.2 System Prompt Enhancement

在 Agent 的 system prompt 中动态注入已连接服务信息：

```python
# 动态生成连接器描述
connector_prompt = ""
if connector_tools:
    connector_prompt = """
## Connected External Services
The user has connected the following external services. You can use these tools
to read from or write to external services when the task requires it.

Available connector tools:
{tool_descriptions}

IMPORTANT: All write operations (send message, create document, etc.) will
require user confirmation before execution. Read operations are allowed
without confirmation.
""".format(tool_descriptions="\n".join(
        f"- {t.name}: {t.description}" for t in connector_tools
    ))
```

### 4.3 Skill Integration via required_tools

Skills 通过 `required_tools` 声明连接器依赖，使 Agent 知道该 Skill 需要哪些外部服务：

```yaml
# skills/sales-report-push/SKILL.md
---
name: sales-report-push
description: |
  Execute sales analysis and push report to external services.
  Requires: sql_query, yuque_create_doc, dingtalk_send_message
required_tools:
  - sql_query
  - yuque_create_doc
  - dingtalk_send_message
---

# Sales Report Push Workflow

## Steps
1. Execute SQL query to extract sales data
2. Generate analysis report with charts (html_interpreter)
3. Format report as Markdown for Yuque
4. Push report to Yuque knowledge base (yuque_create_doc)
5. Send summary notification to DingTalk group (dingtalk_send_message)
```

当 Agent 加载此 Skill 时，会自动检查 `required_tools` 中的连接器是否已配置。如果用户未连接语雀或钉钉，Agent 提示用户先配置连接。

---

## 5. API Design

### 5.1 Connector Management APIs

```
# 连接器类型（目录）
GET    /api/v2/serve/connectors/types              # 列出所有可用连接器类型

# 用户连接管理
POST   /api/v2/serve/connectors                    # 创建连接（提交凭据）
GET    /api/v2/serve/connectors                    # 列出用户的所有连接
DELETE /api/v2/serve/connectors/{id}               # 删除连接
PUT    /api/v2/serve/connectors/{id}               # 更新连接配置
GET    /api/v2/serve/connectors/{id}/test          # 测试连接是否可用

# OAuth 流程（后续扩展）
GET    /api/v2/serve/connectors/oauth/authorize    # 发起 OAuth 授权
GET    /api/v2/serve/connectors/oauth/callback     # OAuth 回调
```

### 5.2 Schema Examples

```python
# POST /api/v2/serve/connectors
class ConnectorCreateRequest(BaseModel):
    connector_type: str          # "yuque"
    connector_name: Optional[str]  # "我的语雀"
    credentials: Dict[str, str]  # {"token": "xxx"}
    extra_config: Optional[Dict]  # {"default_namespace": "team/knowledge"}

# GET /api/v2/serve/connectors
class ConnectorListResponse(BaseModel):
    id: int
    connector_type: str
    connector_name: str
    display_name: str            # "语雀"
    icon: str
    status: str                  # "active" / "expired"
    created_at: datetime

# GET /api/v2/serve/connectors/types
class ConnectorTypeResponse(BaseModel):
    type: str
    display_name: str
    description: str
    icon: str
    category: str
    auth_fields: List[dict]      # 前端动态渲染表单
```

---

## 6. Frontend Design

### 6.1 Connector Management Page

**路径**: `web/pages/construct/connectors/index.tsx`

参考现有数据库管理页面（`web/pages/construct/database/`）的模式：

```
┌─────────────────────────────────────────────────────────────┐
│  外部连接                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  我的连接                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  语雀        │  │  钉钉        │  │  + 添加     │         │
│  │  已连接  ●   │  │  已连接  ●   │  │    新连接   │         │
│  │  [测试][断开]│  │  [测试][断开]│  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  可用连接器                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 语雀     │ │ 钉钉     │ │ 飞书     │ │ 企微     │       │
│  │ 文档协作 │ │ 即时通讯 │ │ 即时通讯 │ │ 即时通讯 │       │
│  │ [连接]   │ │ [连接]   │ │ [连接]   │ │ [连接]   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ GitHub   │ │ 邮箱     │ │ Sheets   │ │ Notion   │       │
│  │ 代码管理 │ │ 电子邮件 │ │ 在线表格 │ │ 文档协作 │       │
│  │ [连接]   │ │ [连接]   │ │ [连接]   │ │ [连接]   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

- 连接器类型通过 `/connectors/types` API 动态加载
- 认证表单根据 `auth_fields` 动态渲染
- 点击「测试」调用 `/connectors/{id}/test` 验证连接

### 6.2 Chat Page Integration

在 `web/pages/index.tsx` 的聊天页面中：

1. **输入区域**：显示已连接服务的图标（类似 Manus 的连接器面板）
2. **Step 卡片**：Agent 使用连接器工具时，显示连接器图标和操作描述
3. **确认对话框**：`step.confirm` 事件触发确认 UI
4. **手动触发**：分析完成后，结果区域提供「推送到语雀」「发到钉钉」按钮

---

## 7. Serve Module Structure

```
packages/dbgpt-serve/src/dbgpt_serve/connector/
├── __init__.py
├── serve.py                    # ConnectorServe(BaseServe)
├── config.py                   # ServeConfig
├── models/
│   ├── __init__.py
│   └── models.py               # ConnectorCredentialEntity + Dao
├── api/
│   ├── __init__.py
│   ├── endpoints.py            # REST API 路由
│   └── schemas.py              # Pydantic 请求/响应模型
└── service/
    ├── __init__.py
    └── service.py              # ConnectorService (CRUD + 加密)
```

**Serve 注册步骤**（参考现有 prompt/datasource 模块）：

1. **scan_serve_configs()** — 在 `packages/dbgpt-app/src/dbgpt_app/initialization/serve_initialization.py` 的 modules 列表中添加：
   ```python
   modules = [
       ...
       "dbgpt_serve.connector.serve",  # 新增
   ]
   ```

2. **register_serve_apps()** — 在同一文件的注册函数中添加条件注册块：
   ```python
   from dbgpt_serve.connector.serve import Serve as ConnectorServe
   ConnectorServe.register(system_app)
   ```

3. **config.py 标准常量** — `packages/dbgpt-serve/src/dbgpt_serve/connector/config.py`：
   ```python
   APP_NAME = "connector"
   SERVE_APP_NAME = "dbgpt_serve_connector"
   SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.connector"
   ```

---

## 8. Security

### 8.1 Credential Security
- 使用 `FernetEncryption`（已存在于 `dbgpt.core.interface.variables`）加密存储凭据
- 每行凭据独立 salt
- 凭据仅在 MCP Server 启动时解密传入环境变量，不在日志或响应中暴露

### 8.2 Operation Safety
- **手动触发写操作**：连接器写操作（发消息、创建文档、发邮件）需用户确认（仅限连接器工具，不影响原有 Agent 工具）
- **定时任务写操作**：默认自动授权免确认，执行后推送通知（含执行结果 + 回退入口）
- **读操作放行**：读取文档、搜索等操作可直接执行
- **权限隔离**：每个用户只能访问自己配置的连接器
- **Token 刷新**：OAuth token 过期自动刷新，刷新失败标记连接为 `expired`

### 8.3 MCP Server Connection Management
- 每个用户连接对应独立的 SSE 长连接（MCP Server 独立部署，DB-GPT 不管理 Server 进程）
- 连接在会话结束后关闭，下次使用时重新建立
- 连接池管理避免并发连接过多
- SSE 连接超时和重试策略：默认 30s 超时，最多重试 3 次

---

## 9. Data Flow

### 9.1 Output Flow (推送分析结果)

```
User: "分析上月销售数据，报告发到语雀，通知钉钉群"
  │
  ▼
ReAct Agent
  │ Thought: 需要执行 SQL 分析，然后推送结果
  │ Phase: Analysis
  │
  │── Action: sql_query
  │   └─ Result: 销售数据表
  │
  │── Action: html_interpreter
  │   └─ Result: 可视化报告
  │
  │ Phase: Push Results
  │
  │── Action: yuque_create_doc       ← MCP Tool
  │   └─ [step.confirm] 用户确认 ✓
  │   └─ Result: 文档已创建 (URL)
  │
  │── Action: dingtalk_send_message  ← MCP Tool
  │   └─ [step.confirm] 用户确认 ✓
  │   └─ Result: 消息已发送
  │
  └── Action: Terminate
      └─ Final: "分析报告已发布到语雀并通知钉钉群"
```

### 9.2 Input Flow (拉取外部数据)

```
User: "读取语雀知识库里的《Q1季度目标》，对比实际销售数据分析完成度"
  │
  ▼
ReAct Agent
  │ Phase: Data Collection
  │
  │── Action: yuque_read_doc         ← MCP Tool (读操作，无需确认)
  │   └─ Result: Q1 目标文档内容
  │
  │── Action: sql_query
  │   └─ Result: Q1 实际销售数据
  │
  │ Phase: Analysis
  │
  │── Action: code_interpreter
  │   └─ Result: 目标完成度分析
  │
  └── Action: Terminate
      └─ Final: "Q1 目标完成率 87%..."
```

### 9.3 Scheduled Task Flow (定时任务流程)

```
Scheduler Trigger (cron: "0 8 * * *")
  │
  ▼
ReAct Agent (context: trigger_type=scheduled, auto_confirm=true)
  │ 
  │── Action: sql_query          ← 内置工具，无需确认
  │   └─ Result: 今日销售数据
  │
  │── Action: html_interpreter   ← 内置工具，无需确认
  │   └─ Result: 可视化报告
  │
  │── Action: yuque_create_doc   ← MCP Tool（定时触发，自动授权免确认）
  │   └─ Result: 文档已创建 (URL)
  │
  │── Action: dingtalk_send_message  ← MCP Tool（定时触发，自动授权免确认）
  │   └─ Result: 消息已发送
  │
  └── Post-Execution Notification
      │
      ├─ 推送通知给用户（钉钉/站内信）：
      │   "定时任务 [每日销售分析] 已执行完成
      │    ✅ 语雀文档已创建: {url}
      │    ✅ 钉钉群已通知
      │    ⏪ [回退操作]"
      │
      └─ 回退 = 补偿性 MCP 工具调用：
          - yuque_create_doc 的回退 → yuque_delete_doc(doc_id)
          - dingtalk_send_message 的回退 → dingtalk_recall_message(msg_id)
          (仅在服务 API 支持时可用；不可回退时标注"不可回退")
```

---

## 10. Files Inventory

### New Files
| Path | Purpose |
|------|---------|
| `packages/dbgpt-core/src/dbgpt/agent/resource/connector/__init__.py` | Connector module |
| `packages/dbgpt-core/src/dbgpt/agent/resource/connector/manager.py` | ConnectorManager |
| `packages/dbgpt-core/src/dbgpt/agent/resource/connector/catalog.py` | ConnectorCatalog (JSON config loader) |
| `packages/dbgpt-core/src/dbgpt/agent/resource/connector/confirmation.py` | ConfirmationInterceptor |
| `packages/dbgpt-ext/src/dbgpt_ext/connector/catalog.json` | Connector catalog data |
| `packages/dbgpt-serve/src/dbgpt_serve/connector/` | Entire Serve module |
| `web/pages/construct/connectors/index.tsx` | Connector management page |
| `web/components/connector/` | Connector UI components |

### Modified Files
| Path | Change |
|------|--------|
| `packages/dbgpt-app/.../agentic_data_api.py` | Inject connector tools in `_react_agent_stream()` |
| `packages/dbgpt-app/.../component_configs.py` | Register ConnectorManager component |
| `packages/dbgpt-core/.../agent/resource/base.py` | Add `Connector` to ResourceType enum |
| `web/pages/index.tsx` | Add connector status indicators in chat page |
| `packages/dbgpt-app/.../serve_initialization.py` | Register ConnectorServe in `scan_serve_configs()` and `register_serve_apps()` |

---

## 11. Implementation Roadmap

### Phase 1: Connector Infrastructure (3 weeks)
- ConnectorManager + ConnectorCatalog
- CredentialStore (FernetEncryption)
- Serve module (API + DB model)
- Human-in-the-loop confirmation mechanism
- First 3 connectors: 飞书 (official MCP), 钉钉 (official MCP), 语雀 (community MCP)
- Frontend connector management page (basic)

### Phase 2: Skill Enhancement (2 weeks)
- Skill `required_tools` resolution with connector tools
- System prompt dynamic connector description injection
- Auto-check connector availability when loading Skills
- Enhanced step UI for connector operations

### Phase 3: L3 Scheduler (3 weeks)
- Scheduled task system for periodic analysis + push
- **定时任务默认自动授权**：`trigger_type=scheduled` 时 ConfirmationInterceptor 免确认
- **执行后通知**：推送执行结果通知给用户（含成功/失败状态 + 回退入口）
- **回退机制**：回退 = 补偿性 MCP 工具调用（如 `yuque_delete_doc`），仅在服务 API 支持时可用
- Cron-based scheduling UI
- Execution history and monitoring
- Failure retry and alerting

### Phase 4: Ecosystem Expansion (ongoing)
- Additional connectors: 企微, GitHub, Email, Notion, Slack, Google Sheets
- OAuth 2.0 flow for services that require it
- Connector marketplace (community contributions)
- Advanced features: webhook triggers, event-driven workflows

---

## 12. Validation Plan

### End-to-End Test Scenarios
1. **Output**: User says "分析数据并发布到语雀" → Agent executes analysis → calls `yuque_create_doc` → user confirms → document appears in Yuque
2. **Input**: User says "读取飞书文档分析" → Agent calls `feishu_get_doc` → processes content → returns analysis
3. **Bidirectional**: User says "读取语雀目标文档，对比 SQL 数据，分析报告发到钉钉" → full input + analysis + output flow
4. **Connection management**: User adds Yuque token in frontend → starts chat → Agent auto-discovers and uses Yuque tools
5. **Security**: Database stores encrypted credentials; write operations require confirmation; read operations execute directly
6. **Scheduled task**: Cron triggers analysis → auto-confirm (no confirmation UI) → yuque_create_doc + dingtalk_send_message → user receives notification with execution summary + rollback link → user clicks rollback → compensating MCP call executed
7. **Rollback**: After scheduled push, user clicks rollback → system calls `yuque_delete_doc(doc_id)` → verifies doc deleted → marks rollback complete

### Unit Tests
- ConnectorManager lifecycle tests
- CredentialStore encrypt/decrypt tests
- ConnectorCatalog loading and validation tests
- ConfirmationInterceptor logic tests
- API endpoint CRUD tests
