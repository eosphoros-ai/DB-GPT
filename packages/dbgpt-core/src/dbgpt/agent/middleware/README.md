# Agent Middleware System for DB-GPT

This module implements a middleware system for DB-GPT agents, inspired by deepagents' AgentMiddleware pattern.

## Architecture

The middleware system allows plugins to hook into agent lifecycle events:

- `AgentMiddleware` - Base class for all middleware
- `MiddlewareManager` - Manages middleware registration and execution
- `MiddlewareAgent` - ConversableAgent with middleware support
- `SkillsMiddlewareV2` - Skills middleware using the new middleware system

## Middleware Lifecycle Hooks

Middleware can hook into the following lifecycle events:

| Hook | Description |
|------|-------------|
| `before_init` | Called before agent initialization |
| `after_init` | Called after agent initialization |
| `before_generate_reply` | Called before generating a reply |
| `after_generate_reply` | Called after generating a reply |
| `before_thinking` | Called before the thinking step |
| `after_thinking` | Called after the thinking step |
| `before_act` | Called before the act step |
| `after_act` | Called after the act step |
| `modify_system_prompt` | Modify the system prompt before it's sent to LLM |

## Usage Examples

### 1. Using MiddlewareAgent with Skills

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

agent_context = AgentContext(
    conv_id="test_conv_001",
)

await agent.bind(agent_context).build()
```

### 2. Creating Custom Middleware

```python
from dbgpt.agent.middleware.base import AgentMiddleware


class LoggingMiddleware(AgentMiddleware):
    """Custom middleware for logging."""

    async def before_generate_reply(self, agent, context, **kwargs):
        """Called before generating a reply."""
        print(f"Before generate reply: {context.message.content}")

    async def after_generate_reply(self, agent, context, reply_message, **kwargs):
        """Called after generating a reply."""
        print(f"After generate reply: {reply_message.content}")


agent = MiddlewareAgent(profile=profile)
agent.register_middleware(LoggingMiddleware())
```

### 3. Using SkillsMiddlewareV2 Directly

```python
from dbgpt.agent.skill.middleware_v2 import SkillsMiddlewareV2

skills_middleware = SkillsMiddlewareV2(
    sources=["/path/to/skills/user"],
    auto_load=True,
    auto_match=True,
    inject_to_system_prompt=True,
)

skills = skills_middleware.load_skills()
for name, skill in skills.items():
    print(f"{name}: {skill.metadata.description}")

matched_skills = skills_middleware.match_skills("research quantum computing")
```

## SKILL Format

Skills are loaded from directories containing a `SKILL.md` file:

```
/skills/user/web-research/
├── SKILL.md          # Required: YAML frontmatter + markdown instructions
└── helper.py         # Optional: supporting files
```

### SKILL.md Format

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
- You need to gather information from the web
- Research requires structured approach

## Workflow
1. Define research scope
2. Search for relevant information
3. Evaluate sources
4. Synthesize findings
5. Present results
```

## Comparison with DeepAgents

| Feature | DeepAgents | DB-GPT (New) |
|---------|-------------|----------------|
| Backend Support | Filesystem, State, Remote | Filesystem (planned) |
| Middleware Hooks | before_agent, wrap_model_call | Full lifecycle hooks |
| Skill Format | SKILL.md with YAML | SKILL.md with YAML |
| Progressive Disclosure | Yes | Yes |
| Async Support | Yes | Yes |

## Migration Guide

### From Existing SkillsAgent

If you're using `SkillsAgent` from `dbgpt.agent.skill.agent`, you can migrate to `MiddlewareAgent`:

```python
# Old way
from dbgpt.agent.skill.agent import SkillsAgent, SkillsAgentConfig

config = SkillsAgentConfig(skill_sources=["/path/to/skills"])
agent = SkillsAgent(profile=profile, skills_config=config)

# New way
from dbgpt.agent.middleware.agent import MiddlewareAgent, AgentConfig

config = AgentConfig(skill_sources=["/path/to/skills"])
agent = MiddlewareAgent(profile=profile, agent_config=config)
```

### From ConversableAgent

To add middleware support to existing `ConversableAgent`:

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

## File Structure

```
dbgpt/agent/
├── middleware/
│   ├── __init__.py
│   ├── base.py              # AgentMiddleware, MiddlewareManager
│   ├── agent.py             # MiddlewareAgent
│   └── example.py           # Usage examples
├── skill/
│   ├── base.py              # Skill, SkillBase, SkillMetadata
│   ├── middleware.py        # Original SkillsMiddleware
│   ├── middleware_v2.py     # SkillsMiddlewareV2 (new)
│   ├── agent.py             # SkillsAgent (old)
│   ├── manage.py            # SkillManager
│   └── parameters.py        # SkillParameters
```

## Future Improvements

- Backend abstraction for skills storage (filesystem, state, remote)
- Hot-reloading of skills
- Skill dependencies and versioning
- Skill execution monitoring and analytics
- Skill marketplace integration

## License

This module is part of DB-GPT and follows the same license.
