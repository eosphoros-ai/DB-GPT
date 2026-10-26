"""Integration of Claude-style SKILL mechanism with DB-GPT agents.

This module provides utilities to use Claude-style SKILL files
with DB-GPT's ConversableAgent.
"""

from typing import List, Optional

from dbgpt.agent.core.agent import AgentContext
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.core import PromptTemplate

from . import FileBasedSkill, SkillRegistry, get_registry


class ClaudeSkillAgent(ConversableAgent):
    """Agent that uses Claude-style SKILL files.

    This agent automatically detects which SKILL to use based on user input
    and applies the corresponding instructions to the prompt.
    """

    def __init__(self, skill_registry: Optional[SkillRegistry] = None, **kwargs):
        """Initialize a Claude Skill Agent.

        Args:
            skill_registry: Skill registry instance (uses global if None).
            **kwargs: Additional arguments for ConversableAgent.
        """
        super().__init__(**kwargs)
        self._skill_registry = skill_registry or get_registry()
        self._current_skill: Optional[FileBasedSkill] = None
        self._base_prompt: Optional[PromptTemplate] = None

    @property
    def skill_registry(self) -> SkillRegistry:
        """Return the skill registry."""
        return self._skill_registry

    @property
    def current_skill(self) -> Optional[FileBasedSkill]:
        """Return the currently active skill."""
        return self._current_skill

    def detect_and_apply_skill(self, user_input: str):
        """Detect and apply a matching skill for the user input.

        Args:
            user_input: The user's input message.
        """
        matching_skill = self._skill_registry.match_skill(user_input)

        if matching_skill:
            self._current_skill = matching_skill
            self._apply_skill_to_prompt()
        else:
            self._current_skill = None

    def set_skill(self, skill_name: str):
        """Manually set a specific skill.

        Args:
            skill_name: Name of the skill to activate.

        Raises:
            ValueError: If skill not found.
        """
        skill = self._skill_registry.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")

        self._current_skill = skill
        self._apply_skill_to_prompt()

    def clear_skill(self):
        """Clear the current skill and revert to base prompt."""
        self._current_skill = None
        if self._base_prompt:
            self.bind_prompt = self._base_prompt

    def _apply_skill_to_prompt(self):
        """Apply the current skill's prompt template."""
        if self._current_skill:
            if self.bind_prompt is None:
                self._base_prompt = self.bind_prompt

            skill_prompt = self._current_skill.get_prompt()

            if self.bind_prompt:
                combined = f"{skill_prompt.template}\n\n{self.bind_prompt.template}"
            else:
                combined = skill_prompt.template

            # 技能指令已经转义成 Jinja2 字面量，这里必须继续用 jinja2 渲染，
            # 否则转义序列会被 f-string 规则二次解析。
            self.bind_prompt = PromptTemplate.from_template(
                combined, template_format="jinja2", template_is_strict=False
            )

    async def generate_reply(
        self,
        received_message,
        sender,
        reviewer=None,
        rely_messages=None,
        historical_dialogues=None,
        is_retry_chat=False,
        last_speaker_name=None,
        **kwargs,
    ):
        """Generate a reply with skill detection.

        Args:
            received_message: The received message.
            sender: Sender agent.
            reviewer: Reviewer agent.
            rely_messages: List of relied messages.
            historical_dialogues: Historical dialogue messages.
            is_retry_chat: Whether this is a retry.
            last_speaker_name: Name of the last speaker.
            **kwargs: Additional arguments.

        Returns:
            Generated reply message.
        """
        if received_message.content:
            self.detect_and_apply_skill(received_message.content)

        return await super().generate_reply(
            received_message,
            sender,
            reviewer,
            rely_messages,
            historical_dialogues,
            is_retry_chat,
            last_speaker_name,
            **kwargs,
        )

    def get_available_skills(self) -> List[str]:
        """Get list of available skill names.

        Returns:
            List of skill names.
        """
        return [skill.metadata.name for skill in self._skill_registry._skills.values()]


async def create_skill_agent(
    skill_dir: str,
    context: AgentContext,
    **kwargs,
) -> ClaudeSkillAgent:
    """Create a Claude Skill Agent with skills loaded from a directory.

    Args:
        skill_dir: Directory containing SKILL.md files.
        context: Agent context.
        **kwargs: Additional arguments for ConversableAgent.

    Returns:
        Configured ClaudeSkillAgent instance.
    """
    registry = get_registry()
    registry.load_from_directory(skill_dir, recursive=True)

    agent = ClaudeSkillAgent(skill_registry=registry, **kwargs)
    await agent.bind(context).build()

    return agent
