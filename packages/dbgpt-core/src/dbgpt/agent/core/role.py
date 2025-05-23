"""Role class for role-based conversation."""

from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Type, Union

from jinja2 import Environment, Template, meta
from jinja2.sandbox import SandboxedEnvironment

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

from .action.base import ActionOutput
from .memory.agent_memory import (
    AgentMemory,
    AgentMemoryFragment,
    StructuredAgentMemoryFragment,
)
from .memory.llm import LLMImportanceScorer, LLMInsightExtractor
from .profile import Profile, ProfileConfig

if TYPE_CHECKING:
    from .agent import AgentMessage


class AgentRunMode(str, Enum):
    """Agent run mode."""

    DEFAULT = "default"
    # Run the agent in loop mode, until the conversation is over(Maximum retries or
    # encounter a stop signal)
    LOOP = "loop"


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
        resource_vars: Optional[Dict] = None,
        is_retry_chat: bool = False,
        **kwargs,
    ) -> str:
        """Return the prompt template for the role.

        Returns:
            str: The prompt template.
        """
        if is_system:
            return self.current_profile.format_system_prompt(
                template_env=self.template_env,
                question=question,
                language=self.language,
                most_recent_memories=most_recent_memories,
                resource_vars=resource_vars,
                is_retry_chat=is_retry_chat,
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

    def identity_check(self) -> None:
        """Check the identity of the role."""
        pass

    def get_name(self) -> str:
        """Get the name of the role."""
        return self.current_profile.get_name()

    @property
    def current_profile(self) -> Profile:
        """Return the current profile."""
        profile = self.profile.create_profile(prefer_prompt_language=self.language)
        return profile

    def prompt_template(
        self,
        template_format: str = "f-string",
        language: str = "en",
        is_retry_chat: bool = False,
    ) -> str:
        """Get agent prompt template."""
        self.language = language
        system_prompt = self.current_profile.get_system_prompt_template()
        template = Template(system_prompt)

        env = Environment()
        parsed_content = env.parse(system_prompt)
        variables = meta.find_undeclared_variables(parsed_content)

        role_params = {
            "role": self.role,
            "name": self.name,
            "goal": self.goal,
            "retry_goal": self.retry_goal,
            "expand_prompt": self.expand_prompt,
            "language": language,
            "constraints": self.constraints,
            "retry_constraints": self.retry_constraints,
            "examples": self.examples,
            "is_retry_chat": is_retry_chat,
        }
        param = role_params.copy()
        runtime_param_names = []
        for variable in variables:
            if variable not in role_params:
                runtime_param_names.append(variable)

        if template_format == "f-string":
            input_params = {}
            for variable in runtime_param_names:
                input_params[variable] = "{" + variable + "}"
            param.update(input_params)
        else:
            input_params = {}
            for variable in runtime_param_names:
                input_params[variable] = "{{" + variable + "}}"
            param.update(input_params)

        prompt_template = template.render(param)
        return prompt_template

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
    def retry_goal(self) -> Optional[str]:
        """Return the retry goal of the role."""
        return self.current_profile.get_retry_goal()

    @property
    def constraints(self) -> Optional[List[str]]:
        """Return the constraints of the role."""
        return self.current_profile.get_constraints()

    @property
    def retry_constraints(self) -> Optional[List[str]]:
        """Return the retry constraints of the role."""
        return self.current_profile.get_retry_constraints()

    @property
    def desc(self) -> Optional[str]:
        """Return the description of the role."""
        return self.current_profile.get_description()

    @property
    def expand_prompt(self) -> Optional[str]:
        """Return the expand prompt introduction of the role."""
        return self.current_profile.get_expand_prompt()

    @property
    def write_memory_template(self) -> str:
        """Return the current save memory template."""
        return self.current_profile.get_write_memory_template()

    @property
    def examples(self) -> Optional[str]:
        """Return the current example template."""
        return self.current_profile.get_examples()

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

    @property
    def memory_fragment_class(self) -> Type[AgentMemoryFragment]:
        """Return the memory fragment class."""
        return AgentMemoryFragment

    async def read_memories(
        self,
        question: str,
    ) -> Union[str, List["AgentMessage"]]:
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
        current_retry_counter: Optional[int] = None,
    ) -> AgentMemoryFragment:
        """Write the memories to the memory.

        We suggest you to override this method to save the conversation to memory
        according to your needs.

        Args:
            question(str): The question received.
            ai_message(str): The AI message, LLM output.
            action_output(ActionOutput): The action output.
            check_pass(bool): Whether the check pass.
            check_fail_reason(str): The check fail reason.
            current_retry_counter(int): The current retry counter.

        Returns:
            AgentMemoryFragment: The memory fragment created.
        """
        if not action_output:
            raise ValueError("Action output is required to save to memory.")

        mem_thoughts = action_output.thoughts or ai_message
        action = action_output.action
        action_input = action_output.action_input
        observation = check_fail_reason or action_output.observations

        memory_map = {
            "thought": mem_thoughts,
            "action": action,
            "observation": observation,
        }
        if action_input:
            memory_map["action_input"] = action_input

        if current_retry_counter is not None and current_retry_counter == 0:
            memory_map["question"] = question

        write_memory_template = self.write_memory_template
        memory_content = self._render_template(write_memory_template, **memory_map)

        fragment_cls: Type[AgentMemoryFragment] = self.memory_fragment_class
        if issubclass(fragment_cls, StructuredAgentMemoryFragment):
            fragment = fragment_cls(memory_map)
        else:
            fragment = fragment_cls(memory_content)
        await self.memory.write(fragment)

        action_output.memory_fragments = {
            "memory": fragment.raw_observation,
            "id": fragment.id,
            "importance": fragment.importance,
        }
        return fragment

    async def recovering_memory(self, action_outputs: List[ActionOutput]) -> None:
        """Recover the memory from the action outputs."""
        fragments = []
        fragment_cls: Type[AgentMemoryFragment] = self.memory_fragment_class
        for action_output in action_outputs:
            if action_output.memory_fragments:
                fragment = fragment_cls.build_from(
                    observation=action_output.memory_fragments["memory"],
                    importance=action_output.memory_fragments.get("importance"),
                    memory_id=action_output.memory_fragments.get("id"),
                )
                fragments.append(fragment)
        await self.memory.write_batch(fragments)
