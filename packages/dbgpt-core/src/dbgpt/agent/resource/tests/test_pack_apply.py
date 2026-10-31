"""``ResourcePack.apply`` must hand the transformed pack back to its caller.

Both ``ReActAgent.load_resource`` and ``DataAgent.load_resource`` build the
agent's resource prompt from the object returned by
``resource.apply(apply_func=...)``.  The pack branch of the recursion never
returned, so those callers received ``None`` and dropped the prompt of every
resource pack.
"""

import asyncio
from typing import Any, Dict, Optional, Tuple

import pytest

from dbgpt.agent.resource.base import Resource, ResourceType
from dbgpt.agent.resource.pack import ResourcePack


class _PromptOnlyResource(Resource):
    """A leaf resource whose only interesting behaviour is its prompt."""

    def __init__(self, name: str):
        self._name = name

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Knowledge

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
        """Return a marker prompt so the caller can tell it was kept."""
        return f"prompt:{self._name}", None


class _ToolResource(_PromptOnlyResource):
    """A resource that agents may filter out of a pack."""

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Tool


class _StatefulPromptResource(_PromptOnlyResource):
    """A leaf resource whose prompt is derived from the pack it was applied to.

    ``ResourcePack.apply`` used to rebind its loop target to the last child and
    then write the rebuilt ``_resources`` map onto it.  A resource that reads
    ``_resources`` from itself therefore observed the whole pack, so this class
    turns that write into an observable prompt change instead of a private
    attribute assertion.
    """

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Return the marker prompt, plus any pack contents attached to it."""
        inherited = getattr(self, "_resources", None)
        if inherited:
            names = ",".join(sorted(inherited))
            return f"prompt:{self._name}[inherited:{names}]", None
        return f"prompt:{self._name}", None


def _make_pack() -> ResourcePack:
    return ResourcePack(
        [_PromptOnlyResource("kb"), _PromptOnlyResource("files")],
        name="agent-resources",
    )


@pytest.mark.asyncio
async def test_apply_returns_the_pack_it_was_given():
    """apply() must return an object callers can still build a prompt from."""
    pack = _make_pack()

    result = pack.apply(apply_func=lambda resource: resource)

    assert result is not None
    prompt, _ = await result.get_prompt()
    assert prompt == "prompt:kb\nprompt:files"


@pytest.mark.asyncio
async def test_apply_keeps_only_the_surviving_resources():
    """A filtered resource must disappear from the returned pack."""
    pack = ResourcePack(
        [_PromptOnlyResource("kb"), _ToolResource("search")],
        name="agent-resources",
    )

    def _drop_tools(resource: Resource):
        if resource.type() == ResourceType.Tool:
            return None
        return resource

    result = pack.apply(apply_func=_drop_tools)

    assert result is not None
    prompt, _ = await result.get_prompt()
    assert prompt == "prompt:kb"


def test_apply_does_not_write_the_pack_contents_onto_a_child():
    """The rebuilt map belongs to the pack; a child's prompt must not change."""
    kb = _StatefulPromptResource("kb")
    files = _StatefulPromptResource("files")
    pack = ResourcePack([kb, files], name="agent-resources")

    # The child prompts before apply() are the reference: apply() must not leak
    # the pack's contents into any child, which is what the loop rebinding did.
    pack.apply(apply_func=lambda resource: resource)

    assert asyncio.run(kb.get_prompt())[0] == "prompt:kb"
    assert asyncio.run(files.get_prompt())[0] == "prompt:files"


@pytest.mark.asyncio
async def test_apply_keeps_nested_packs():
    """A nested pack is a resource like any other and must survive apply()."""
    inner = ResourcePack([_PromptOnlyResource("inner-kb")], name="inner")
    outer = ResourcePack([_PromptOnlyResource("kb"), inner], name="outer")

    result = outer.apply(apply_func=lambda resource: resource)

    assert result is not None
    prompt, _ = await result.get_prompt()
    assert "prompt:inner-kb" in prompt
