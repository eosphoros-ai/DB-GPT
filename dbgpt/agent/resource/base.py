"""Resources for the agent."""

import dataclasses
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from dbgpt._private.pydantic import BaseModel, model_to_dict
from dbgpt.util.parameter_utils import BaseParameters, _get_parameter_descriptions

P = TypeVar("P", bound="ResourceParameters")
T = TypeVar("T", bound="Resource")


class ResourceType(str, Enum):
    """Resource type enumeration."""

    DB = "database"
    Knowledge = "knowledge"
    Internet = "internet"
    Tool = "tool"
    Plugin = "plugin"
    TextFile = "text_file"
    ExcelFile = "excel_file"
    ImageFile = "image_file"
    AWELFlow = "awel_flow"
    # Resource type for resource pack
    Pack = "pack"


@dataclasses.dataclass
class ResourceParameters(BaseParameters):
    """Resource parameters class.

    It defines the parameters for building a resource.
    """

    name: str = dataclasses.field(metadata={"help": "Resource name", "tags": "fixed"})

    @classmethod
    def _resource_version(cls) -> str:
        """Return the resource version."""
        return "v2"

    @classmethod
    def to_configurations(
        cls, parameters: Type["ResourceParameters"], version: Optional[str] = None
    ) -> Any:
        """Convert the parameters to configurations."""
        return _get_parameter_descriptions(parameters)


class Resource(ABC, Generic[P]):
    """Resource for the agent."""

    @classmethod
    @abstractmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""

    @classmethod
    def type_alias(cls) -> str:
        """Return the resource type alias."""
        return cls.type().value

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the resource name."""

    @classmethod
    def resource_parameters_class(cls) -> Type[P]:
        """Return the parameters class."""
        return ResourceParameters

    def prefer_resource_parameters_class(self) -> Type[P]:
        """Return the parameters class.

        You can override this method to return a different parameters class.
        It will be used to initialize the resource with parameters.
        """
        return self.resource_parameters_class()

    def initialize_with_parameters(self, resource_parameters: P):
        """Initialize the resource with parameters."""
        pass

    def preload_resource(self):
        """Preload the resource."""
        pass

    @classmethod
    def from_resource(
        cls: Type[T],
        resource: Optional["Resource"],
        expected_type: Optional[ResourceType] = None,
    ) -> List[T]:
        """Create a resource from another resource.

        Another resource can be a pack or a single resource, if it is a pack, it will
        return all resources which type is the same as the current resource.

        Args:
            resource(Resource): The resource.
            expected_type(ResourceType): The expected resource type.
        Returns:
            List[Resource]: The resources.
        """
        if not resource:
            return []
        typed_resources = []
        for r in resource.get_resource_by_type(expected_type or cls.type()):
            typed_resources.append(cast(T, r))
        return typed_resources

    @abstractmethod
    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Get the prompt.

        Args:
            lang(str): The language.
            prompt_type(str): The prompt type.
            question(str): The question.
            resource_name(str): The resource name, just for the pack, it will be used
                to select specific resource in the pack.
        """

    def execute(self, *args, resource_name: Optional[str] = None, **kwargs) -> Any:
        """Execute the resource."""
        raise NotImplementedError

    async def async_execute(
        self, *args, resource_name: Optional[str] = None, **kwargs
    ) -> Any:
        """Execute the resource asynchronously."""
        raise NotImplementedError

    @property
    def is_async(self) -> bool:
        """Return whether the resource is asynchronous."""
        return False

    @property
    def is_pack(self) -> bool:
        """Return whether the resource is a pack."""
        return False

    @property
    def sub_resources(self) -> List["Resource"]:
        """Return the resources."""
        if not self.is_pack:
            raise ValueError("The resource is not a pack, no sub-resources.")
        return []

    def get_resource_by_type(self, resource_type: ResourceType) -> List["Resource"]:
        """Get resources by type.

        If the resource is a pack, it will search the sub-resources. Otherwise, it will
        return itself if the type matches.

        Args:
            resource_type(ResourceType): The resource type.

        Returns:
            List[Resource]: The resources.
        """
        if not self.is_pack:
            if self.type() == resource_type:
                return [self]
            else:
                return []
        resources = []
        for resource in self.sub_resources:
            if resource.type() == resource_type:
                resources.append(resource)
        return resources


class AgentResource(BaseModel):
    """Agent resource class."""

    type: str
    name: str
    value: str
    is_dynamic: bool = (
        False  # Is the current resource predefined or dynamically passed in?
    )

    def resource_prompt_template(self, **kwargs) -> str:
        """Get the resource prompt template."""
        return "{data_type}  --{data_introduce}"

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Optional["AgentResource"]:
        """Create an AgentResource object from a dictionary."""
        if d is None:
            return None
        return AgentResource(
            type=d.get("type"),
            name=d.get("name"),
            introduce=d.get("introduce"),
            value=d.get("value", None),
            is_dynamic=d.get("is_dynamic", False),
            parameters=d.get("parameters", None),
        )

    @staticmethod
    def from_json_list_str(d: Optional[str]) -> Optional[List["AgentResource"]]:
        """Create a list of AgentResource objects from a json string."""
        if d is None:
            return None
        try:
            json_array = json.loads(d)
        except Exception:
            raise ValueError(f"Illegal AgentResource json string！{d}")
        if not isinstance(json_array, list):
            raise ValueError(f"Illegal AgentResource json string！{d}")
        json_list = []
        for item in json_array:
            r = AgentResource.from_dict(item)
            if r:
                json_list.append(r)
        return json_list

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentResource object to a dictionary."""
        temp = model_to_dict(self)
        for field, value in temp.items():
            if isinstance(value, Enum):
                temp[field] = value.value
        return temp
