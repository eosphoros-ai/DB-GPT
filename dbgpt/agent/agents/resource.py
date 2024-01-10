from __future__ import annotations

from enum import Enum
import dataclasses
from typing import Any, Dict, List, Optional, Tuple, Union


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
