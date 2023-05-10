#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import functools
import importlib
import inspect
from typing import Any, Callable, Optional

class Command:
    """A class representing a command.

    Attributes:
        name (str): The name of the command.
        description (str): A brief description of what the command does.
        signature (str): The signature of the function that the command executes. Default to None.
    """

    def __init__(self,
                 name: str,
                 description: str,
                 method: Callable[..., Any],
                 signature: str = "",
                 enabled: bool = True,
                 disabled_reason: Optional[str] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.method = method
        self.signature = signature if signature else str(inspect.signature(self.method))
        self.enabled = enabled
        self.disabled_reason = disabled_reason

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        if not self.enabled:
            return f"Command '{self.name}' is disabled: {self.disabled_reason}"
        return self.method(*args, **kwds)