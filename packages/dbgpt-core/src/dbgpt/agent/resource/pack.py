"""Resource pack module.

Resource pack is a collection of resources(also, it is a resource) that can be executed
together.
"""

import copy
import dataclasses
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from .base import Resource, ResourceParameters, ResourceType


@dataclasses.dataclass
class PackResourceParameters(ResourceParameters):
    """Resource pack parameters class."""

    pass


class ResourcePack(Resource[PackResourceParameters]):
    """Resource pack class."""

    def __init__(
        self,
        resources: List[Resource],
        name: str = "Resource Pack",
        prompt_separator: str = "\n",
        **kwargs,
    ):
        """Initialize the resource pack."""
        self._resources: Dict[str, Resource] = {
            resource.name: resource for resource in resources
        }
        self._name = name
        self._prompt_separator = prompt_separator

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Pack

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._name

    def _get_resource_by_name(self, name: str) -> Optional[Resource]:
        """Get the resource by name."""
        return self._resources.get(name, None)

    async def preload_resource(self):
        """Preload the resource."""
        for sub_resource in self.sub_resources:
            await sub_resource.preload_resource()

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, Optional[Dict]]:
        """Get the prompt."""
        prompt_list = []
        info_map = {}
        for name, resource in self._resources.items():
            prompt, resource_reference = await resource.get_prompt(
                lang=lang,
                prompt_type=prompt_type,
                question=question,
                resource_name=resource_name,
                **kwargs,
            )
            prompt_list.append(prompt)
            if resource_reference is not None:
                info_map.update(resource_reference)
        return self._prompt_separator.join(prompt_list), info_map

    def append(self, resource: Resource, overwrite: bool = False):
        """Append a resource to the pack."""
        name = resource.name
        if name in self._resources and not overwrite:
            raise ValueError(f"Resource {name} already exists in the pack.")
        self._resources[name] = resource

    def execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the resource."""
        if not resource_name:
            raise ValueError("No resource name provided, will not execute.")
        resource = self._resources.get(resource_name)
        if resource:
            return resource.execute(*args, **kwargs)
        raise ValueError("No resource parameters provided, will not execute.")

    async def async_execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the resource asynchronously."""
        if not resource_name:
            raise ValueError("No resource name provided, will not execute.")
        resource = self._resources.get(resource_name)
        if resource:
            return await resource.async_execute(*args, **kwargs)
        raise ValueError("No resource parameters provided, will not execute.")

    @property
    def is_pack(self) -> bool:
        """Return whether the resource is a pack."""
        return True

    @property
    def sub_resources(self) -> List[Resource]:
        """Return the resources."""
        return list(self._resources.values())

    def apply(
        self,
        apply_func: Optional[
            Callable[[Resource], Union[Resource, List[Resource], None]]
        ] = None,
        apply_pack_func: Optional[
            Callable[["Resource"], Union["Resource", None]]
        ] = None,
    ) -> Union[Resource, None]:
        """Apply the function to the resource."""
        if not self.is_pack:
            return self

        if not apply_func and not apply_pack_func:
            raise ValueError("No function provided to apply to the resource pack.")

        def _apply_func_to_resource(
            resource: Resource,
        ) -> Union[Resource, List[Resource], None]:
            if resource.is_pack:
                if apply_pack_func is not None:
                    return apply_pack_func(resource)
                resources = []
                resource_copy = cast(ResourcePack, copy.copy(resource))
                for resource_copy in resource_copy.sub_resources:
                    result = _apply_func_to_resource(resource_copy)
                    if result:
                        if isinstance(result, list):
                            resources.extend(result)
                        else:
                            resources.append(result)
                # Replace the resources
                resource_copy._resources = {
                    resource.name: resource for resource in resources
                }
            else:
                if apply_func is not None:
                    return apply_func(resource)
                else:
                    return resource

        new_resource = _apply_func_to_resource(self)
        resource_copy = cast(ResourcePack, copy.copy(self))
        if isinstance(new_resource, list):
            resource_copy._resources = {
                resource.name: resource for resource in new_resource
            }
        return new_resource
