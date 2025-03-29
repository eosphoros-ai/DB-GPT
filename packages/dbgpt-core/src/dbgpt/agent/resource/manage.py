"""Resource manager."""

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Type, Union, cast

from dbgpt._private.pydantic import BaseModel, ConfigDict, model_validator
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.parameter_utils import ParameterDescription

from .base import AgentResource, Resource, ResourceParameters, ResourceType
from .pack import ResourcePack
from .tool.pack import ToolResourceType, _is_function_tool, _to_tool_list

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

    def get_parameter_class(
        self,
        **kwargs,
    ) -> Type[ResourceParameters]:
        """Return the parameter description."""
        if self.is_class:
            return self.resource_cls.resource_parameters_class(**kwargs)
        return self.resource_instance.prefer_resource_parameters_class(**kwargs)  # type: ignore # noqa


class ResourceManager(BaseComponent):
    """Resource manager.

    To manage the resources.
    """

    name = ComponentType.RESOURCE_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new AgentManager."""
        super().__init__(system_app)
        self.system_app = system_app
        self._resources: Dict[str, RegisterResource] = {}
        self._type_to_resources: Dict[str, List[RegisterResource]] = defaultdict(list)

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
        resource_instance: Optional[Union[Resource, ToolResourceType]] = None,
        resource_type: Optional[ResourceType] = None,
        resource_type_alias: Optional[str] = None,
        ignore_duplicate: bool = False,
    ):
        """Register a resource."""
        if resource_instance and _is_function_tool(resource_instance):
            resource_instance = _to_tool_list(resource_instance)[0]  # type: ignore

        if resource_cls is None and resource_instance is None:
            raise ValueError("Resource class or instance must be provided.")
        name: Optional[str] = None
        if resource_instance is not None:
            resource_cls = resource_cls or type(resource_instance)  # type: ignore
            name = resource_instance.name  # type: ignore
        resource = RegisterResource(
            name=name,
            resource_cls=resource_cls,
            resource_instance=resource_instance,
            resource_type=resource_type,
            resource_type_alias=resource_type_alias,
        )
        if resource.key in self._resources:
            if ignore_duplicate:
                return
            else:
                raise ValueError(f"Resource {resource.key} already exists.")
        self._resources[resource.key] = resource
        self._type_to_resources[resource.type_unique_key].append(resource)

    def get_supported_resources_type(self) -> List[str]:
        """Get supported resources types."""
        unique_types = []
        for key, resource in self._resources.items():
            if resource.type_unique_key not in unique_types:
                unique_types.append(resource.type_unique_key)
        return unique_types

    def get_supported_resources(
        self, version: Optional[str] = None, type: Optional[str] = None, **kwargs
    ) -> Dict[str, Union[List[ParameterDescription], List[str]]]:
        """Return the resources."""
        results: Dict[str, Union[List[ParameterDescription], List[str]]] = defaultdict(
            list
        )
        for key, resource in self._resources.items():
            if type and type != resource.type_unique_key:
                continue
            parameter_class = resource.get_parameter_class(**kwargs)
            resource_type = resource.type_unique_key
            configs: Any = parameter_class.to_configurations(
                parameter_class,
                version=version,
            )
            all_instance_options = []
            if (
                isinstance(configs, list)
                and len(configs) > 0
                and isinstance(configs[0], ParameterDescription)
            ):
                # v1, not compatible with class
                # set_configs_name = set(results[resource_type])
                set_configs: list = []
                if not resource.is_class:
                    for r in self._type_to_resources[resource_type]:
                        if not r.is_class:
                            set_configs.append(
                                {
                                    "label": r.resource_instance.name,  # type: ignore
                                    "key": r.resource_instance.name,  # type: ignore
                                    "description": r.resource_instance.description,  # type: ignore # noqa
                                }
                            )  # type: ignore
                all_instance_options = set_configs

            if all_instance_options and version == "v1":
                # v1 resource instance options
                results[resource_type] = all_instance_options
            elif (
                all_instance_options
                and version != "v1"
                and isinstance(configs, list)
                and isinstance(configs[0], ParameterDescription)
            ):
                idx = -1
                for i, config in enumerate(configs):
                    if config.param_name == "name":
                        idx = i
                        break
                if idx >= 0:
                    configs[idx].valid_values = all_instance_options
                # New version, Update the valid values
                results[resource_type] = configs
            else:
                results[resource_type] = configs

        return results

    def build_resource_by_type(
        self,
        type_unique_key: str,
        agent_resource: AgentResource,
        return_resource: bool = True,
    ) -> Union[Resource, Dict[str, Any]]:
        """Return the resource by type."""
        item = self._type_to_resources.get(type_unique_key)
        if not item:
            raise ValueError(f"Resource type {type_unique_key} not found.")
        inst_items = [i for i in item if not i.is_class]
        resource_value: Union[str, Dict[str, Any]] = agent_resource.value
        v2_resource = False
        if resource_value and isinstance(resource_value, str):
            try:
                resource_value = json.loads(resource_value)
                # V2 value is JSON string
                v2_resource = True
            except json.JSONDecodeError:
                pass

        if inst_items:
            real_resource_name = (
                resource_value.get("name")
                if isinstance(resource_value, dict)
                else resource_value
            )
            for i in inst_items:
                if (
                    i.resource_instance
                    and i.resource_instance.name == real_resource_name
                ):
                    return (
                        i.resource_instance
                        if return_resource
                        else {"name": real_resource_name}
                    )
            raise ValueError(
                f"Resource {real_resource_name} not found in {type_unique_key}"
            )
            # return cast(Resource, inst_items[0].resource_instance)
        elif len(inst_items) > 1:
            raise ValueError(
                f"Multiple instances of resource {type_unique_key} found, "
                f"please specify the resource name."
            )
        else:
            single_item = item[0]
            try:
                parameter_cls = single_item.get_parameter_class()
                param = parameter_cls.from_dict(
                    resource_value if v2_resource else agent_resource.to_dict()
                )
                param_dict = param.to_dict()
                if not return_resource:
                    return param_dict
                param_dict["system_app"] = self.system_app
                resource_inst = single_item.resource_cls(**param_dict)
                return resource_inst
            except Exception as e:
                logger.warning(f"Failed to build resource {single_item.key}: {str(e)}")
                raise ValueError(
                    f"Failed to build resource {single_item.key}: {str(e)}"
                )

    def build_resource(
        self,
        agent_resources: Optional[List[AgentResource]] = None,
    ) -> Optional[Resource]:
        """Build a resource.

        If there is only one resource, return the resource instance, otherwise return a
        ResourcePack.

        Args:
            agent_resources: The agent resources.
            version: The resource version.

        Returns:
            Optional[Resource]: The resource instance.
        """
        if not agent_resources:
            return None
        dependencies: List[Resource] = []
        for resource in agent_resources:
            resource_inst = cast(
                Resource, self.build_resource_by_type(resource.type, resource)
            )
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
