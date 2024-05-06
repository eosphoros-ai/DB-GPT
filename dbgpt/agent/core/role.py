"""Role class for role-based conversation."""

from abc import ABC
from typing import Any, Dict, List, Optional, Set

from jinja2.meta import find_undeclared_variables
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
        prompt_template = (
            self.system_prompt_template if is_system else self.user_prompt_template
        )
        template_vars = self._get_template_variables(prompt_template)
        _sub_render_keys = {"role", "name", "goal", "expand_prompt", "constraints"}
        pass_vars = {
            "role": self.role,
            "name": self.name,
            "goal": self.goal,
            "expand_prompt": self.expand_prompt,
            "language": self.language,
            "constraints": self.constraints,
            "most_recent_memories": (
                most_recent_memories if most_recent_memories else None
            ),
            "examples": self.examples,
            # "out_schema": out_schema if out_schema else None,
            # "resource_prompt": resource_prompt if resource_prompt else None,
            "question": question,
        }
        resource_vars = await self.generate_resource_variables(question)
        pass_vars.update(resource_vars)
        pass_vars.update(kwargs)
        filtered_data = {
            key: pass_vars[key] for key in template_vars if key in pass_vars
        }
        for key in filtered_data.keys():
            value = filtered_data[key]
            if key in _sub_render_keys and value:
                if isinstance(value, str):
                    # Render the sub-template
                    filtered_data[key] = self._render_template(value, **pass_vars)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, str):
                            value[i] = self._render_template(item, **pass_vars)
        return self._render_template(prompt_template, **filtered_data)

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
    def examples(self) -> Optional[str]:
        """Return the examples of the role."""
        return self.current_profile.get_examples()

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
    def expand_prompt(self) -> Optional[str]:
        """Return the expand prompt of the role."""
        return self.current_profile.get_expand_prompt()

    @property
    def system_prompt_template(self) -> str:
        """Return the current system prompt template."""
        return self.current_profile.get_system_prompt_template()

    @property
    def user_prompt_template(self) -> str:
        """Return the current user prompt template."""
        return self.current_profile.get_user_prompt_template()

    @property
    def save_memory_template(self) -> str:
        """Return the current save memory template."""
        return self.current_profile.get_save_memory_template()

    def _get_template_variables(self, template: str) -> Set[str]:
        parsed_content = self.template_env.parse(template)
        return find_undeclared_variables(parsed_content)

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

    async def save_to_memory(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
    ) -> None:
        """Save the role to the memory."""
        if not action_output:
            raise ValueError("Action output is required to save to memory.")

        mem_thoughts = action_output.thoughts or ai_message
        observation = action_output.observations or action_output.content
        if not check_pass and check_fail_reason:
            observation += "\n" + check_fail_reason

        memory_map = {
            "question": question,
            "thought": mem_thoughts,
            "action": action_output.action,
            "observation": observation,
        }
        save_memory_template = self.save_memory_template
        memory_content = self._render_template(save_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
