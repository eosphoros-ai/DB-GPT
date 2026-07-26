"""Role class for role-based conversation."""

import json
import logging
import os
from abc import ABC
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Type, Union

from jinja2 import Environment, meta
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

logger = logging.getLogger(__name__)

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

    # Task progress tracking: list of dicts with keys 'step', 'action', 'phase'
    # This is NOT a pydantic field - managed as a plain instance attribute
    # so it survives across retry rounds without being serialised into memory.
    _task_progress: List[Dict] = []

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
        # Render via the sandboxed environment to prevent SSTI from any
        # user-controlled content that reaches the system prompt template.
        template = self.template_env.from_string(system_prompt)

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

    @property
    def task_progress_summary(self) -> Optional[str]:
        """Return a human-readable task progress summary.

        Lists every action the agent has taken so far, marking the last entry as
        the most recent step.  The summary is injected into every LLM call so the
        model never forgets what has already been done and what still needs to be
        done to complete the original task.
        """
        progress = getattr(self, "_task_progress", [])
        if not progress:
            return None
        lines = ["## Task Progress (do NOT repeat completed steps)"]
        for entry in progress:
            step = entry.get("step", "?")
            action = entry.get("action", "")
            phase = entry.get("phase", "")
            action_intention = entry.get("action_intention", "")
            status = entry.get("status", "done")
            snapshot_file = entry.get("snapshot_file", "")
            icon = "\u2705" if status == "done" else "\u274c"
            line = f"{icon} Step {step}: Action={action}"
            if action_intention:
                line += f" | Intention: {action_intention}"
            if phase:
                line += f" | Phase: {phase}"
            if snapshot_file:
                line += f" | ref: {os.path.basename(snapshot_file)}"
            lines.append(line)
        return "\n".join(lines)

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
        phase = action_output.phase if hasattr(action_output, "phase") else None
        action_intention = (
            action_output.action_intention
            if hasattr(action_output, "action_intention")
            else None
        )
        action_reason = (
            action_output.action_reason
            if hasattr(action_output, "action_reason")
            else None
        )
        observation = check_fail_reason or action_output.observations

        memory_map = {
            "thought": mem_thoughts,
            "action": action,
            "observation": observation,
        }
        if action_input:
            memory_map["action_input"] = action_input
        if phase:
            memory_map["phase"] = phase
        if action_intention:
            memory_map["action_intention"] = action_intention
        if action_reason:
            memory_map["action_reason"] = action_reason

        if current_retry_counter is not None and current_retry_counter == 0:
            memory_map["question"] = question

        # ------------------------------------------------------------------
        # Maintain task progress tracking (survives buffer eviction).
        # _task_progress is a plain list on the instance, NOT a pydantic field,
        # so it is never serialised/deserialised and stays in memory for the full
        # lifetime of the agent object.
        # ------------------------------------------------------------------
        snapshot_path: Optional[str] = None
        if check_pass and action:
            if not hasattr(self, "_task_progress") or self._task_progress is None:
                object.__setattr__(self, "_task_progress", [])
            progress: List[Dict] = self._task_progress  # type: ignore[assignment]
            step_num = (current_retry_counter or 0) + 1
            # Estimate observation tokens for budget tracking
            obs_tokens = len(observation) // 4 if observation else 0
            # Write full operation detail to a snapshot file so Layer 1/2
            # compaction never loses precise values (action_input, observation).
            snapshot_path = self._write_op_snapshot(
                step=step_num,
                action=action,
                action_input=action_input,
                observation=observation,
                thought=mem_thoughts,
                phase=phase,
                action_intention=action_intention,
                action_reason=action_reason,
            )
            progress.append(
                {
                    "step": step_num,
                    "action": action,
                    "phase": phase or "",
                    "action_intention": action_intention or "",
                    "action_reason": action_reason or "",
                    "status": "done",
                    "observation_tokens": obs_tokens,
                    "snapshot_file": snapshot_path or "",
                }
            )

        write_memory_template = self.write_memory_template
        memory_content = self._render_template(write_memory_template, **memory_map)

        fragment_cls: Type[AgentMemoryFragment] = self.memory_fragment_class
        if issubclass(fragment_cls, StructuredAgentMemoryFragment):
            fragment = fragment_cls(memory_map)
        else:
            fragment = fragment_cls(memory_content)
        fragment.snapshot_path = snapshot_path
        await self.memory.write(fragment)

        action_output.memory_fragments = {
            "memory": fragment.raw_observation,
            "id": fragment.id,
            "importance": fragment.importance,
        }
        return fragment

    def _write_op_snapshot(
        self,
        step: int,
        action: str,
        action_input: Optional[str],
        observation: Optional[str],
        thought: Optional[str],
        phase: Optional[str],
        action_intention: Optional[str] = None,
        action_reason: Optional[str] = None,
    ) -> Optional[str]:
        """Write a full operation snapshot to disk and return the file path.

        The snapshot preserves the complete action_input and observation so that
        Layer 1 / Layer 2 compaction never loses precise values (file paths,
        computed results, variable names, etc.).  The agent can later recover the
        detail by reading this file via a ``read_file`` action.

        Returns the absolute path of the written file, or None if no output_dir
        is available on the agent context.
        """
        # Resolve the base directory from AgentContext.output_dir, falling back
        # to DBGPT_HOME/workspace/op_snapshots.
        output_dir: Optional[str] = None
        ctx = getattr(self, "agent_context", None)
        if ctx is not None:
            output_dir = getattr(ctx, "output_dir", None)
        if not output_dir:
            home = os.environ.get("DBGPT_HOME", os.path.expanduser("~/.dbgpt"))
            output_dir = os.path.join(home, "workspace", "op_snapshots")

        conv_id = ""
        if ctx is not None:
            conv_id = getattr(ctx, "conv_id", "") or ""

        snapshot_dir = os.path.join(output_dir, conv_id) if conv_id else output_dir
        try:
            os.makedirs(snapshot_dir, exist_ok=True)
            safe_action = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in action
            )
            filename = f"step_{step:03d}_{safe_action}.json"
            filepath = os.path.join(snapshot_dir, filename)
            payload = {
                "step": step,
                "action": action,
                "phase": phase or "",
                "action_intention": action_intention or "",
                "action_reason": action_reason or "",
                "thought": thought or "",
                "action_input": action_input or "",
                "observation": observation or "",
                "timestamp": datetime.utcnow().isoformat(),
                "conv_id": conv_id,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception:
            logger.exception(
                "Failed to write op snapshot for step %d action %s", step, action
            )
            return None

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
