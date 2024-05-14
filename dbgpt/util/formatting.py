"""Utilities for formatting strings."""
import json
from string import Formatter
from typing import Any, List, Mapping, Sequence, Set, Union


class StrictFormatter(Formatter):
    """A subclass of formatter that checks for extra keys."""

    def check_unused_args(
        self,
        used_args: Set[Union[int, str]],
        args: Sequence,
        kwargs: Mapping[str, Any],
    ) -> None:
        """Check to see if extra parameters are passed."""
        extra = set(kwargs).difference(used_args)
        if extra:
            raise KeyError(extra)

    def vformat(
        self, format_string: str, args: Sequence, kwargs: Mapping[str, Any]
    ) -> str:
        """Check that no arguments are provided."""
        if len(args) > 0:
            raise ValueError(
                "No arguments should be provided, "
                "everything should be passed as keyword arguments."
            )
        return super().vformat(format_string, args, kwargs)

    def validate_input_variables(
        self, format_string: str, input_variables: List[str]
    ) -> None:
        dummy_inputs = {input_variable: "foo" for input_variable in input_variables}
        super().format(format_string, **dummy_inputs)


class NoStrictFormatter(StrictFormatter):
    def check_unused_args(
        self,
        used_args: Set[Union[int, str]],
        args: Sequence,
        kwargs: Mapping[str, Any],
    ) -> None:
        """Not check unused args"""
        pass


formatter = StrictFormatter()
no_strict_formatter = NoStrictFormatter()


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return json.JSONEncoder.default(self, obj)
