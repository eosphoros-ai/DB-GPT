from abc import ABC
from typing import Any, List, Optional

from pydantic import BaseModel


class Role(ABC, BaseModel):
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
        arbitrary_types_allowed = True

    def prompt_template(
        self,
        specified_prompt: Optional[str] = None,
    ):
        if specified_prompt:
            return specified_prompt

        template = f"""
        {self.role_prompt}
        Please think step by step to achieve the goal. You can use the resources given below. At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

        {{resource_prompt}}

        {self.expand_prompt if len(self.expand_prompt) > 0 else ""}

        *** IMPORTANT REMINDER ***
        {self.language_require_prompt}
        {self.constraints_prompt}

        {'You can refer to the following examples:' if len(self.examples) > 0 else ""}
        {self.examples if len(self.examples) > 0 else ""}

        {{out_schema}}
        """
        return template

    @property
    def role_prompt(self):
        """You are a {self.profile}, named {self.name}, your goal is {self.goal}."""
        profile_prompt = f"You are a {self.profile},"
        name_prompt = f"named {self.name}," if len(self.name) > 0 else ""
        goal_prompt = f"your goal is {self.goal}"
        prompt = f"""{profile_prompt}{name_prompt}{goal_prompt}"""
        return prompt

    @property
    def constraints_prompt(self):
        if len(self.constraints) > 0:
            return "\n".join(
                f"{i + 1}. {item}" for i, item in enumerate(self.constraints)
            )

    @property
    def language_require_prompt(self):
        if self.language == "zh":
            return "Please answer in simplified Chinese."
        else:
            return "Please answer in English."

    @property
    def introduce(self):
        return self.desc

    def identity_check(self):
        pass
