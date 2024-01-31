from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any, Dict, List, Optional


class ResourceType(Enum):
    DB = "db"
    Knowledge = "knowledge"
    Internet = "internet"
    Plugin = "plugin"


@dataclasses.dataclass()
class AgentResource:
    type: ResourceType
    name: str
    introduce: str
    value: str
    is_dynamic: bool = (
        False
    )

    def to_resource_prompt(self):
        return f""""""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Optional[AgentResource]:
        if d is None:
            return None
        return AgentResource(
            type=ResourceType(d.get("type")),
            name=d.get("name"),
            introduce=d.get("introduce"),
            value=d.get("value", None),
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def json_to_agent_resource_list(json_array: str) -> List[AgentResource]:
    data_list = json.loads(json_array)
    return [AgentResource.from_dict(item) for item in data_list]


def dataclass_to_dict(obj: Any) -> dict:
    if dataclasses.is_dataclass(obj):
        d = dataclasses.asdict(obj)
        for field, value in d.items():
            if isinstance(value, Enum):
                d[field] = value.value
        return d
    raise TypeError("Provided object is not a dataclass instance")
