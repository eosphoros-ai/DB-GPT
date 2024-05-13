"""Resource manager."""

import logging
from typing import Dict, List, Optional, Type, cast

from dbgpt._private.pydantic import BaseModel, ConfigDict, model_validator
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.parameter_utils import ParameterDescription

from .base import AgentResource, Resource, ResourceParameters, ResourceType
from .pack import ResourcePack

logger = logging.getLogger(__name__)


class RegisterResource(BaseModel):
    """Register resource model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: Optional[str] = None
    resource_type: ResourceType
    resource_type_alias: Optional[str] = None
    resource_cls: Type[Resource]
    resource_instance: Optional[Resource] = None
    is_class: bool = True

    @property
    def key(self) -> str:
        """Return the key."""
        full_cls = f"{self.resource_cls.__module__}.{self.resource_cls.__qualname__}"
        name = self.name or full_cls
        resource_type_alias = self.resource_type_alias or self.resource_type.value
        return f"{resource_type_alias}:{name}"

    @property
    def type_unique_key(self) -> str:
        """Return the key."""
        resource_type_alias = self.resource_type_alias or self.resource_type.value
        return resource_type_alias

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values):
        """Pre-fill the model."""
        if not isinstance(values, dict):
            return values
        resource_instance = values.get("resource_instance")
        if resource_instance is not None:
            values["name"] = values["name"] or resource_instance.name
            values["is_class"] = False
            if not isinstance(resource_instance, Resource):
                raise ValueError(
                    f"resource_instance must be a Resource instance, not "
                    f"{type(resource_instance)}"
                )
        if not values.get("resource_type"):
            values["resource_type"] = values["resource_cls"].type()
        if not values.get("resource_type_alias"):
            values["resource_type_alias"] = values["resource_cls"].type_alias()
        return values

    def get_parameter_class(self) -> Type[ResourceParameters]:
        """Return the parameter description."""
        if self.is_class:
            return self.resource_cls.resource_parameters_class()
        return self.resource_instance.prefer_resource_parameters_class()  # type: ignore


class ResourceManager(BaseComponent):
    """Resource manager.

    To manage the resources.
    """

    name = ComponentType.RESOURCE_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new AgentManager."""
        super().__init__(system_app)
        self.system_app = system_app
        self._resources: dict[str, RegisterResource] = {}
        self._type_to_resources: dict[str, RegisterResource] = {}

    def init_app(self, system_app: SystemApp):
        """Initialize the AgentManager."""
        self.system_app = system_app

    def after_start(self):
        """Register all resources."""
        # TODO: Register some internal resources
        pass

    def register_resource(
        self,
        resource_cls: Optional[Type[Resource]] = None,
        resource_instance: Optional[Resource] = None,
        resource_type: Optional[ResourceType] = None,
        resource_type_alias: Optional[str] = None,
    ):
        """Register a resource."""
        if resource_cls is None and resource_instance is None:
            raise ValueError("Resource class or instance must be provided.")
        name: Optional[str] = None
        if resource_instance is not None:
            resource_cls = resource_cls or type(resource_instance)
            name = resource_instance.name
        resource = RegisterResource(
            name=name,
            resource_cls=resource_cls,
            resource_instance=resource_instance,
            resource_type=resource_type,
            resource_type_alias=resource_type_alias,
        )
        self._resources[resource.key] = resource
        self._type_to_resources[resource.type_unique_key] = resource

    def get_supported_resources(
        self, version: Optional[str] = None
    ) -> Dict[str, List[ParameterDescription]]:
        """Return the resources."""
        results = {}
        for key, resource in self._resources.items():
            parameter_class = resource.get_parameter_class()
            resource_type = resource.type_unique_key
            results[resource_type] = parameter_class.to_configurations(
                parameter_class, version=version
            )
        return results

    def build_resource_by_type(
        self, type_unique_key: str, agent_resource: AgentResource
    ) -> Resource:
        """Return the resource by type."""
        item = self._type_to_resources.get(type_unique_key)
        if not item:
            raise ValueError(f"Resource type {type_unique_key} not found.")
        if not item.is_class:
            return cast(Resource, item.resource_instance)
        else:
            try:
                parameter_cls = item.get_parameter_class()
                param = parameter_cls.from_dict(agent_resource.to_dict())
                resource_inst = item.resource_cls(**param.to_dict())
                return resource_inst
            except Exception as e:
                logger.warning(f"Failed to build resource {item.key}: {str(e)}")
                raise ValueError(f"Failed to build resource {item.key}: {str(e)}")

    def build_resource(
        self, agent_resources: Optional[List[AgentResource]] = None
    ) -> Optional[Resource]:
        """Build a resource.

        If there is only one resource, return the resource instance, otherwise return a
        ResourcePack.

        Args:
            agent_resources: The agent resources.

        Returns:
            Optional[Resource]: The resource instance.
        """
        if not agent_resources:
            return None
        dependencies: List[Resource] = []
        for resource in agent_resources:
            resource_inst = self.build_resource_by_type(resource.type, resource)
            dependencies.append(resource_inst)
        if len(dependencies) == 1:
            return dependencies[0]
        else:
            return ResourcePack(dependencies)


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_resource(system_app: SystemApp):
    """Initialize the resource manager."""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    resource_manager = ResourceManager(system_app)
    system_app.register_instance(resource_manager)


def get_resource_manager(system_app: Optional[SystemApp] = None) -> ResourceManager:
    """Return the resource manager."""
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_resource(system_app)
    app = system_app or _SYSTEM_APP
    return ResourceManager.get_instance(cast(SystemApp, app))
