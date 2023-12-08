from abc import ABC, abstractmethod


class Trigger(ABC):
    @abstractmethod
    async def trigger(self) -> None:
        """Trigger the workflow or a specific operation in the workflow."""
