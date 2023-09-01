import json
from abc import ABC
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel


from pilot.common.formatting import formatter, no_strict_formatter
from pilot.out_parser.base import BaseOutputParser
from pilot.common.schema import SeparatorStyle
from pilot.prompts.example_base import ExampleSelector


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
    "f-string": lambda is_strict: formatter.format
    if is_strict
    else no_strict_formatter.format,
    "jinja2": lambda is_strict: jinja2_formatter,
}


class PromptTemplate(BaseModel, ABC):
    input_variables: List[str]
    """A list of the names of the variables the prompt template expects."""
    template_scene: Optional[str]
    template_define: Optional[str]
    """this template define"""
    template: Optional[str]
    """The prompt template."""
    template_format: str = "f-string"
    """strict template will check template args"""
    template_is_strict: bool = True
    """The format of the prompt template. Options are: 'f-string', 'jinja2'."""
    response_format: Optional[str]
    """default use stream out"""
    stream_out: bool = True
    """"""
    output_parser: BaseOutputParser = None
    """"""
    sep: str = SeparatorStyle.SINGLE.value

    example_selector: ExampleSelector = None

    need_historical_messages: bool = False

    temperature: float = 0.6
    max_new_tokens: int = 1024

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    @property
    def _prompt_type(self) -> str:
        """Return the prompt type key."""
        return "prompt"

    def format(self, **kwargs: Any) -> str:
        """Format the prompt with the inputs."""
        if self.template:
            if self.response_format:
                kwargs["response"] = json.dumps(
                    self.response_format, ensure_ascii=False, indent=4
                )
            return DEFAULT_FORMATTER_MAPPING[self.template_format](
                self.template_is_strict
            )(self.template, **kwargs)

    def add_goals(self, goal: str) -> None:
        self.goals.append(goal)

    def add_constraint(self, constraint: str) -> None:
        """
        Add a constraint to the constraints list.

        Args:
            constraint (str): The constraint to be added.
        """
        self.constraints.append(constraint)
