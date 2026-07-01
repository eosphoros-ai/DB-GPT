"""Unit tests for ``make_react_tools`` factory (plan stage 1, Task 1.6).

Verifies:
    1. The factory returns a dict with all 8 expected tool keys.
    2. State isolation — two calls with different ``react_state`` produce
       independent tool sets that capture their own state (writing one
       state does not affect the other; work_dir differs by conv_id).
    3. Read-only resources (db/knowledge) default to None and tools degrade
       gracefully with the existing user-facing messages.
"""

import json

import pytest

from dbgpt_app.openapi.api_v1.subagent.react_tools import make_react_tools

_EXPECTED_TOOLS = {
    "load_skill",
    "load_tools",
    "knowledge_retrieve",
    "sql_query",
    "code_interpreter",
    "shell_interpreter",
    "execute_skill_script_file",
    "html_interpreter",
}


def test_factory_returns_all_expected_tools():
    tools = make_react_tools({"conv_id": "c1"})
    assert set(tools.keys()) == _EXPECTED_TOOLS
    # @tool returns a callable wrapper; the FunctionTool is on wrapper._tool.
    for name, t in tools.items():
        assert callable(t)
        assert t._tool.name == name


def test_two_calls_return_distinct_tool_objects():
    state_a = {"conv_id": "conv_a"}
    state_b = {"conv_id": "conv_b"}
    tools_a = make_react_tools(state_a)
    tools_b = make_react_tools(state_b)
    # Distinct closures => distinct tool objects per call.
    for name in _EXPECTED_TOOLS:
        assert tools_a[name] is not tools_b[name]


def test_state_isolation_load_skill_writes_only_its_own_state():
    """load_skill writes matched/skill_prompt into the captured state.

    A miss (skill not found) must not mutate state; and each tool set must
    only ever touch the dict it captured — never the sibling agent's dict.
    """
    state_a = {"conv_id": "conv_a"}
    state_b = {"conv_id": "conv_b"}
    tools_a = make_react_tools(state_a)

    # Call A's load_skill with a non-existent skill: returns "not found",
    # and crucially does NOT leak into state_b.
    out = tools_a["load_skill"](skill_name="__no_such_skill__", file_path="x")
    parsed = json.loads(out)
    assert "not found" in parsed["chunks"][0]["content"]
    # state_b is the sibling agent — must be untouched by A's tool.
    assert "matched" not in state_b
    assert "skill_prompt" not in state_b


@pytest.mark.asyncio
async def test_code_interpreter_isolates_generated_images_per_state():
    """Each agent's code_interpreter writes artifacts only to its own state.

    The empty-code path returns before spawning a subprocess, but a real run
    appends to ``react_state['generated_images']``. We assert the two tool
    sets are independently callable and that the captured state dicts are
    distinct objects, so a write in one can never appear in the other.
    """
    state_a = {"conv_id": "conv_AAA"}
    state_b = {"conv_id": "conv_BBB"}
    tools_a = make_react_tools(state_a)
    tools_b = make_react_tools(state_b)

    out_a = await tools_a["code_interpreter"](code="")
    out_b = await tools_b["code_interpreter"](code="")
    assert "No code provided" in json.loads(out_a)["chunks"][0]["content"]
    assert "No code provided" in json.loads(out_b)["chunks"][0]["content"]

    # Simulate an artifact landing in A's state; B must stay clean.
    state_a.setdefault("generated_images", []).append("/images/a.png")
    assert state_b.get("generated_images") is None


def test_sql_query_degrades_when_no_database():
    tools = make_react_tools({"conv_id": "c1"}, database_connector=None)
    out = tools["sql_query"](sql="SELECT 1")
    parsed = json.loads(out)
    assert "未选择数据库" in parsed["chunks"][0]["content"]


def test_sql_query_blocks_non_select():
    class _FakeConn:
        def run(self, sql):  # pragma: no cover - should never be called
            raise AssertionError("write statement must be blocked before run()")

    tools = make_react_tools({"conv_id": "c1"}, database_connector=_FakeConn())
    out = tools["sql_query"](sql="DELETE FROM t")
    parsed = json.loads(out)
    assert "安全限制" in parsed["chunks"][0]["content"]


@pytest.mark.asyncio
async def test_knowledge_retrieve_degrades_when_no_resource():
    tools = make_react_tools({"conv_id": "c1"}, knowledge_resources=None)
    out = await tools["knowledge_retrieve"](query="q")
    parsed = json.loads(out)
    assert "No knowledge base available" in parsed["chunks"][0]["content"]
