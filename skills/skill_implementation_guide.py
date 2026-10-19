"""
Skill-based Agent Implementation Guide

This guide shows how to integrate SKILL loading mechanism into DB-GPT agents.
"""

# ============================================================================
# 1. Basic Skill Definition
# ============================================================================

import asyncio
from typing import Dict, List, Optional

from dbgpt.agent.skill import (
    Skill,
    SkillBuilder,
    SkillMetadata,
    SkillType,
)
from dbgpt.core import PromptTemplate


# Method 1: Define skill class
class CustomSkill(Skill):
    """Custom skill example."""

    def __init__(self):
        """Initialize custom skill."""
        metadata = SkillMetadata(
            name="custom_skill",
            description="A custom skill for specific tasks",
            version="1.0.0",
            skill_type=SkillType.Custom,
            tags=["custom", "example"],
        )
        prompt = PromptTemplate.from_template(
            "You are a custom assistant for specific tasks."
        )
        super().__init__(
            metadata=metadata,
            prompt_template=prompt,
            required_tools=["tool1", "tool2"],
            required_knowledge=["knowledge_base"],
        )


# Method 2: Use SkillBuilder
custom_skill = (
    SkillBuilder(name="my_skill", description="My awesome skill")
    .with_version("1.0.0")
    .with_author("Your Name")
    .with_skill_type(SkillType.Coding)
    .with_tags(["coding", "python"])
    .with_prompt_template(
        "You are a coding assistant. Help users write clean, efficient code."
    )
    .with_required_tool("python_interpreter")
    .with_config({"max_lines": 1000})
    .build()
)


# ============================================================================
# 2. Skill Registration
# ============================================================================

from dbgpt.agent.skill import get_skill_manager, initialize_skill
from dbgpt.component import SystemApp


def register_skills():
    """Register skills in the system."""
    system_app = SystemApp()
    initialize_skill(system_app)
    skill_manager = get_skill_manager(system_app)

    # Register skill instance
    skill_manager.register_skill(
        skill_instance=custom_skill,
        name="my_awesome_skill",
    )

    # List all skills
    skills = skill_manager.list_skills()
    print(f"Registered skills: {skills}")


# ============================================================================
# 3. Agent with Skill Integration
# ============================================================================

from dbgpt.agent import ConversableAgent
from dbgpt.agent.skill import Skill


class SkillBasedAgent(ConversableAgent):
    """Agent that uses a skill."""

    def __init__(self, skill: Skill, **kwargs):
        """Initialize agent with skill."""
        super().__init__(**kwargs)
        self._skill = skill
        self._apply_skill_to_profile()

    @property
    def skill(self) -> Skill:
        """Return the skill."""
        return self._skill

    def _apply_skill_to_profile(self):
        """Apply skill settings to agent profile."""
        if self.skill.prompt_template:
            self.bind_prompt = self.skill.prompt_template

        # Set profile based on skill metadata
        if self.profile:
            self.profile.goal = self.skill.metadata.description

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load resources required by the skill."""
        # Load required tools
        if self.skill.required_tools and self.resource:
            tools = self.resource.get_resource_by_type("tool")
            for tool_name in self.skill.required_tools:
                if tool_name not in [t.name for t in tools]:
                    raise ValueError(f"Required tool {tool_name} not found")

        # Load required knowledge
        if self.skill.required_knowledge and self.resource:
            knowledge = self.resource.get_resource_by_type("knowledge")
            for knowledge_name in self.skill.required_knowledge:
                if knowledge_name not in [k.name for k in knowledge]:
                    raise ValueError(f"Required knowledge {knowledge_name} not found")

        return await super().load_resource(question, is_retry_chat)


# ============================================================================
# 4. Skill Loading from Files
# ============================================================================

from dbgpt.agent.skill import SkillLoader


def load_skills_from_directory(directory: str):
    """Load all skills from a directory."""
    loader = SkillLoader()
    skills = loader.load_skills_from_directory(directory, recursive=True)

    system_app = SystemApp()
    initialize_skill(system_app)
    skill_manager = get_skill_manager(system_app)

    for skill in skills:
        skill_manager.register_skill(skill_instance=skill, name=skill.metadata.name)

    print(f"Loaded {len(skills)} skills from {directory}")


# ============================================================================
# 5. Dynamic Skill Switching
# ============================================================================


class DynamicSkillAgent(ConversableAgent):
    """Agent that can switch between different skills."""

    def __init__(self, **kwargs):
        """Initialize agent with dynamic skill support."""
        super().__init__(**kwargs)
        self._current_skill: Optional[Skill] = None
        self._available_skills: Dict[str, Skill] = {}

    def register_skill(self, skill: Skill):
        """Register a skill."""
        self._available_skills[skill.metadata.name] = skill

    def switch_skill(self, skill_name: str):
        """Switch to a different skill."""
        if skill_name not in self._available_skills:
            raise ValueError(f"Skill {skill_name} not found")

        self._current_skill = self._available_skills[skill_name]

        if self._current_skill.prompt_template:
            self.bind_prompt = self._current_skill.prompt_template

        print(f"Switched to skill: {skill_name}")

    @property
    def current_skill(self) -> Optional[Skill]:
        """Return the current skill."""
        return self._current_skill


# ============================================================================
# 6. Skill Composition (Multiple Skills)
# ============================================================================


class CompositeSkillAgent(ConversableAgent):
    """Agent that combines multiple skills."""

    def __init__(self, skills: List[Skill], **kwargs):
        """Initialize agent with multiple skills."""
        super().__init__(**kwargs)
        self._skills = skills

    def get_skill_by_type(self, skill_type: SkillType) -> Optional[Skill]:
        """Get skill by type."""
        for skill in self._skills:
            if skill.metadata.skill_type == skill_type:
                return skill
        return None

    def get_all_tools(self) -> List[str]:
        """Get all required tools from all skills."""
        all_tools = []
        for skill in self._skills:
            all_tools.extend(skill.required_tools)
        return list(set(all_tools))

    def combine_prompts(self) -> str:
        """Combine prompts from all skills."""
        prompts = []
        for skill in self._skills:
            if skill.prompt_template:
                prompts.append(skill.prompt_template.template)
        return "\n\n".join(prompts)


# ============================================================================
# 7. Usage Example
# ============================================================================


async def example_usage():
    """Example usage of skill-based agents."""
    from dbgpt.agent import AgentContext, LLMConfig, AgentMemory
    from dbgpt.agent.resource import tool

    @tool
    def search(query: str) -> str:
        """Search for information.

        Args:
            query: Search query.

        Returns:
            Search results.
        """
        return f"Search results for: {query}"

    # Create skill
    skill = (
        SkillBuilder(name="search_skill", description="Search assistant")
        .with_prompt_template("Help users search for information.")
        .with_required_tool("search")
        .build()
    )

    # Create agent with skill
    agent = SkillBasedAgent(skill=skill)

    # Bind necessary components
    context = AgentContext(conv_id="test_conv")
    llm_config = LLMConfig()
    memory = AgentMemory()

    await agent.bind(context).bind(llm_config).bind(memory).bind([search]).build()

    print("Agent created with skill!")
    print(f"Skill name: {agent.skill.metadata.name}")
    print(f"Required tools: {agent.skill.required_tools}")


if __name__ == "__main__":
    register_skills()
    asyncio.run(example_usage())
