"""Profile module."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

import cachetools
from jinja2.meta import find_undeclared_variables
from jinja2.sandbox import Environment, SandboxedEnvironment

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_validator
from dbgpt.util.configure import ConfigInfo, DynConfig

VALID_TEMPLATE_KEYS = {
    "role",
    "name",
    "goal",
    "resource_prompt",
    "expand_prompt",
    "language",
    "constraints",
    "examples",
    "out_schema",
    "most_recent_memories",
    "question",
}

_DEFAULT_SYSTEM_TEMPLATE = """\
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.
{% if resource_prompt %}\
{{ resource_prompt }} 
{% endif %}\
{% if expand_prompt %}\
{{ expand_prompt }} 
{% endif %}\

*** IMPORTANT REMINDER ***
{% if language == 'zh' %}\
Please answer in simplified Chinese.
{% else %}\
Please answer in English.
{% endif %}\

{% if constraints %}\
{% for constraint in constraints %}\
{{ loop.index }}. {{ constraint }}
{% endfor %}\
{% endif %}\

{% if examples %}\
You can refer to the following examples:
{{ examples }}\
{% endif %}\

{% if out_schema %} {{ out_schema }} {% endif %}\
"""  # noqa

_DEFAULT_USER_TEMPLATE = """\
{% if most_recent_memories %}\
Most recent observations:
{{ most_recent_memories }}
{% endif %}\

{% if question %}\
Question: {{ question }}
{% endif %}
"""

_DEFAULT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
"""


class Profile(ABC):
    """Profile interface."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of current agent."""

    @abstractmethod
    def get_role(self) -> str:
        """Return the role of current agent."""

    def get_goal(self) -> Optional[str]:
        """Return the goal of current agent."""
        return None

    def get_constraints(self) -> Optional[List[str]]:
        """Return the constraints of current agent."""
        return None

    def get_description(self) -> Optional[str]:
        """Return the description of current agent.

        It will not be used to generate prompt.
        """
        return None

    def get_expand_prompt(self) -> Optional[str]:
        """Return the expand prompt of current agent."""
        return None

    def get_examples(self) -> Optional[str]:
        """Return the examples of current agent."""
        return None

    @abstractmethod
    def get_system_prompt_template(self) -> str:
        """Return the prompt template of current agent."""

    @abstractmethod
    def get_user_prompt_template(self) -> str:
        """Return the user prompt template of current agent."""

    @abstractmethod
    def get_write_memory_template(self) -> str:
        """Return the save memory template of current agent."""

    def format_system_prompt(
        self,
        template_env: Optional[Environment] = None,
        question: Optional[str] = None,
        language: str = "en",
        most_recent_memories: Optional[str] = None,
        resource_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Format the system prompt.

        Args:
            template_env(Optional[Environment]): The template environment for jinja2.
            question(Optional[str]): The question.
            language(str): The language of current context.
            most_recent_memories(Optional[str]): The most recent memories, it reads
                from memory.
            resource_vars(Optional[Dict[str, Any]]): The resource variables.

        Returns:
            str: The formatted system prompt.
        """
        return self._format_prompt(
            self.get_system_prompt_template(),
            template_env=template_env,
            question=question,
            language=language,
            most_recent_memories=most_recent_memories,
            resource_vars=resource_vars,
            **kwargs
        )

    def format_user_prompt(
        self,
        template_env: Optional[Environment] = None,
        question: Optional[str] = None,
        language: str = "en",
        most_recent_memories: Optional[str] = None,
        resource_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Format the user prompt.

        Args:
            template_env(Optional[Environment]): The template environment for jinja2.
            question(Optional[str]): The question.
            language(str): The language of current context.
            most_recent_memories(Optional[str]): The most recent memories, it reads
                from memory.
            resource_vars(Optional[Dict[str, Any]]): The resource variables.

        Returns:
            str: The formatted user prompt.
        """
        return self._format_prompt(
            self.get_user_prompt_template(),
            template_env=template_env,
            question=question,
            language=language,
            most_recent_memories=most_recent_memories,
            resource_vars=resource_vars,
            **kwargs
        )

    @property
    def _sub_render_keys(self) -> Set[str]:
        """Return the sub render keys.

        If the value is a string and the key is in the sub render keys, it will be
            rendered.

        Returns:
            Set[str]: The sub render keys.
        """
        return {"role", "name", "goal", "expand_prompt", "constraints"}

    def _format_prompt(
        self,
        template: str,
        template_env: Optional[Environment] = None,
        question: Optional[str] = None,
        language: str = "en",
        most_recent_memories: Optional[str] = None,
        resource_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Format the prompt."""
        if not template_env:
            template_env = SandboxedEnvironment()
        pass_vars = {
            "role": self.get_role(),
            "name": self.get_name(),
            "goal": self.get_goal(),
            "expand_prompt": self.get_expand_prompt(),
            "language": language,
            "constraints": self.get_constraints(),
            "most_recent_memories": (
                most_recent_memories if most_recent_memories else None
            ),
            "examples": self.get_examples(),
            "question": question,
        }
        if resource_vars:
            # Merge resource variables
            pass_vars.update(resource_vars)
        pass_vars.update(kwargs)

        # Parse the template to find all variables in the template
        template_vars = find_undeclared_variables(template_env.parse(template))
        # Just keep the valid template key variables
        filtered_data = {
            key: pass_vars[key] for key in template_vars if key in pass_vars
        }

        def _render_template(_template_env, _template: str, **_kwargs):
            r_template = _template_env.from_string(_template)
            return r_template.render(**_kwargs)

        for key in filtered_data.keys():
            value = filtered_data[key]
            if key in self._sub_render_keys and value:
                if isinstance(value, str):
                    # Render the sub-template
                    filtered_data[key] = _render_template(
                        template_env, value, **pass_vars
                    )
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, str):
                            value[i] = _render_template(template_env, item, **pass_vars)
        return _render_template(template_env, template, **filtered_data)


class DefaultProfile(BaseModel, Profile):
    """Default profile."""

    name: str = Field("", description="The name of the agent.")
    role: str = Field("", description="The role of the agent.")
    goal: Optional[str] = Field(None, description="The goal of the agent.")
    constraints: Optional[List[str]] = Field(
        None, description="The constraints of the agent."
    )

    desc: Optional[str] = Field(
        None, description="The description of the agent, not used to generate prompt."
    )

    expand_prompt: Optional[str] = Field(
        None, description="The expand prompt of the agent."
    )

    examples: Optional[str] = Field(
        None, description="The examples of the agent prompt."
    )

    system_prompt_template: str = Field(
        _DEFAULT_SYSTEM_TEMPLATE, description="The system prompt template of the agent."
    )
    user_prompt_template: str = Field(
        _DEFAULT_USER_TEMPLATE, description="The user prompt template of the agent."
    )

    write_memory_template: str = Field(
        _DEFAULT_WRITE_MEMORY_TEMPLATE,
        description="The save memory template of the agent.",
    )

    def get_name(self) -> str:
        """Return the name of current agent."""
        return self.name

    def get_role(self) -> str:
        """Return the role of current agent."""
        return self.role

    def get_goal(self) -> Optional[str]:
        """Return the goal of current agent."""
        return self.goal

    def get_constraints(self) -> Optional[List[str]]:
        """Return the constraints of current agent."""
        return self.constraints

    def get_description(self) -> Optional[str]:
        """Return the description of current agent.

        It will not be used to generate prompt.
        """
        return self.desc

    def get_expand_prompt(self) -> Optional[str]:
        """Return the expand prompt of current agent."""
        return self.expand_prompt

    def get_examples(self) -> Optional[str]:
        """Return the examples of current agent."""
        return self.examples

    def get_system_prompt_template(self) -> str:
        """Return the prompt template of current agent."""
        return self.system_prompt_template

    def get_user_prompt_template(self) -> str:
        """Return the user prompt template of current agent."""
        return self.user_prompt_template

    def get_write_memory_template(self) -> str:
        """Return the save memory template of current agent."""
        return self.write_memory_template


class ProfileFactory:
    """Profile factory interface.

    It is used to create a profile.
    """

    @abstractmethod
    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        """Create a profile."""


class LLMProfileFactory(ProfileFactory):
    """Create a profile by LLM.

    Based on LLM automatic generation, it usually specifies the rules of the generation
     configuration first, clarifies the composition and attributes of the agent
     configuration in the target population, and then gives a small number of samples,
    and finally LLM generates the configuration of all agents.
    """

    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        """Create a profile by LLM.

        TODO: Implement this method.
        """
        pass


class DatasetProfileFactory(ProfileFactory):
    """Create a profile by dataset.

    Use existing data sets to generate agent configurations.

    In some cases, the data set contains a large amount of information about real people
    , first organize the information about real people in the data set into a natural
    language prompt, which is then used to generate the agent configuration.
    """

    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        """Create a profile by dataset.

        TODO: Implement this method.
        """
        pass


class CompositeProfileFactory(ProfileFactory):
    """Create a profile by combining multiple profile factories."""

    def __init__(self, factories: List[ProfileFactory]):
        """Create a composite profile factory."""
        self.factories = factories

    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        """Create a profile by combining multiple profile factories.

        TODO: Implement this method.
        """
        pass


class ProfileConfig(BaseModel):
    """Profile configuration.

    If factory is not specified, name and role must be specified.
    If factory is specified and name and role are also specified, the factory will be
    preferred.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile_id: int = Field(0, description="The profile ID.")
    name: str | ConfigInfo | None = DynConfig(..., description="The name of the agent.")
    role: str | ConfigInfo | None = DynConfig(..., description="The role of the agent.")
    goal: str | ConfigInfo | None = DynConfig(None, description="The goal.")
    constraints: List[str] | ConfigInfo | None = DynConfig(None, is_list=True)
    desc: str | ConfigInfo | None = DynConfig(
        None, description="The description of the agent."
    )
    expand_prompt: str | ConfigInfo | None = DynConfig(
        None, description="The expand prompt."
    )
    examples: str | ConfigInfo | None = DynConfig(None, description="The examples.")

    system_prompt_template: str | ConfigInfo | None = DynConfig(
        _DEFAULT_SYSTEM_TEMPLATE, description="The prompt template."
    )
    user_prompt_template: str | ConfigInfo | None = DynConfig(
        _DEFAULT_USER_TEMPLATE, description="The user prompt template."
    )
    write_memory_template: str | ConfigInfo | None = DynConfig(
        _DEFAULT_WRITE_MEMORY_TEMPLATE, description="The save memory template."
    )
    factory: ProfileFactory | None = Field(None, description="The profile factory.")

    @model_validator(mode="before")
    @classmethod
    def check_before(cls, values):
        """Check before validation."""
        if isinstance(values, dict):
            return values
        if values["factory"] is None:
            if values["name"] is None:
                raise ValueError("name must be specified if factory is not specified")
            if values["role"] is None:
                raise ValueError("role must be specified if factory is not specified")
        return values

    @cachetools.cached(cachetools.TTLCache(maxsize=100, ttl=10))
    def create_profile(
        self,
        profile_id: Optional[int] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Profile:
        """Create a profile.

        If factory is specified, use the factory to create the profile.
        """
        factory_profile = None
        if profile_id is None:
            profile_id = self.profile_id
        name = self.name
        role = self.role
        goal = self.goal
        constraints = self.constraints
        desc = self.desc
        expand_prompt = self.expand_prompt
        system_prompt_template = self.system_prompt_template
        user_prompt_template = self.user_prompt_template
        write_memory_template = self.write_memory_template
        examples = self.examples
        call_args = {
            "prefer_prompt_language": prefer_prompt_language,
            "prefer_model": prefer_model,
        }
        if isinstance(name, ConfigInfo):
            name = name.query(**call_args)
        if isinstance(role, ConfigInfo):
            role = role.query(**call_args)
        if isinstance(goal, ConfigInfo):
            goal = goal.query(**call_args)
        if isinstance(constraints, ConfigInfo):
            constraints = constraints.query(**call_args)
        if isinstance(desc, ConfigInfo):
            desc = desc.query(**call_args)
        if isinstance(expand_prompt, ConfigInfo):
            expand_prompt = expand_prompt.query(**call_args)
        if isinstance(examples, ConfigInfo):
            examples = examples.query(**call_args)
        if isinstance(system_prompt_template, ConfigInfo):
            system_prompt_template = system_prompt_template.query(**call_args)
        if isinstance(user_prompt_template, ConfigInfo):
            user_prompt_template = user_prompt_template.query(**call_args)
        if isinstance(write_memory_template, ConfigInfo):
            write_memory_template = write_memory_template.query(**call_args)

        if self.factory is not None:
            factory_profile = self.factory.create_profile(
                profile_id,
                name,
                role,
                goal,
                prefer_prompt_language,
                prefer_model,
            )

        if factory_profile is not None:
            return factory_profile
        return DefaultProfile(
            name=name,
            role=role,
            goal=goal,
            constraints=constraints,
            desc=desc,
            expand_prompt=expand_prompt,
            examples=examples,
            system_prompt_template=system_prompt_template,
            user_prompt_template=user_prompt_template,
            write_memory_template=write_memory_template,
        )

    def __hash__(self):
        """Return the hash value."""
        return hash(self.profile_id)
