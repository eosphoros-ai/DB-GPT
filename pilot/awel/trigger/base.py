from __future__ import annotations

from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

from ..operator.base import BaseOperator
from ..operator.common_operator import TriggerOperator
from ..dag.base import DAGContext
from ..task.base import TaskOutput


class Trigger(TriggerOperator, ABC):
    @abstractmethod
    async def trigger(self, end_operator: "BaseOperator") -> None:
        """Trigger the workflow or a specific operation in the workflow."""
