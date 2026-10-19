"""Unit tests for the TaskFlow agent runner (profiles / assembly / events)."""

import json

import pytest

from dbgpt_app.operators.agent_runner import (
    AgentStepEvent,
    _build_resources_section,
    _build_skills_section,
    _make_multi_db_sql_tool,
    build_user_message,
    get_agent_profile,
    list_agent_profiles,
    list_builtin_tools,
    run_react_agent,
)


class TestManifests:
    def test_profiles(self):
        profiles = list_agent_profiles()
        ids = {p["id"] for p in profiles}
        assert ids == {"react_data", "react_knowledge", "react_general"}
        for p in profiles:
            assert p["label"] and p["label_en"] and p["desc"]

    def test_builtin_tools(self):
        ids = {t["id"] for t in list_builtin_tools()}
        assert "sql_query" in ids and "knowledge_retrieve" in ids

    def test_profile_fallback(self):
        assert get_agent_profile("nope").profile_id == "react_general"
        assert get_agent_profile(None).profile_id == "react_general"
        assert get_agent_profile("react_data").default_tools


class TestPromptAssembly:
    def test_user_message_with_sources(self):
        msg = build_user_message(
            "复核数字", "有多少张表", [("数据库查询", "db_query", "| a |\n|-|\n| 1 |")]
        )
        assert "复核数字" in msg
        assert "有多少张表" in msg
        assert '<source node="数据库查询" kind="db_query">' in msg
        assert "| 1 |" in msg

    def test_user_message_truncates(self):
        big = "x" * 30_000
        msg = build_user_message("g", "q", [("n1", "data", big), ("n2", "data", big)])
        assert "已截断" in msg
        assert len(msg) < 30_000

    def test_empty_sections(self):
        msg = build_user_message("g", "q", [])
        assert "<source" not in msg

    def test_resources_section(self):
        sec = _build_resources_section(["db1"], ["kb1"], True)
        assert "db1" in sec and "kb1" in sec
        assert _build_resources_section([], [], True) == ""

    def test_skills_section_empty(self):
        assert _build_skills_section([], True) == ""


class TestKbFileTools:
    def test_builds_family_per_spaces(self):
        from dbgpt_app.operators.agent_runner import _make_kb_file_tools

        tools = _make_kb_file_tools(["kb_a", "kb_b"], None)
        names = {getattr(t, "__name__", "") for t in tools}
        expected = {"_kb_ls", "_kb_glob", "_kb_grep", "_kb_cat", "_semantic_search"}
        assert expected <= names

    @pytest.mark.asyncio
    async def test_scope_guard(self):
        from dbgpt_app.operators.agent_runner import _make_kb_file_tools

        tools = _make_kb_file_tools(["kb_a"], None)
        kb_ls = next(t for t in tools if t.__name__ == "_kb_ls")
        out = json.loads(await kb_ls(space="kb_c"))["chunks"][0]["content"]
        assert "不在本节点可用范围" in out

    @pytest.mark.asyncio
    async def test_multi_space_requires_explicit_space(self):
        from dbgpt_app.operators.agent_runner import _make_kb_file_tools

        tools = _make_kb_file_tools(["kb_a", "kb_b"], None)
        kb_ls = next(t for t in tools if t.__name__ == "_kb_ls")
        out = json.loads(await kb_ls())["chunks"][0]["content"]
        assert "请显式指定 space" in out
        assert "kb_a" in out and "kb_b" in out

    def test_empty_spaces(self):
        from dbgpt_app.operators.agent_runner import _make_kb_file_tools

        assert _make_kb_file_tools([], None) == []


class TestMultiDbSqlTool:
    def _run(self, tool, sql, db_name=None):
        out = tool(sql=sql, db_name=db_name) if db_name else tool(sql=sql)
        return json.loads(out)["chunks"][0]["content"]

    def test_blocks_write_sql(self):
        tool = _make_multi_db_sql_tool(["db_a"], None)
        content = self._run(tool, "DELETE FROM t")
        assert "安全限制" in content

    def test_rejects_out_of_scope_db(self):
        tool = _make_multi_db_sql_tool(["db_a"], None)
        content = self._run(tool, "SELECT 1", db_name="db_b")
        assert "不在本节点可用范围" in content

    def test_multi_db_requires_explicit_name(self):
        tool = _make_multi_db_sql_tool(["db_a", "db_b"], None)
        content = self._run(tool, "SELECT 1")
        assert "请显式指定 db_name" in content


class TestMarkerSanitize:
    def test_marker_with_backticks_in_steps_keeps_block_intact(self):
        from dbgpt_app.operators.taskflow import build_step_marker

        marker = build_step_marker(
            step_id="n2",
            label="思考并回复",
            kind="agent",
            status="running",
            steps=[
                {
                    "kind": "thinking",
                    "title": "思考",
                    "detail": "看 ```vis-thinking\nraw stuff\n``` 和 ```code``` 块",
                    "round": 1,
                }
            ],
        )
        # Only the two fence lines may contain triple backticks.
        body = marker.strip().split("\n")
        assert body[0].startswith("```vis-flow-step")
        assert body[-1] == "```"
        payload = json.loads("\n".join(body[1:-1]))
        assert payload["step_id"] == "n2"
        assert "```" not in payload["steps"][0]["detail"]


class TestThoughtCleaning:
    def test_strips_vis_blocks_and_protocol(self):
        from dbgpt_app.operators.agent_runner import _clean_thought_text

        raw = (
            "```vis-thinking\n需要列出知识库文件\n```\n"
            "Thought: 用户问有哪些文档,应先列清单。\n"
            "Action Intention: 列出根目录\n"
            "Action: kb_ls\n"
            "Action Input: {}"
        )
        cleaned = _clean_thought_text(raw)
        assert "vis-thinking" not in cleaned
        assert "Action" not in cleaned
        assert "先列清单" in cleaned

    def test_no_thought_prefix_returns_stripped(self):
        from dbgpt_app.operators.agent_runner import _clean_thought_text

        assert _clean_thought_text("```vis-thinking\nabc\n```hello") == "hello"


class TestRobustFinalAnswer:
    def test_multiline_markdown_result_extracted(self):
        from dbgpt_app.operators.agent_runner import _robust_final_answer

        report = (
            "# 报告标题\n\n## 一、核心结论\n"
            "1. **销售呈季节性**,假日周提升约 +8%。\n\n| a |\n|---|\n| 1 |"
        )
        raw = (
            "Thought: 工具不可用,直接产出报告。\n\n"
            "Action: terminate\n"
            f'Action Input: {{"result": {json.dumps(report)}}}'
        )
        assert _robust_final_answer(raw) == report

    def test_unparseable_envelope_falls_back_to_stripped(self):
        from dbgpt_app.operators.agent_runner import _robust_final_answer

        raw = "Thought: x\nAction: terminate\nAction Input: {broken json\n正文内容"
        out = _robust_final_answer(raw)
        assert "Thought:" not in out and "Action Input:" not in out
        assert "正文内容" in out

    def test_plain_text_passthrough(self):
        from dbgpt_app.operators.agent_runner import _robust_final_answer

        assert _robust_final_answer("就是结论本身") == "就是结论本身"


class _StubAgent:
    """Captures the bind chain and returns a canned reply with fake steps."""

    instances = []

    def __init__(self, **kwargs):
        self.bound = []
        self.kwargs = kwargs
        _StubAgent.instances.append(self)

    def bind(self, obj):
        self.bound.append(obj)
        return self

    async def build(self):
        return self

    async def generate_reply(
        self, received_message=None, sender=None, stream_callback=None, **_
    ):
        self.received = received_message.content
        if stream_callback:
            await stream_callback("thinking", {"round": 1, "llm_reply": "想一下"})
            await stream_callback(
                "act",
                {
                    "round": 1,
                    "action_output": {
                        "action": "sql_query",
                        "action_input": {"sql": "SELECT 1"},
                        "observations": "| 1 |",
                    },
                },
            )
        from dbgpt.agent import AgentMessage

        return AgentMessage(content="最终答案")


class _StubGptsMemory:
    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_run_react_agent_end_to_end(monkeypatch):
    monkeypatch.setattr(
        "dbgpt.agent.expand.tool_calling_agent.ToolCallingReActAgent", _StubAgent
    )
    monkeypatch.setattr("dbgpt.agent.core.memory.gpts.GptsMemory", _StubGptsMemory)

    events = []

    async def on_step(ev: AgentStepEvent):
        events.append(ev)

    answer = await run_react_agent(
        goal="复核",
        question="有多少张表?",
        upstream_sections=[("数据库查询", "db_query", "| 5 |")],
        profile_id="react_data",
        tools=["sql_query"],
        datasources=["db_a"],
        max_turns=5,
        llm_client=None,
        on_step=on_step,
        language="zh",
    )
    assert answer == "最终答案"
    agent = _StubAgent.instances[-1]
    # The user message carries goal + question + sourced upstream material.
    assert "复核" in agent.received
    assert "有多少张表?" in agent.received
    assert '<source node="数据库查询" kind="db_query">' in agent.received
    # Step events stream through: thinking / action / observation / answer.
    kinds = [e.kind for e in events]
    assert kinds[0] == "thinking"
    assert "action" in kinds and "observation" in kinds
    assert kinds[-1] == "answer"
    action_event = next(e for e in events if e.kind == "action")
    assert action_event.title == "sql_query"
