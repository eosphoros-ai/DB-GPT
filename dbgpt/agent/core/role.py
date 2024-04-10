"""Role class for role-based conversation."""
from abc import ABC
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel


class Role(ABC, BaseModel):
    """Role class for role-based conversation."""

    profile: str = ""
    name: str = ""
    resource_introduction = ""
    goal: str = ""

    expand_prompt: str = ""

    fixed_subgoal: Optional[str] = None

    constraints: List[str] = []
    examples: str = ""
    desc: str = ""
    language: str = "en"
    is_human: bool = False
    is_team: bool = False

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def prompt_template(
        self,
        specified_prompt: Optional[str] = None,
    ) -> str:
        """Return the prompt template for the role.

        Args:
            specified_prompt (str, optional): The specified prompt. Defaults to None.

        Returns:
            str: The prompt template.
        """
        if specified_prompt:
            return specified_prompt

        expand_prompt = self.expand_prompt if len(self.expand_prompt) > 0 else ""
        examples_prompt = (
            "You can refer to the following examples:\n"
            if len(self.examples) > 0
            else ""
        )
        examples = self.examples if len(self.examples) > 0 else ""
        template = (
            f"{self.role_prompt}\n"
            "Please think step by step to achieve the goal. You can use the resources "
            "given below. At the same time, please strictly abide by the constraints "
            "and specifications in IMPORTANT REMINDER.\n\n"
            f"{{resource_prompt}}\n\n"
            f"{expand_prompt}\n\n"
            "*** IMPORTANT REMINDER ***\n"
            f"{self.language_require_prompt}\n"
            f"{self.constraints_prompt}\n"
            f"{examples_prompt}{examples}\n\n"
            f"{{out_schema}}"
        )
        return template

    @property
    def role_prompt(self) -> str:
        """Return the role prompt.

        You are a {self.profile}, named {self.name}, your goal is {self.goal}.

        Returns:
            str: The role prompt.
        """
        profile_prompt = f"You are a {self.profile},"
        name_prompt = f"named {self.name}," if len(self.name) > 0 else ""
        goal_prompt = f"your goal is {self.goal}"
        prompt = f"""{profile_prompt}{name_prompt}{goal_prompt}"""
        return prompt

    @property
    def constraints_prompt(self) -> str:
        """Return the constraints prompt.

        Return:
            str: The constraints prompt.
        """
        if len(self.constraints) > 0:
            return "\n".join(
                f"{i + 1}. {item}" for i, item in enumerate(self.constraints)
            )
        return ""

    @property
    def language_require_prompt(self) -> str:
        """Return the language requirement prompt.

        Returns:
            str: The language requirement prompt.
        """
        if self.language == "zh":
            return "Please answer in simplified Chinese."
        else:
            return "Please answer in English."

    @property
    def introduce(self) -> str:
        """Introduce the role."""
        return self.desc

    def identity_check(self) -> None:
        """Check the identity of the role."""
        pass

    def get_name(self) -> str:
        """Get the name of the role."""
        return self.name

    def get_profile(self) -> str:
        """Get the profile of the role."""
        return self.profile

    def get_describe(self) -> str:
        """Get the describe of the role."""
        return self.desc
