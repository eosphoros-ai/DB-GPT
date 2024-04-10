"""Resource loader module."""
from collections import defaultdict
from typing import Optional, Type, TypeVar

from .resource_api import ResourceClient, ResourceType

T = TypeVar("T", bound=ResourceClient)


class ResourceLoader:
    """Resource loader."""

    def __init__(self):
        """Create a new resource loader."""
        self._resource_api_instance = defaultdict(ResourceClient)

    def get_resource_api(
        self,
        resource_type: Optional[ResourceType],
        cls: Optional[Type[T]] = None,
        check_instance: bool = True,
    ) -> Optional[T]:
        """Get the resource loader for the given resource type."""
        if not resource_type:
            return None

        if resource_type not in self._resource_api_instance:
            raise ValueError(
                f"No loader available for resource of type {resource_type.value}"
            )
        inst = self._resource_api_instance[resource_type]
        if check_instance and cls and not isinstance(inst, cls):
            raise ValueError(
                f"Resource loader for {resource_type.value} is not an instance of {cls}"
            )
        return inst

    def register_resource_api(self, api_instance: ResourceClient):
        """Register the resource API instance."""
        self._resource_api_instance[api_instance.type] = api_instance
