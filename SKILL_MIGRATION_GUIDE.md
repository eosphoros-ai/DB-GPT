# DB-GPT Agent SKILL 改造方案

## 概述

本方案参考 deepagents 的中间件机制，为 DB-GPT 的 agent 引入更灵活的 SKILL 加载机制。

## 核心改造

### 1. 中间件系统 (`middleware/`)

#### `base.py` - 中间件基础架构

```python
class AgentMiddleware(ABC):
    """中间件基类，定义生命周期钩子"""
    
    async def before_init(self, agent, **kwargs) -> Optional[Dict[str, Any]]
    async def after_init(self, agent, **kwargs) -> Optional[Dict[str, Any]]
    async def before_generate_reply(self, agent, context, **kwargs) -> Optional[Dict[str, Any]]
    async def after_generate_reply(self, agent, context, reply_message, **kwargs) -> Optional[Dict[str, Any]]
    async def before_thinking(self, agent, context, **kwargs) -> Optional[Dict[str, Any]]
    async def after_thinking(self, agent, context, llm_reply, model_name, **kwargs) -> Optional[Dict[str, Any]]
    async def before_act(self, agent, context, message, **kwargs) -> Optional[Dict[str, Any]]
    async def after_act(self, agent, context, action_output, **kwargs) -> Optional[Dict[str, Any]]
    async def modify_system_prompt(self, agent, original_prompt, context) -> str

class MiddlewareManager:
    """中间件管理器"""
    def register(self, middleware: AgentMiddleware)
    def unregister(self, middleware: AgentMiddleware)
    async def execute_before_init(...)
    async def execute_after_init(...)
    async def execute_before_generate_reply(...)
    # ... 其他钩子执行方法
```

**特点：**
- 支持9个生命周期钩子
- 中间件可注册/注销
- 支持启用/禁用中间件
- 状态管理机制

#### `agent.py` - 支持中间件的 Agent

```python
class MiddlewareAgent(ConversableAgent):
    """扩展 ConversableAgent 支持中间件"""
    
    def __init__(self, agent_config: Optional[AgentConfig] = None, **kwargs)
    def register_middleware(self, middleware)
    def unregister_middleware(self, middleware)
    
    async def build(self, is_retry_chat=False)
    async def thinking(self, messages, sender=None, prompt=None)
    async def act(self, message, sender, ...)
    async def build_system_prompt(...)
```

**特点：**
- 继承自 ConversableAgent
- 集成 MiddlewareManager
- 自动在生命周期中执行中间件钩子
- 支持配置化启用中间件

### 2. Skills 中间件 V2 (`skill/middleware_v2.py`)

```python
class SkillsMiddlewareV2(AgentMiddleware):
    """基于新中间件系统的 Skills 实现"""
    
    def __init__(self, sources: List[str], auto_load=True, ...)
    def load_skills(self) -> Dict[str, LoadedSkill]
    def get_skill(self, name: str) -> Optional[LoadedSkill]
    def list_skills(self) -> List
    def match_skills(self, user_input: str) -> List[LoadedSkill]
    
    async def after_init(self, agent, **kwargs)
    async def before_generate_reply(self, agent, context, **kwargs)
    async def modify_system_prompt(self, agent, original_prompt, context)
```

**特点：**
- 继承 AgentMiddleware
- 复用现有的 SkillsMiddleware
- 支持自动加载和匹配 skills
- 注入 skills 信息到系统提示词

## 文件结构

```
dbgpt/agent/
├── middleware/                          # 新增：中间件系统
│   ├── __init__.py
│   ├── base.py                          # AgentMiddleware, MiddlewareManager
│   ├── agent.py                         # MiddlewareAgent
│   ├── README.md                        # 文档
│   └── example.py                       # 使用示例
├── skill/
│   ├── base.py                          # Skill, SkillBase, SkillMetadata
│   ├── middleware.py                     # 原有 SkillsMiddleware
│   ├── middleware_v2.py                 # 新增：SkillsMiddlewareV2
│   ├── agent.py                         # 原有 SkillsAgent
│   ├── manage.py                        # SkillManager
│   └── parameters.py                    # SkillParameters
└── __init__.py                          # 更新导出

examples/
├── skills/                              # 新增：示例 Skills
│   └── user/
│       ├── web-research/
│       │   └── SKILL.md
│       └── code-review/
│           └── SKILL.md
└── test_skills_middleware.py             # 新增：测试脚本
```

## 使用方式

### 方式 1：使用 MiddlewareAgent（推荐）

```python
from dbgpt.agent.core.profile.base import ProfileConfig
from dbgpt.agent.core.agent import AgentContext
from dbgpt.agent.middleware.agent import MiddlewareAgent, AgentConfig

profile = ProfileConfig(
    name="assistant",
    role="AI Assistant",
    goal="Help users with their tasks using available skills.",
)

config = AgentConfig(
    enable_middleware=True,
    enable_skills=True,
    skill_sources=[
        "/path/to/skills/user",
        "/path/to/skills/project",
    ],
)

agent = MiddlewareAgent(
    profile=profile,
    agent_config=config,
)

agent_context = AgentContext(conv_id="test_conv_001")
await agent.bind(agent_context).build()
```

### 方式 2：使用自定义中间件

```python
from dbgpt.agent.middleware.base import AgentMiddleware

class LoggingMiddleware(AgentMiddleware):
    """自定义中间件示例"""
    
    async def before_generate_reply(self, agent, context, **kwargs):
        print(f"Before: {context.message.content}")
    
    async def after_generate_reply(self, agent, context, reply_message, **kwargs):
        print(f"After: {reply_message.content}")

agent = MiddlewareAgent(profile=profile)
agent.register_middleware(LoggingMiddleware())
```

### 方式 3：直接使用 SkillsMiddlewareV2

```python
from dbgpt.agent.skill.middleware_v2 import SkillsMiddlewareV2

skills_middleware = SkillsMiddlewareV2(
    sources=["/path/to/skills/user"],
    auto_load=True,
    auto_match=True,
)

skills = skills_middleware.load_skills()
matched = skills_middleware.match_skills("research quantum computing")
```

## SKILL 格式

### 目录结构

```
/skills/user/web-research/
├── SKILL.md          # 必需：YAML frontmatter + markdown 指令
└── helper.py         # 可选：辅助文件
```

### SKILL.md 格式

```markdown
---
name: web-research
description: Structured approach to conducting thorough web research
version: 1.0.0
author: Your Name
skill_type: research
tags: [web, research, analysis]
allowed-tools: web-search
license: MIT
---

# Web Research Skill

## When to Use
- User asks you to research a topic
- You need to gather information from web

## Workflow
1. Define research scope
2. Search for relevant information
3. Evaluate sources
4. Synthesize findings
5. Present results

## Best Practices
- Start with broad searches, then narrow down
- Cross-reference information from multiple sources
- Be transparent about uncertainty
```

## 与 deepagents 对比

| 特性 | deepagents | DB-GPT (新) |
|------|------------|--------------|
| 后端支持 | Filesystem, State, Remote | Filesystem (计划中) |
| 中间件钩子 | before_agent, wrap_model_call | 完整生命周期钩子 |
| SKILL 格式 | SKILL.md with YAML | SKILL.md with YAML |
| 渐进式披露 | 是 | 是 |
| 异步支持 | 是 | 是 |
| 自定义中间件 | 是 | 是 |
| 状态管理 | 是 | 是 |

## 迁移指南

### 从现有 SkillsAgent 迁移

```python
# 旧方式
from dbgpt.agent.skill.agent import SkillsAgent, SkillsAgentConfig

config = SkillsAgentConfig(skill_sources=["/path/to/skills"])
agent = SkillsAgent(profile=profile, skills_config=config)

# 新方式
from dbgpt.agent.middleware.agent import MiddlewareAgent, AgentConfig

config = AgentConfig(skill_sources=["/path/to/skills"])
agent = MiddlewareAgent(profile=profile, agent_config=config)
```

### 从 ConversableAgent 迁移

```python
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.middleware.base import MiddlewareManager

class MyAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.middleware_manager = MiddlewareManager()
    
    async def build(self, is_retry_chat=False):
        await self.middleware_manager.execute_before_init(self)
        await super().build(is_retry_chat)
        await self.middleware_manager.execute_after_init(self)
        return self
```

## 优势

1. **模块化**：中间件可以独立开发和测试
2. **可扩展**：轻松添加新的中间件
3. **灵活性**：可以动态注册/注销中间件
4. **兼容性**：与现有的 ConversableAgent 兼容
5. **渐进式**：可以选择性使用中间件

## 未来改进

- Backend 抽象（支持多种存储后端）
- Skills 热重载
- Skill 依赖和版本管理
- Skill 执行监控和分析
- Skill 市场集成

## 测试

运行测试脚本：

```bash
python examples/test_skills_middleware.py
```

## 参考资料

- DeepAgents: https://github.com/anthropics/deepagents
- Agent Skills: https://agentskills.io/specification
- DB-GPT Agent Framework
