"""Knowledge resource API for the agent."""
from typing import Any, Optional

from .resource_api import ResourceClient, ResourceType


class ResourceKnowledgeClient(ResourceClient):
    """Knowledge resource client."""

    @property
    def type(self):
        """Return the resource type."""
        return ResourceType.Knowledge

    async def get_kn(self, space_name: str, question: Optional[str] = None) -> Any:
        """Get the knowledge content."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def add_kn(
        self, space_name: str, kn_name: str, type: str, content: Optional[Any]
    ):
        """Add knowledge content."""
        raise NotImplementedError("The run method should be implemented in a subclass.")
