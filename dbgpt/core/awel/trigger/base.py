"""Base class for all trigger classes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic

from ..operators.common_operator import TriggerOperator
from ..task.base import OUT


class Trigger(TriggerOperator[OUT], ABC, Generic[OUT]):
    """Base class for all trigger classes.

    Now only support http trigger.
    """

    @abstractmethod
    async def trigger(self, **kwargs) -> Any:
        """Trigger the workflow or a specific operation in the workflow."""
