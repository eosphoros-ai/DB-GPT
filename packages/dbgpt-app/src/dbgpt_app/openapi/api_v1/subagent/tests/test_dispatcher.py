"""Unit tests for the sub-agent builder + read-only filter (plan stage 2).

Covers:
    - _filter_readonly_connector_tools: drops write tools (catalog
      confirm_actions), keeps read-only; fails safe when manager is None.
    - _build_sub_prompt: injects goal and optional shared context.
    - build_sub_react_agent: isolated conv_id / react_state; tool set excludes
      dispatch_parallel_tasks + todowrite, includes Terminate; None model =>
      Default LLM strategy.
"""

import pytest

from dbgpt_app.openapi.api_v1.subagent.dispatcher import (
    _SUBAGENT_FACTORY_TOOL_NAMES,
    _build_sub_prompt,
    _filter_readonly_connector_tools,
    build_sub_react_agent,
)


class _FakeEntry:
    def __init__(self, confirm_actions):
        self.confirm_actions = confirm_actions


class _FakeCatalog:
    def __init__(self, entries):
        self._entries = entries

    def list(self):
        return self._entries


class _FakeManager:
    def __init__(self, entries):
        self._catalog = _FakeCatalog(entries)

    def get_catalog(self):
        return self._catalog


class _FakeTool:
    """Mimics a connector BaseTool: name lives on ``_tool.name``."""

    def __init__(self, name):
        self._tool = type("T", (), {"name": name})()


def _make_fake_llm_client():
    """A minimal concrete LLMClient so LLMConfig's isinstance check passes."""
    from dbgpt.core.interface.llm import LLMClient

    class _FakeLLMClient(LLMClient):
        async def generate(self, *a, **k):  # pragma: no cover
            raise NotImplementedError

        async def generate_stream(self, *a, **k):  # pragma: no cover
            raise NotImplementedError
            yield  # make it an async generator

        async def models(self, *a, **k):  # pragma: no cover
            return []

        async def count_token(self, *a, **k):  # pragma: no cover
            return 0

    return _FakeLLMClient()


def test_filter_readonly_drops_write_tools():
    entries = [_FakeEntry(confirm_actions=["create_issue", "delete_repo"])]
    manager = _FakeManager(entries)
    tools = [
        _FakeTool("search_issues"),  # read-only
        _FakeTool("create_issue"),  # write -> dropped
        _FakeTool("get_repo"),  # read-only
        _FakeTool("delete_repo"),  # write -> dropped
    ]
    out = _filter_readonly_connector_tools(tools, manager)
    names = {t._tool.name for t in out}
    assert names == {"search_issues", "get_repo"}


def test_filter_readonly_empty_input():
    assert _filter_readonly_connector_tools(None, _FakeManager([])) == []
    assert _filter_readonly_connector_tools([], _FakeManager([])) == []


def test_filter_readonly_fails_safe_when_manager_none():
    # Without a catalog we cannot classify; fail safe = inject none.
    tools = [_FakeTool("anything")]
    assert _filter_readonly_connector_tools(tools, None) == []


def test_filter_readonly_keeps_all_when_no_confirm_actions():
    entries = [_FakeEntry(confirm_actions=[])]
    manager = _FakeManager(entries)
    tools = [_FakeTool("a"), _FakeTool("b")]
    out = _filter_readonly_connector_tools(tools, manager)
    assert {t._tool.name for t in out} == {"a", "b"}


def test_build_sub_prompt_includes_goal():
    pt = _build_sub_prompt("analyze sales", None)
    assert "analyze sales" in pt.template
    # No context block when extra_context is None.
    assert "Shared context" not in pt.template


def test_build_sub_prompt_includes_context():
    pt = _build_sub_prompt("goal X", "prior result: 42")
    assert "goal X" in pt.template
    assert "Shared context" in pt.template
    assert "prior result: 42" in pt.template


def test_subagent_tool_names_exclude_dispatch_and_todowrite():
    assert "dispatch_parallel_tasks" not in _SUBAGENT_FACTORY_TOOL_NAMES
    assert "todowrite" not in _SUBAGENT_FACTORY_TOOL_NAMES
    # The 8 factory tools are all present.
    assert len(_SUBAGENT_FACTORY_TOOL_NAMES) == 8


@pytest.mark.asyncio
async def test_build_sub_react_agent_isolation(monkeypatch):
    """Two sub-agents get distinct conv_id + distinct react_state objects.

    ``ReActAgent`` is imported inside build_sub_react_agent (lazy import), so
    we patch it at the SOURCE module — the function-local ``from ... import
    ReActAgent`` then resolves to our fake. GptsMemory.init only fills
    in-memory dicts (no DB), so it is safe to run for real.
    """
    import dbgpt.agent.expand.react_agent as react_mod

    class _FakeBuilt:
        def __init__(self, tool_pack):
            self.tool_pack = tool_pack

    class _FakeReActAgent:
        def __init__(self, *a, **k):
            self._tool_pack = None

        def bind(self, obj):
            # ToolPack is the only bind we care about for the assertion.
            from dbgpt.agent.resource import ToolPack

            if isinstance(obj, ToolPack):
                self._tool_pack = obj
            return self

        async def build(self):
            return _FakeBuilt(self._tool_pack)

    monkeypatch.setattr(react_mod, "ReActAgent", _FakeReActAgent)

    fake_client = _make_fake_llm_client()
    agent_a, cid_a, state_a = await build_sub_react_agent(
        "goal a", 0, parent_conv_id="parent123", llm_client=fake_client
    )
    agent_b, cid_b, state_b = await build_sub_react_agent(
        "goal b", 1, parent_conv_id="parent123", llm_client=fake_client
    )

    # batch_id defaults to 0 when not passed (back-compat path).
    assert cid_a == "parent123__d0_sub_0"
    assert cid_b == "parent123__d0_sub_1"
    assert state_a is not state_b
    assert state_a["conv_id"] == "parent123__d0_sub_0"

    # Tool pack must contain Terminate, exclude dispatch/todowrite.
    tool_names = set(agent_a.tool_pack._resources.keys())
    assert "dispatch_parallel_tasks" not in tool_names
    assert "todowrite" not in tool_names
    assert any("terminate" in n.lower() for n in tool_names)


@pytest.mark.asyncio
async def test_build_sub_react_agent_batch_id_isolates_conv_id(monkeypatch):
    """Different batch_id => different sub_conv_id for the same sub_index.

    This is the core fix for the "second dispatch overwrites first dispatch's
    sub_0" bug: batch 2's sub_0 must NOT reuse batch 1's sub_0 working dir.
    """
    import dbgpt.agent.expand.react_agent as react_mod

    class _FakeBuilt:
        def __init__(self, tool_pack):
            self.tool_pack = tool_pack

    class _FakeReActAgent:
        def __init__(self, *a, **k):
            self._tool_pack = None

        def bind(self, obj):
            from dbgpt.agent.resource import ToolPack

            if isinstance(obj, ToolPack):
                self._tool_pack = obj
            return self

        async def build(self):
            return _FakeBuilt(self._tool_pack)

    monkeypatch.setattr(react_mod, "ReActAgent", _FakeReActAgent)

    fake_client = _make_fake_llm_client()
    _, cid_batch1_sub0, _ = await build_sub_react_agent(
        "g", 0, parent_conv_id="p", llm_client=fake_client, batch_id=1
    )
    _, cid_batch2_sub0, _ = await build_sub_react_agent(
        "g", 0, parent_conv_id="p", llm_client=fake_client, batch_id=2
    )
    assert cid_batch1_sub0 == "p__d1_sub_0"
    assert cid_batch2_sub0 == "p__d2_sub_0"
    assert cid_batch1_sub0 != cid_batch2_sub0
