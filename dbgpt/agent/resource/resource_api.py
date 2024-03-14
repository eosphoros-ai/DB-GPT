from __future__ import annotations

import dataclasses
import json
from abc import ABC
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel


class ResourceType(Enum):
    DB = "database"
    Knowledge = "knowledge"
    Internet = "internet"
    Plugin = "plugin"
    TextFile = "text_file"
    ExcelFile = "excel_file"
    ImageFile = "image_file"
    AwelFlow = "awel_flow"


class AgentResource(BaseModel):
    type: ResourceType
    name: str
    value: str
    is_dynamic: bool = (
        False  # Is the current resource predefined or dynamically passed in?
    )

    def resource_prompt_template(self, **kwargs) -> str:
        return f"""{{data_type}}  --{{data_introduce}}"""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Optional[AgentResource]:
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
    def from_josn_list_str(d: Optional[str]) -> Optional[List[AgentResource]]:
        if d is None:
            return None
        try:
            json_array = json.loads(d)
        except Exception as e:
            raise ValueError(f"Illegal AgentResource json string！{d}")
        return [AgentResource.from_dict(item) for item in json_array]

    def to_dict(self) -> Dict[str, Any]:
        temp = self.dict()
        for field, value in temp.items():
            if isinstance(value, Enum):
                temp[field] = value.value
        return temp


class ResourceClient(ABC):
    @property
    def type(self) -> ResourceType:
        pass

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> str:
        """
        Get the content introduction prompt of the specified resource
        Args:
            value:

        Returns:

        """
        return ""

    def get_data_type(self, resource: AgentResource) -> str:
        return ""

    async def get_resource_prompt(
        self, conv_uid, resource: AgentResource, question: Optional[str] = None
    ) -> str:
        return resource.resource_prompt_template().format(
            data_type=self.get_data_type(resource),
            data_introduce=await self.get_data_introduce(resource, question),
        )
