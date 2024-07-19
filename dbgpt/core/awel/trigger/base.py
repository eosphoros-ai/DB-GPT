"""Base class for all trigger classes."""

from abc import ABC, abstractmethod
from typing import Any, Generic, Optional

from dbgpt._private.pydantic import BaseModel, Field

from ..operators.common_operator import TriggerOperator
from ..task.base import OUT


class TriggerMetadata(BaseModel):
    """Metadata for the trigger."""

    trigger_type: Optional[str] = Field(
        default=None, description="The type of the trigger"
    )


class Trigger(TriggerOperator[OUT], ABC, Generic[OUT]):
    """Base class for all trigger classes.

    Now only support http trigger.
    """

    @abstractmethod
    async def trigger(self, **kwargs) -> Any:
        """Trigger the workflow or a specific operation in the workflow."""
