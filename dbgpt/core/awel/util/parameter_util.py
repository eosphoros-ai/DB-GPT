"""The parameter utility."""

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

from dbgpt._private.pydantic import BaseModel, Field, root_validator
from dbgpt.core.interface.serialization import Serializable

_DEFAULT_DYNAMIC_REGISTRY = {}


class OptionValue(Serializable, BaseModel):
    """The option value of the parameter."""

    label: str = Field(..., description="The label of the option")
    name: str = Field(..., description="The name of the option")
    value: Any = Field(..., description="The value of the option")

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return self.dict()


class BaseDynamicOptions(Serializable, BaseModel, ABC):
    """The base dynamic options."""

    @abstractmethod
    def option_values(self) -> List[OptionValue]:
        """Return the option values of the parameter."""


class FunctionDynamicOptions(BaseDynamicOptions):
    """The function dynamic options."""

    func: Callable[[], List[OptionValue]] = Field(
        ..., description="The function to generate the dynamic options"
    )
    func_id: str = Field(
        ..., description="The unique id of the function to generate the dynamic options"
    )

    def option_values(self) -> List[OptionValue]:
        """Return the option values of the parameter."""
        return self.func()

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the function id."""
        func = values.get("func")
        if func is None:
            raise ValueError(
                "The function to generate the dynamic options is required."
            )
        func_id = _generate_unique_id(func)
        values["func_id"] = func_id
        _DEFAULT_DYNAMIC_REGISTRY[func_id] = func
        return values

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return {"func_id": self.func_id}


def _generate_unique_id(func: Callable) -> str:
    if func.__name__ == "<lambda>":
        func_id = f"lambda_{inspect.getfile(func)}_{inspect.getsourcelines(func)}"
    else:
        func_id = f"{func.__module__}.{func.__name__}"
    return func_id
