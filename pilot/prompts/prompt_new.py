import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union
from pydantic import BaseModel, Extra, Field, root_validator


from pilot.common.formatting import formatter
from pilot.out_parser.base import BaseOutputParser
from pilot.common.schema import SeparatorStyle


def jinja2_formatter(template: str, **kwargs: Any) -> str:
    """Format a template using jinja2."""
    try:
        from jinja2 import Template
    except ImportError:
        raise ImportError(
            "jinja2 not installed, which is needed to use the jinja2_formatter. "
            "Please install it with `pip install jinja2`."
        )

    return Template(template).render(**kwargs)


DEFAULT_FORMATTER_MAPPING: Dict[str, Callable] = {
    "f-string": formatter.format,
    "jinja2": jinja2_formatter,
}


class PromptTemplate(BaseModel, ABC):
    input_variables: List[str]
    """A list of the names of the variables the prompt template expects."""
    template_scene: str

    template_define: str
    """this template define"""
    template: str
    """The prompt template."""
    template_format: str = "f-string"
    """The format of the prompt template. Options are: 'f-string', 'jinja2'."""
    response_format: str
    """default use stream out"""
    stream_out: bool = True
    """"""
    output_parser: BaseOutputParser = None
    """"""
    sep: str = SeparatorStyle.SINGLE.value

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    @property
    def _prompt_type(self) -> str:
        """Return the prompt type key."""
        return "prompt"

    def _generate_command_string(self, command: Dict[str, Any]) -> str:
        """
        Generate a formatted string representation of a command.

        Args:
            command (dict): A dictionary containing command information.

        Returns:
            str: The formatted command string.
        """
        args_string = ", ".join(
            f'"{key}": "{value}"' for key, value in command["args"].items()
        )
        return f'{command["label"]}: "{command["name"]}", args: {args_string}'

    def _generate_numbered_list(self, items: List[Any], item_type="list") -> str:
        """
        Generate a numbered list from given items based on the item_type.

        Args:
            items (list): A list of items to be numbered.
            item_type (str, optional): The type of items in the list.
                Defaults to 'list'.

        Returns:
            str: The formatted numbered list.
        """
        if item_type == "command":
            command_strings = []
            if self.command_registry:
                command_strings += [
                    str(item)
                    for item in self.command_registry.commands.values()
                    if item.enabled
                ]
            # terminate command is added manually
            command_strings += [self._generate_command_string(item) for item in items]
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(command_strings))
        else:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    def format(self, **kwargs: Any) -> str:
        """Format the prompt with the inputs."""

        kwargs["response"] = json.dumps(self.response_format, indent=4)
        return DEFAULT_FORMATTER_MAPPING[self.template_format](self.template, **kwargs)

    def add_goals(self, goal: str) -> None:
        self.goals.append(goal)

    def add_constraint(self, constraint: str) -> None:
        """
        Add a constraint to the constraints list.

        Args:
            constraint (str): The constraint to be added.
        """
        self.constraints.append(constraint)
