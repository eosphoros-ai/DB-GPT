"""``ResourcePack`` must keep every resource, even when names collide.

The app editor gives every new resource the same default name ("My Agent
Resource"), so an agent bound to two knowledge bases usually receives two
resources with one name. The pack used to index them by name only, so the later
resource replaced the earlier one and only one knowledge base was ever recalled
(issue #2579).
"""

import asyncio
import dataclasses
import json
from typing import Any, Dict, Optional, Tuple, Type

from dbgpt.component import SystemApp

from ..base import AgentResource, Resource, ResourceParameters, ResourceType
from ..manage import ResourceManager
from ..pack import ResourcePack
from ..tool.base import FunctionTool
from ..tool.pack import ToolPack

_DEFAULT_NAME = "My Agent Resource"


@dataclasses.dataclass
class _SpaceParameters(ResourceParameters):
    space_name: Optional[str] = dataclasses.field(default=None)


class _SpaceResource(Resource[_SpaceParameters]):
    """A knowledge-like resource that prompts with its space name."""

    def __init__(self, name: str, space_name: Optional[str] = None, **kwargs: Any):
        self._name = name
        self._space_name = space_name

    @classmethod
    def type(cls) -> ResourceType:
        return ResourceType.Knowledge

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[_SpaceParameters]:
        return _SpaceParameters

    @property
    def name(self) -> str:
        return self._name

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        return f"space:{self._space_name}", {self._space_name: {}}


def test_same_named_resources_are_all_prompted():
    pack = ResourcePack(
        [
            _SpaceResource(_DEFAULT_NAME, "time"),
            _SpaceResource(_DEFAULT_NAME, "location"),
        ]
    )

    prompt, references = asyncio.run(pack.get_prompt(question="where and when?"))

    assert prompt.split("\n") == ["space:time", "space:location"]
    assert set(references) == {"time", "location"}
    assert [r._space_name for r in pack.sub_resources] == ["time", "location"]


def test_build_resource_keeps_same_named_resources():
    manager = ResourceManager(SystemApp())
    manager.register_resource(_SpaceResource)

    pack = manager.build_resource(
        [
            AgentResource(
                type=ResourceType.Knowledge.value,
                value=json.dumps({"name": _DEFAULT_NAME, "space_name": space}),
            )
            for space in ("time", "location")
        ]
    )

    assert isinstance(pack, ResourcePack)
    assert [r._space_name for r in pack.sub_resources] == ["time", "location"]


def test_first_resource_keeps_plain_name_key():
    first = _SpaceResource("kb", "a")
    second = _SpaceResource("kb", "b")
    taken = _SpaceResource("kb_1", "c")
    pack = ResourcePack([first, taken, second])

    assert pack._get_resource_by_name("kb") is first
    assert pack._get_resource_by_name("kb_1") is taken
    assert pack._get_resource_by_name("kb_2") is second


def test_distinct_names_are_unchanged():
    resources = [_SpaceResource("a", "a"), _SpaceResource("b", "b")]
    pack = ResourcePack(resources)

    assert list(pack._resources) == ["a", "b"]


def test_tool_pack_still_keys_tools_by_name():
    def first() -> str:
        """First tool."""
        return "first"

    def second() -> str:
        """Second tool."""
        return "second"

    tool_a = FunctionTool("search", first)
    tool_b = FunctionTool("search", second)
    pack = ToolPack([tool_a, tool_b])

    assert list(pack._resources) == ["search"]
    assert pack._resources["search"] is tool_b
