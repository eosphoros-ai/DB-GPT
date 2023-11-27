from __future__ import annotations

from abc import ABC, abstractmethod

from ..operator.common_operator import TriggerOperator


class Trigger(TriggerOperator, ABC):
    @abstractmethod
    async def trigger(self) -> None:
        """Trigger the workflow or a specific operation in the workflow."""
