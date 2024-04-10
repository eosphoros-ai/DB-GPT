"""Resource API for the agent."""
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel


class ResourceType(Enum):
    """Resource type enumeration."""

    DB = "database"
    Knowledge = "knowledge"
    Internet = "internet"
    Plugin = "plugin"
    TextFile = "text_file"
    ExcelFile = "excel_file"
    ImageFile = "image_file"
    AWELFlow = "awel_flow"


class AgentResource(BaseModel):
    """Agent resource class."""

    type: ResourceType
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
            type=ResourceType(d.get("type")),
            name=d.get("name"),
            introduce=d.get("introduce"),
            value=d.get("value", None),
            is_dynamic=d.get("is_dynamic", False),
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
        temp = self.dict()
        for field, value in temp.items():
            if isinstance(value, Enum):
                temp[field] = value.value
        return temp


class ResourceClient(ABC):
    """Resource client interface."""

    @property
    @abstractmethod
    def type(self) -> ResourceType:
        """Return the resource type."""

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """
        Get the content introduction prompt of the specified resource.

        Args:
            resource(AgentResource): The specified resource.
            question(str): The question to be asked.

        Returns:
            str: The introduction content.
        """
        return ""

    def get_data_type(self, resource: AgentResource) -> str:
        """Return the data type of the specified resource.

        Args:
            resource(AgentResource): The specified resource.

        Returns:
            str: The data type.
        """
        return ""

    async def get_resource_prompt(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> str:
        """Get the resource prompt.

        Args:
            resource(AgentResource): The specified resource.
            question(str): The question to be asked.

        Returns:
            str: The resource prompt.
        """
        return resource.resource_prompt_template().format(
            data_type=self.get_data_type(resource),
            data_introduce=await self.get_data_introduce(resource, question),
        )
