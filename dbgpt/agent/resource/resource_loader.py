from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

from .resource_api import ResourceClient, ResourceType


class ResourceLoader:
    def __init__(self):
        self._resource_api_instance = defaultdict(ResourceClient)

    def get_resesource_api(
        self, resource_type: ResourceType
    ) -> Optional[ResourceClient]:
        if not resource_type:
            return None

        if resource_type not in self._resource_api_instance:
            raise ValueError(
                f"No loader available for resource of type {resource_type.value}"
            )

        return self._resource_api_instance[resource_type]

    def register_resesource_api(self, api_instance: ResourceClient):
        self._resource_api_instance[api_instance.type] = api_instance
