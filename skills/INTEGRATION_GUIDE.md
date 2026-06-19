# SKILL Mechanism Integration Guide

This document explains how to integrate the SKILL mechanism into existing DB-GPT agents.

## Integration Steps

### 1. Import the SKILL Module

Add the following imports to files that need SKILL support:

```python
from dbgpt.agent.skill import (
    Skill,
    SkillBuilder,
    SkillLoader,
    SkillManager,
    SkillType,
    get_skill_manager,
    initialize_skill,
)
```

### 2. Modify the Agent Class to Support Skills

Add skill support to your agent class:

```python
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.skill import Skill

class SkillEnabledAgent(ToolAssistantAgent):
    def __init__(self, skill: Optional[Skill] = None, **kwargs):
        super().__init__(**kwargs)
        self._skill = skill

        if self._skill:
            self._apply_skill_to_profile()

    @property
    def skill(self) -> Optional[Skill]:
        return self._skill

    def _apply_skill_to_profile(self):
        """Apply skill configuration to the agent profile."""
        if self.skill.prompt_template:
            self.bind_prompt = self.skill.prompt_template

        if self.profile:
            self.profile.goal = self.skill.metadata.description

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load resources required by the skill."""
        if self.skill:
            await self._load_skill_resources()
        return await super().load_resource(question, is_retry_chat)

    async def _load_skill_resources(self):
        """Load tools and knowledge required by the skill."""
        if not self.resource:
            return

        # Check required tools
        if self.skill.required_tools:
            available_tools = self.resource.get_resource_by_type("tool")
            available_tool_names = [t.name for t in available_tools]

            for required_tool in self.skill.required_tools:
                if required_tool not in available_tool_names:
                    raise ValueError(
                        f"Required tool '{required_tool}' not found. "
                        f"Available tools: {available_tool_names}"
                    )

        # Check required knowledge bases
        if self.skill.required_knowledge:
            available_knowledge = self.resource.get_resource_by_type("knowledge")
            available_knowledge_names = [k.name for k in available_knowledge]

            for required_knowledge in self.skill.required_knowledge:
                if required_knowledge not in available_knowledge_names:
                    raise ValueError(
                        f"Required knowledge '{required_knowledge}' not found. "
                        f"Available knowledge: {available_knowledge_names}"
                    )
```

### 3. Initialize the Skill Manager

Initialize the Skill Manager at application startup:

```python
from dbgpt.component import SystemApp

def initialize_app():
    system_app = SystemApp()
    initialize_skill(system_app)
    return system_app
```

### 4. Register Skills

```python
from dbgpt.agent.skill import get_skill_manager

def register_my_skills(system_app):
    skill_manager = get_skill_manager(system_app)

    # Create and register skill
    skill = (
        SkillBuilder(name="my_skill", description="My skill description")
        .with_skill_type(SkillType.Chat)
        .with_prompt_template("You are a helpful assistant.")
        .build()
    )

    skill_manager.register_skill(
        skill_instance=skill,
        name="my_skill",
    )
```

### 5. Create an Agent with a Skill

```python
from dbgpt.agent import AgentContext, LLMConfig, AgentMemory

async def create_agent_with_skill():
    # Get skill
    skill_manager = get_skill_manager()
    skill = skill_manager.get_skill(name="my_skill")

    # Create agent
    agent = SkillEnabledAgent(skill=skill)

    # Bind configuration
    context = AgentContext(conv_id="test_conv")
    llm_config = LLMConfig()
    memory = AgentMemory()

    await agent.bind(context).bind(llm_config).bind(memory).build()

    return agent
```

## Modifying an Existing Agent Example

### Example: Modifying IntentRecognitionAgent

Original file: `packages/dbgpt-serve/src/dbgpt_serve/agent/agents/expand/intent_recognition_agent.py`

```python
import logging
from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.agent.skill import Skill
from dbgpt_serve.agent.agents.expand.actions.intent_recognition_action import (
    IntentRecognitionAction,
)

class IntentRecognitionAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(...)

    def __init__(self, skill: Optional[Skill] = None, **kwargs):
        super().__init__(**kwargs)
        self._skill = skill
        self._init_actions([IntentRecognitionAction])

        if self._skill:
            self._apply_skill_to_profile()

    @property
    def skill(self) -> Optional[Skill]:
        return self._skill

    def _apply_skill_to_profile(self):
        if self.skill and self.skill.prompt_template:
            self.bind_prompt = self.skill.prompt_template

agent_manage = get_agent_manager()
agent_manage.register_agent(IntentRecognitionAgent)
```

## SKILL File Formats

### JSON Format

```json
{
  "metadata": {
    "name": "intent_recognition",
    "description": "Intent recognition skill for user queries",
    "version": "1.0.0",
    "author": "DB-GPT Team",
    "skill_type": "custom",
    "tags": ["intent", "recognition", "nlp"]
  },
  "prompt_template": "You are an intent recognition expert. Analyze user queries and identify their intents.",
  "required_tools": [],
  "required_knowledge": [],
  "config": {
    "max_intents": 10,
    "enable_slot_filling": true
  }
}
```

### Python Format

```python
from dbgpt.agent.skill import Skill, SkillMetadata, SkillType
from dbgpt.core import PromptTemplate

class IntentRecognitionSkill(Skill):
    def __init__(self):
        metadata = SkillMetadata(
            name="intent_recognition",
            description="Intent recognition skill",
            version="1.0.0",
            skill_type=SkillType.Custom,
            tags=["intent", "recognition"],
        )
        prompt = PromptTemplate.from_template(
            "You are an intent recognition expert."
        )
        super().__init__(
            metadata=metadata,
            prompt_template=prompt,
            config={"max_intents": 10},
        )
```

## Testing SKILL Integration

```python
import pytest
from dbgpt.agent.skill import SkillBuilder, SkillType

def test_skill_integration():
    # Create skill
    skill = (
        SkillBuilder(name="test_skill", description="Test skill")
        .build()
    )

    # Create agent
    agent = SkillEnabledAgent(skill=skill)

    # Verify
    assert agent.skill is not None
    assert agent.skill.metadata.name == "test_skill"
```

## Best Practices

1. **Separation of concerns**: Skills should focus on capabilities in a specific domain
2. **Version management**: Use semantic versioning for skills
3. **Dependency declaration**: Clearly declare tools and knowledge required by the skill
4. **Documentation**: Write detailed documentation and examples for each skill
5. **Test coverage**: Write unit tests for each skill

## FAQ

### Q: How do I dynamically switch skills?

A: Add a `switch_skill` method to the agent:

```python
def switch_skill(self, skill: Skill):
    self._skill = skill
    self._apply_skill_to_profile()
```

### Q: Can a skill include multiple tools?

A: Yes, call `with_required_tool` multiple times:

```python
skill = (
    SkillBuilder(name="multi_tool", description="Multi tool skill")
    .with_required_tool("tool1")
    .with_required_tool("tool2")
    .with_required_tool("tool3")
    .build()
)
```

### Q: How do I load a skill from a file?

A: Use `SkillLoader`:

```python
from dbgpt.agent.skill import SkillLoader

loader = SkillLoader()
skill = loader.load_skill_from_file("path/to/skill.json")
```
