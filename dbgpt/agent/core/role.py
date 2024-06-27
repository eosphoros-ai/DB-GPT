"""Role class for role-based conversation."""

from abc import ABC
from typing import Any, Dict, List, Optional

from jinja2.sandbox import SandboxedEnvironment

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

from .action.base import ActionOutput
from .memory.agent_memory import AgentMemory, AgentMemoryFragment
from .memory.llm import LLMImportanceScorer, LLMInsightExtractor
from .profile import Profile, ProfileConfig


class Role(ABC, BaseModel):
    """Role class for role-based conversation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile: ProfileConfig = Field(
        ...,
        description="The profile of the role.",
    )
    memory: AgentMemory = Field(default_factory=AgentMemory)

    fixed_subgoal: Optional[str] = Field(None, description="Fixed subgoal")

    language: str = "en"
    is_human: bool = False
    is_team: bool = False

    template_env: SandboxedEnvironment = Field(default_factory=SandboxedEnvironment)

    async def build_prompt(
        self,
        question: Optional[str] = None,
        is_system: bool = True,
        most_recent_memories: Optional[str] = None,
        **kwargs
    ) -> str:
        """Return the prompt template for the role.

        Returns:
            str: The prompt template.
        """
        resource_vars = await self.generate_resource_variables(question)

        if is_system:
            return self.current_profile.format_system_prompt(
                template_env=self.template_env,
                question=question,
                language=self.language,
                most_recent_memories=most_recent_memories,
                resource_vars=resource_vars,
                **kwargs,
            )
        else:
            return self.current_profile.format_user_prompt(
                template_env=self.template_env,
                question=question,
                language=self.language,
                most_recent_memories=most_recent_memories,
                resource_vars=resource_vars,
                **kwargs,
            )

    async def generate_resource_variables(
        self, question: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate the resource variables."""
        return {}

    def identity_check(self) -> None:
        """Check the identity of the role."""
        pass

    def get_name(self) -> str:
        """Get the name of the role."""
        return self.current_profile.get_name()

    @property
    def current_profile(self) -> Profile:
        """Return the current profile."""
        profile = self.profile.create_profile()
        return profile

    @property
    def name(self) -> str:
        """Return the name of the role."""
        return self.current_profile.get_name()

    @property
    def role(self) -> str:
        """Return the role of the role."""
        return self.current_profile.get_role()

    @property
    def goal(self) -> Optional[str]:
        """Return the goal of the role."""
        return self.current_profile.get_goal()

    @property
    def constraints(self) -> Optional[List[str]]:
        """Return the constraints of the role."""
        return self.current_profile.get_constraints()

    @property
    def desc(self) -> Optional[str]:
        """Return the description of the role."""
        return self.current_profile.get_description()

    @property
    def write_memory_template(self) -> str:
        """Return the current save memory template."""
        return self.current_profile.get_write_memory_template()

    def _render_template(self, template: str, **kwargs):
        r_template = self.template_env.from_string(template)
        return r_template.render(**kwargs)

    @property
    def memory_importance_scorer(self) -> Optional[LLMImportanceScorer]:
        """Create the memory importance scorer.

        The memory importance scorer is used to score the importance of a memory
        fragment.
        """
        return None

    @property
    def memory_insight_extractor(self) -> Optional[LLMInsightExtractor]:
        """Create the memory insight extractor.

        The memory insight extractor is used to extract a high-level insight from a
        memory fragment.
        """
        return None

    async def read_memories(
        self,
        question: str,
    ) -> str:
        """Read the memories from the memory."""
        memories = await self.memory.read(question)
        recent_messages = [m.raw_observation for m in memories]
        return "".join(recent_messages)

    async def write_memories(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
    ) -> None:
        """Write the memories to the memory.

        We suggest you to override this method to save the conversation to memory
        according to your needs.

        Args:
            question(str): The question received.
            ai_message(str): The AI message, LLM output.
            action_output(ActionOutput): The action output.
            check_pass(bool): Whether the check pass.
            check_fail_reason(str): The check fail reason.
        """
        if not action_output:
            raise ValueError("Action output is required to save to memory.")

        mem_thoughts = action_output.thoughts or ai_message
        observation = action_output.observations
        if not check_pass and observation and check_fail_reason:
            observation += "\n" + check_fail_reason

        memory_map = {
            "question": question,
            "thought": mem_thoughts,
            "action": action_output.action,
            "observation": observation,
        }
        write_memory_template = self.write_memory_template
        memory_content = self._render_template(write_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
