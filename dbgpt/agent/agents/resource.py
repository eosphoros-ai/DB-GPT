from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class ResourceType(Enum):
    DB = "db"
    Knowledge = "knowledge"
    Plugin = "plugin"
    Internet = "internet"


@dataclasses.dataclass()
class AgentResource:
    type: ResourceType
    name: str
    introduce: str
    value: str
    is_dynamic: bool = (
        False  # Is the current resource predefined or dynamically passed in?
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
