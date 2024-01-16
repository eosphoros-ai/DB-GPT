"""Base classes for AWEL."""
from abc import ABC, abstractmethod


class Trigger(ABC):
    """Base class for trigger."""

    @abstractmethod
    async def trigger(self) -> None:
        """Trigger the workflow or a specific operation in the workflow."""
