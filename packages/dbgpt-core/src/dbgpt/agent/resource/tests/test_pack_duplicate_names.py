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

import pytest

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
        """Create a resource for one knowledge space."""
        self._name = name
        self._space_name = space_name

    @classmethod
    def type(cls) -> ResourceType:
        """Return the knowledge resource type."""
        return ResourceType.Knowledge

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[_SpaceParameters]:
        """Return the parameters class used by ResourceManager."""
        return _SpaceParameters

    @property
    def name(self) -> str:
        """Return the resource name."""
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
        """Return a prompt and references naming the space."""
        return f"space:{self._space_name}", {self._space_name: {}}


def test_same_named_resources_are_all_prompted():
    """Both same-named resources contribute their prompt and references."""
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
    """ResourceManager.build_resource keeps two resources with the default name."""
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


def test_last_duplicate_keeps_plain_name_key():
    """The last duplicate keeps the plain name, so execution routing is unchanged."""
    first = _SpaceResource("kb", "a")
    second = _SpaceResource("kb", "b")
    pack = ResourcePack([first, second])

    assert pack._get_resource_by_name("kb") is second
    assert pack._get_resource_by_name("kb_1") is first
    assert pack.sub_resources == [first, second]


def test_suffix_skips_names_of_later_resources():
    """A suffixed key never takes the name of another resource in the pack."""
    first = _SpaceResource("kb", "a")
    second = _SpaceResource("kb", "b")
    named_kb_1 = _SpaceResource("kb_1", "c")
    pack = ResourcePack([first, second, named_kb_1])

    assert pack._get_resource_by_name("kb_1") is named_kb_1
    assert pack._get_resource_by_name("kb") is second
    assert pack._get_resource_by_name("kb_2") is first
    assert pack.sub_resources == [first, second, named_kb_1]


@pytest.mark.parametrize("overwrite", [False, True])
def test_append_moves_a_generated_key_out_of_the_way(overwrite):
    """Appending a resource really named like a generated key keeps everything."""
    first = _SpaceResource("kb", "a")
    second = _SpaceResource("kb", "b")
    named_kb_1 = _SpaceResource("kb_1", "c")
    pack = ResourcePack([first, second])

    pack.append(named_kb_1, overwrite=overwrite)

    assert pack._get_resource_by_name("kb_1") is named_kb_1
    assert pack._get_resource_by_name("kb") is second
    assert pack._get_resource_by_name("kb_2") is first
    assert pack.sub_resources == [first, second, named_kb_1]


def test_append_still_rejects_a_real_duplicate():
    """Appending a resource whose name is really used still raises."""
    pack = ResourcePack([_SpaceResource("kb", "a")])

    with pytest.raises(ValueError):
        pack.append(_SpaceResource("kb", "b"))


def test_distinct_names_are_unchanged():
    """Unique names are still used as keys unchanged."""
    resources = [_SpaceResource("a", "a"), _SpaceResource("b", "b")]
    pack = ResourcePack(resources)

    assert list(pack._resources) == ["a", "b"]


def test_tool_pack_still_keys_tools_by_name():
    """ToolPack keeps keying tools by the name the LLM calls."""

    def first() -> str:
        """First tool."""
        return "first"

    def second() -> str:
        """Second tool."""
        return "second"

    tool_a = FunctionTool("search", first)
    tool_b = FunctionTool("search", second)
    pack = ToolPack([tool_a, tool_b])

    assert pack.sub_resources == [tool_b]
    assert pack.execute(resource_name="search") == "second"


def test_pack_merges_references_of_every_knowledge_resource():
    """References under the shared ``knowledge`` key are merged, not replaced."""

    class _Referenced(_SpaceResource):
        async def get_prompt(self, **kwargs: Any):
            """Return only references for the space."""
            return "", {"knowledge": [{"name": f"{self._space_name}.md"}]}

    pack = ResourcePack(
        [_Referenced(_DEFAULT_NAME, "time"), _Referenced(_DEFAULT_NAME, "location")]
    )

    _, references = asyncio.run(pack.get_prompt(question="where and when?"))

    assert references == {"knowledge": [{"name": "time.md"}, {"name": "location.md"}]}
