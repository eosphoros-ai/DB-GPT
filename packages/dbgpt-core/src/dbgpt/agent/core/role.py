"""Role class for role-based conversation."""

import functools
import logging
from abc import ABCMeta
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

from jinja2 import Environment, Template, meta
from jinja2.sandbox import SandboxedEnvironment

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
    from .base_agent import ConversableAgent

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


class AgentRunMode(str, Enum):
    """Agent run mode."""

    DEFAULT = "default"
    # Run the agent in loop mode, until the conversation is over(Maximum retries or
    # encounter a stop signal)
    LOOP = "loop"


class Role:
    """Role class for role-based conversation."""

    profile: ProfileConfig = ProfileConfig()
    language: str = "en"

    @classmethod
    def curr_cls_role(cls) -> str:
        profile = cls.profile.create_profile(prefer_prompt_language=cls.language)
        return profile.get_role()

    @classmethod
    def curr_cls_name(cls) -> str:
        profile = cls.profile.create_profile(prefer_prompt_language=cls.language)
        return profile.get_name()

    @classmethod
    def curr_cls_goal(cls) -> Optional[str]:
        profile = cls.profile.create_profile(prefer_prompt_language=cls.language)
        return profile.get_goal()

    def __init__(
        self,
        profile: ProfileConfig,
        memory: AgentMemory,
        fixed_subgoal: Optional[str] = None,
        language: str = "en",
        is_human: bool = False,
        is_team: bool = False,
        template_env: Optional[SandboxedEnvironment] = None,
    ):
        self.profile = profile
        self.memory = memory
        self.fixed_subgoal = fixed_subgoal
        self.language = language
        self.is_human = is_human
        self.is_team = is_team
        self.template_env = template_env or SandboxedEnvironment()

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
    def avatar(self) -> Optional[str]:
        """Return the goal of the role."""
        return self.current_profile.get_avatar()

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


class ConversableAgentMeta(ABCMeta):
    """
    Metaclass for ConversableAgent to handle initialization defaults and compatibility.

    This metaclass provides automatic default value injection for ConversableAgent subclasses,
    allowing users to define class-level field defaults that are automatically applied during
    instance creation, similar to pydantic BaseModel behavior but without the dependency.
    """

    @classmethod
    def _collect_field_defaults(
        cls, namespace: Dict[str, Any], bases: tuple
    ) -> Dict[str, Any]:
        """
        Collect all field default values defined as class attributes.

        This method scans both the current class and its base classes to find type-annotated
        attributes that have default values assigned. It handles inheritance properly by
        allowing subclasses to override parent class defaults.

        Args:
            namespace: The class namespace containing the class attributes and methods
            bases: Tuple of base classes in the class hierarchy

        Returns:
            Dict mapping field names to their default values

        Example:
            class MyAgent(ConversableAgent):
                profile: ProfileConfig = ProfileConfig(name="MyAgent")
                max_retry_count: int = 5

            # This method would return:
            # {'profile': ProfileConfig(name="MyAgent"), 'max_retry_count': 5}
        """
        defaults = {}

        # First, collect defaults from the current class being defined
        # We only consider type-annotated fields that have actual values assigned
        annotations = namespace.get("__annotations__", {})
        for field_name in annotations:
            # Check if this field has a value assigned in the class definition
            if (
                field_name in namespace
                and not field_name.startswith("_")  # Skip private/magic attributes
                and not callable(namespace.get(field_name))
            ):  # Skip methods
                defaults[field_name] = namespace[field_name]
                logger.debug(
                    f"Collected field default from current class: {field_name}"
                )

        # Then, collect defaults from base classes (in reverse MRO order)
        # This ensures proper inheritance: parent defaults are collected first,
        # then can be overridden by child class defaults
        for base_class in reversed(bases):
            if hasattr(base_class, "__annotations__"):
                try:
                    base_annotations = getattr(base_class, "__annotations__", {})
                    for field_name in base_annotations:
                        # Only add if not already defined in a subclass (child overrides parent)
                        # and the base class actually has this attribute with a non-callable value
                        if (
                            field_name not in defaults  # Preserve child class overrides
                            and hasattr(base_class, field_name)
                            and not field_name.startswith("_")
                        ):  # Skip private attributes
                            field_value = getattr(base_class, field_name)
                            if not callable(field_value):  # Skip methods and functions
                                defaults[field_name] = field_value
                                logger.debug(
                                    f"Collected field default from base class {base_class.__name__}: {field_name}"
                                )

                except (AttributeError, RuntimeError) as e:
                    # Handle cases where base class attribute access fails
                    # This can happen with complex inheritance or dynamic attributes
                    logger.debug(
                        f"Failed to collect defaults from base class {base_class}: {e}"
                    )
                    continue

        logger.debug(f"Total collected field defaults: {list(defaults.keys())}")
        return defaults

    @classmethod
    def _apply_defaults(cls, func: F, field_defaults: Dict[str, Any]) -> F:
        """
        Create a wrapper function that applies default values before calling the original __init__.

        This decorator intercepts the __init__ call and automatically injects default values
        for any parameters that weren't explicitly provided by the caller.

        Args:
            func: The original __init__ method
            field_defaults: Dictionary of field names to default values collected from class attributes

        Returns:
            Wrapped function that applies defaults before calling the original
        """

        # Define all known parameters that ConversableAgent and its parents accept
        # This avoids the need to inspect function signatures which can be unreliable
        # when users define __init__ with *args, **kwargs
        KNOWN_PARAMS = {
            # Role parameters (inherited from Role class)
            "profile",
            "memory",
            "fixed_subgoal",
            "language",
            "is_human",
            "is_team",
            "template_env",
            # Agent parameters (specific to ConversableAgent)
            "agent_context",
            "actions",
            "resource",
            "llm_config",
            "bind_prompt",
            "run_mode",
            "max_retry_count",
            "max_timeout",
            "llm_client",
            "stream_out",
            "show_reference",
            "executor",
        }

        @functools.wraps(func)
        def apply_defaults(self: "ConversableAgent", *args: Any, **kwargs: Any) -> Any:
            logger.debug(f"Applying defaults for {self.__class__.__name__}.__init__")
            logger.debug(f"Field defaults available: {list(field_defaults.keys())}")

            # Priority 1: Apply class-level field defaults (highest priority)
            # These are defaults defined as class attributes like: profile = ProfileConfig(...)
            for param_name, default_value in field_defaults.items():
                if param_name not in kwargs and param_name in KNOWN_PARAMS:
                    kwargs[param_name] = default_value
                    logger.debug(f"Applied field default: {param_name}")

            # Priority 2: Apply built-in framework defaults (lower priority)
            # These are sensible defaults for common parameters when not specified by class attributes
            builtin_defaults = {
                "actions": [],  # Empty action list by default
                "max_retry_count": 3,  # Standard retry count
                "max_timeout": 600,  # 10 minutes timeout
                "stream_out": True,  # Enable streaming by default
                "show_reference": False,  # Don't show references by default
            }

            for param_name, default_value in builtin_defaults.items():
                if (
                    param_name not in kwargs
                    and param_name in KNOWN_PARAMS
                    and param_name not in field_defaults
                ):  # Only if not overridden by class attribute
                    kwargs[param_name] = default_value
                    logger.debug(f"Applied builtin default: {param_name}")

            # Special handling for executor: create a new ThreadPoolExecutor instance
            # This needs to be created fresh for each instance to avoid sharing executors
            if "executor" not in kwargs and "executor" not in field_defaults:
                kwargs["executor"] = ThreadPoolExecutor(max_workers=1)
                logger.debug("Applied default ThreadPoolExecutor")

            return func(self, *args, **kwargs)

        return cast(F, apply_defaults)

    def __new__(cls, name, bases, namespace, **kwargs):
        """
        Create a new ConversableAgent class with automatic default value handling.

        This method is called when a new class inheriting from ConversableAgent is defined.
        It collects field defaults and wraps the __init__ method to apply them automatically.

        Args:
            name: Name of the class being created
            bases: Tuple of base classes
            namespace: Class namespace dictionary
            **kwargs: Additional keyword arguments

        Returns:
            The new class with enhanced __init__ method
        """

        # Collect all field defaults from class attributes
        field_defaults = cls._collect_field_defaults(namespace, bases)

        # Create the new class using the standard metaclass machinery
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)

        # Store field defaults on the class for introspection and debugging
        new_cls._field_defaults = field_defaults

        # Wrap the __init__ method to apply defaults automatically
        # We check if __init__ exists in current namespace or any base class
        if "__init__" in namespace or any(hasattr(base, "__init__") for base in bases):
            original_init = new_cls.__init__
            new_cls.__init__ = cls._apply_defaults(original_init, field_defaults)
            logger.debug(f"Enhanced {name}.__init__ with default value injection")

        # Allow classes to define post-creation hooks
        if hasattr(new_cls, "after_define"):
            new_cls.after_define()

        return new_cls
