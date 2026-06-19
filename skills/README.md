# SKILL Mechanism - DB-GPT Agent Skill Loading System

## Overview

The SKILL mechanism is an advanced feature of the DB-GPT Agent framework. It allows agents to load and manage predefined skill packages, enabling modular and reusable agent capabilities.

## Core Files

```
packages/dbgpt-core/src/dbgpt/agent/skill/
├── __init__.py           # Module entry point, exports main classes
├── base.py              # Skill base class definitions
├── parameters.py        # Skill parameter classes
├── manage.py           # Skill manager
└── loader.py           # Skill loader and builder
```

## Key Features

### 1. Skill Definition

A skill includes the following components:
- **Metadata**: Skill metadata (name, description, version, type, tags)
- **Prompt Template**: System prompt template
- **Required Tools**: List of required tools
- **Required Knowledge**: List of required knowledge bases
- **Actions**: Executable actions
- **Config**: Skill-specific configuration parameters

### 2. Skill Types

| Type | Description |
|------|-------------|
| `Coding` | Programming skills |
| `DataAnalysis` | Data analysis skills |
| `WebSearch` | Web search skills |
| `KnowledgeQA` | Knowledge Q&A skills |
| `Chat` | Conversation skills |
| `Custom` | Custom skills |

## Quick Start

### 1. Create a Skill

```python
from dbgpt.agent.skill import SkillBuilder, SkillType

skill = (
    SkillBuilder(name="my_skill", description="My awesome skill")
    .with_version("1.0.0")
    .with_author("Your Name")
    .with_skill_type(SkillType.Coding)
    .with_tags(["coding", "python"])
    .with_prompt_template(
        "You are a coding assistant. Help users write clean, efficient code."
    )
    .with_required_tool("python_interpreter")
    .build()
)
```

### 2. Register a Skill

```python
from dbgpt.agent.skill import get_skill_manager, initialize_skill
from dbgpt.component import SystemApp

system_app = SystemApp()
initialize_skill(system_app)
skill_manager = get_skill_manager(system_app)

skill_manager.register_skill(
    skill_instance=skill,
    name="my_awesome_skill",
)
```

### 3. Create a Skill-based Agent

```python
from dbgpt.agent import ConversableAgent
from dbgpt.agent.skill import Skill

class SkillBasedAgent(ConversableAgent):
    def __init__(self, skill: Skill, **kwargs):
        super().__init__(**kwargs)
        self._skill = skill
        self._apply_skill_to_profile()

    @property
    def skill(self) -> Skill:
        return self._skill
```

### 4. Use the Agent

```python
agent = SkillBasedAgent(skill=skill)
await agent.bind(context).bind(llm_config).bind(memory).build()
```

## API Reference

### SkillBuilder

| Method | Parameters | Description |
|------|------|------|
| `with_version(version)` | version: str | Set version |
| `with_author(author)` | author: str | Set author |
| `with_skill_type(type)` | type: SkillType | Set skill type |
| `with_tags(tags)` | tags: List[str] | Set tags |
| `with_prompt_template(template)` | template: str | Set prompt template |
| `with_required_tool(name)` | name: str | Add required tool |
| `with_required_knowledge(name)` | name: str | Add required knowledge base |
| `with_action(action)` | action: Any | Add action |
| `with_config(config)` | config: Dict | Set configuration |
| `build()` | - | Build skill |

### SkillManager

| Method | Parameters | Return Value | Description |
|------|------|--------|------|
| `register_skill()` | skill_cls, skill_instance, name, metadata | None | Register skill |
| `get_skill()` | name, skill_type, version | SkillBase | Get skill |
| `get_skills_by_type()` | skill_type | List[SkillBase] | Get skills by type |
| `list_skills()` | - | List[Dict] | List all skills |

### SkillLoader

| Method | Parameters | Return Value | Description |
|------|------|--------|------|
| `load_skill_from_file()` | file_path | Optional[SkillBase] | Load skill from file |
| `load_skill_from_module()` | module_path | Optional[SkillBase] | Load skill from module |
| `load_skills_from_directory()` | directory, recursive | List[SkillBase] | Load all skills from directory |

## File Formats

### JSON Format

```json
{
  "metadata": {
    "name": "web_search_assistant",
    "description": "Web search assistant",
    "version": "1.0.0",
    "author": "DB-GPT Team",
    "skill_type": "web_search",
    "tags": ["web", "search"]
  },
  "prompt_template": "You are a web search assistant.",
  "required_tools": ["google_search"],
  "required_knowledge": [],
  "config": {}
}
```

### Python Format

```python
from dbgpt.agent.skill import Skill, SkillMetadata, SkillType
from dbgpt.core import PromptTemplate

class CustomSkill(Skill):
    def __init__(self):
        metadata = SkillMetadata(
            name="custom_skill",
            description="A custom skill",
            version="1.0.0",
            skill_type=SkillType.Custom,
        )
        prompt = PromptTemplate.from_template("You are a custom assistant.")
        super().__init__(
            metadata=metadata,
            prompt_template=prompt,
        )
```

## Examples

### Complete Example

See `examples/agents/skill_agent_example.py` for a full usage example.

### Skill Files

- `skills/web_search_skill.json` - Web search skill example
- `skills/data_analysis_skill.json` - Data analysis skill example

### Implementation Guides

- `skills/skill_implementation_guide.py` - Detailed implementation guide
- `skills/INTEGRATION_GUIDE.md` - Guide for integrating skills into existing agents

## Integration Steps

1. **Import the SKILL module**
   ```python
   from dbgpt.agent.skill import Skill, SkillBuilder, get_skill_manager
   ```

2. **Modify the Agent class**
   ```python
   class MyAgent(ConversableAgent):
       def __init__(self, skill: Optional[Skill] = None, **kwargs):
           super().__init__(**kwargs)
           self._skill = skill
           if self._skill:
               self._apply_skill_to_profile()
   ```

3. **Initialize the Skill Manager**
   ```python
   from dbgpt.component import SystemApp
   system_app = SystemApp()
   initialize_skill(system_app)
   ```

4. **Register and use the skill**
   ```python
   skill_manager = get_skill_manager(system_app)
   skill_manager.register_skill(skill_instance=skill)
   agent = MyAgent(skill=skill)
   ```

## Advanced Usage

### Dynamic Skill Switching

```python
class DynamicSkillAgent(ConversableAgent):
    def switch_skill(self, skill_name: str):
        self._skill = self._skills[skill_name]
        self._apply_skill_to_profile()
```

### Multi-Skill Composition

```python
class CompositeSkillAgent(ConversableAgent):
    def __init__(self, skills: List[Skill], **kwargs):
        super().__init__(**kwargs)
        self._skills = skills

    def get_all_tools(self) -> List[str]:
        all_tools = []
        for skill in self._skills:
            all_tools.extend(skill.required_tools)
        return list(set(all_tools))
```

## Best Practices

1. **Modular design**: Each skill should focus on a single domain
2. **Version management**: Use semantic versioning (e.g., 1.0.0)
3. **Dependency declaration**: Clearly declare required tools and knowledge bases
4. **Documentation**: Write detailed documentation for each skill
5. **Test coverage**: Write unit tests for each skill

## Troubleshooting

### Common Issues

**Q: Skill failed to load?**
A: Check the file path and verify the JSON format is correct

**Q: Required tool not found?**
A: Ensure all required tools are provided when binding the agent

**Q: Prompt template not taking effect?**
A: Ensure `bind_prompt` is set correctly in `_apply_skill_to_profile`

## Contributing

Contributions of new skills are welcome! Please follow these steps:

1. Fork the project
2. Create a new skill file
3. Write tests
4. Submit a Pull Request

## License

MIT License

## Contact

For questions or suggestions, please open an Issue or Pull Request.
