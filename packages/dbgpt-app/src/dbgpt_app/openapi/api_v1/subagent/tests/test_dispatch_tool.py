"""Unit tests for dispatch_parallel_tasks orchestration (plan stage 3)."""

import json

import pytest

import dbgpt_app.openapi.api_v1.subagent.dispatcher as disp
from dbgpt_app.openapi.api_v1.subagent.dispatcher import make_dispatch_tool


def _make_fake_llm_client():
    from dbgpt.core.interface.llm import LLMClient

    class _FakeLLMClient(LLMClient):
        async def generate(self, *a, **k):  # pragma: no cover
            raise NotImplementedError

        async def generate_stream(self, *a, **k):  # pragma: no cover
            raise NotImplementedError
            yield

        async def models(self, *a, **k):  # pragma: no cover
            return []

        async def count_token(self, *a, **k):  # pragma: no cover
            return 0

    return _FakeLLMClient()


class _Report:
    def __init__(self, content):
        self.content = content


class _Reply:
    def __init__(self, content):
        self.content = content
        self.action_report = _Report(content)


class _FakeAgent:
    """A sub-agent whose generate_reply returns a canned reply.

    If ``acts`` is given, it drives the stream_callback with those tool
    actions (simulating the sub-agent's internal act events) before replying.
    """

    def __init__(
        self,
        reply_text,
        *,
        raise_exc=None,
        images=None,
        acts=None,
        action_inputs=None,
        emit_thinking=False,
        drop_action_input_on_act=False,
    ):
        self._reply_text = reply_text
        self._raise_exc = raise_exc
        self._images = images or []
        self._acts = acts or []
        self._action_inputs = action_inputs or {}
        self._emit_thinking = emit_thinking
        self._drop_action_input_on_act = drop_action_input_on_act

    async def generate_reply(self, *a, **k):
        if self._raise_exc:
            raise self._raise_exc
        cb = k.get("stream_callback")
        if cb is not None:
            for i, action in enumerate(self._acts):
                action_input = self._action_inputs.get(action)
                if self._emit_thinking and action_input:
                    await cb(
                        "thinking",
                        {
                            "round": i + 1,
                            "llm_reply": (
                                f"Thought: run the confirmed tool\n"
                                f"Action: {action}\n"
                                f"Action Input: {action_input}"
                            ),
                        },
                    )
                await cb(
                    "act",
                    {
                        "round": i + 1,
                        "action_output": {
                            "action": action,
                            "action_intention": f"doing {action}",
                            "action_input": (
                                None if self._drop_action_input_on_act else action_input
                            ),
                            # Simulate a real tool result wrapper so the
                            # dispatcher's _parse_observation_chunks unwraps it.
                            "observations": (
                                '{"chunks": [{"output_type": "markdown", '
                                '"content": "| a | b |"}]}'
                            ),
                        },
                    },
                )
            # terminate act must NOT be forwarded as a step
            await cb("act", {"round": 99, "action_output": {"terminate": True}})
        return _Reply(self._reply_text)


def _patch_builder(monkeypatch, agent_factory):
    """Patch build_sub_react_agent to yield (agent, conv_id, state)."""

    async def _fake_build(goal, idx, **kwargs):
        agent, state = agent_factory(idx, goal)
        return agent, f"parent__sub_{idx}", state

    monkeypatch.setattr(disp, "build_sub_react_agent", _fake_build)


def _collector():
    events = []

    async def emit_event(payload):
        events.append(payload)

    return events, emit_event


@pytest.mark.asyncio
async def test_dispatch_runs_all_tasks_and_relays_text(monkeypatch):
    def factory(idx, goal):
        return _FakeAgent(f"result-{idx}"), {"generated_images": []}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    out = await tool(tasks=[{"goal": "g0", "title": "A"}, {"goal": "g1", "title": "B"}])
    parsed = json.loads(out)
    summary = parsed["chunks"][0]["content"]
    assert "result-0" in summary and "result-1" in summary
    assert "A" in summary and "B" in summary
    # agent.start + agent.done per task (no artifacts event when none).
    starts = [e for e in events if e["type"] == "agent.start"]
    dones = [e for e in events if e["type"] == "agent.done"]
    assert len(starts) == 2 and len(dones) == 2
    assert {e["result"] for e in dones} == {"result-0", "result-1"}
    assert all(isinstance(e["elapsed_ms"], int) for e in dones)


@pytest.mark.asyncio
async def test_dispatch_summary_never_relays_react_envelope(monkeypatch):
    raw = """``````vis-thinking
internal draft
``````
Thought: I can now finish.
Action: terminate
Action Input: {"output": "Clean user-facing summary"}"""

    def factory(idx, goal):
        return _FakeAgent(raw), {"generated_images": []}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )

    out = await tool(tasks=[{"goal": "g0", "title": "A"}])
    summary = json.loads(out)["chunks"][0]["content"]
    done = next(e for e in events if e["type"] == "agent.done")

    assert "Clean user-facing summary" in summary
    assert done["result"] == "Clean user-facing summary"
    assert "Thought:" not in summary
    assert "Action Input:" not in summary
    assert "vis-thinking" not in summary


@pytest.mark.asyncio
async def test_dispatch_caps_to_max_parallel(monkeypatch):
    def factory(idx, goal):
        return _FakeAgent(f"r{idx}"), {"generated_images": []}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p",
        llm_client=_make_fake_llm_client(),
        emit_event=emit,
        max_parallel=3,
    )
    out = await tool(tasks=[{"goal": f"g{i}"} for i in range(5)])
    summary = json.loads(out)["chunks"][0]["content"]
    # Only 3 executed; the drop notice mentions the remaining 2.
    assert "另有 2 个" in summary
    assert len([e for e in events if e["type"] == "agent.start"]) == 3


@pytest.mark.asyncio
async def test_dispatch_single_failure_degrades_not_breaks(monkeypatch):
    def factory(idx, goal):
        if idx == 1:
            return _FakeAgent("", raise_exc=RuntimeError("boom")), {}
        return _FakeAgent(f"ok{idx}"), {"generated_images": []}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    out = await tool(tasks=[{"goal": "g0"}, {"goal": "g1"}, {"goal": "g2"}])
    summary = json.loads(out)["chunks"][0]["content"]
    assert "ok0" in summary and "ok2" in summary
    assert "failed" in summary  # the boom task degraded, batch survived
    dones = [e for e in events if e["type"] == "agent.done"]
    assert {"failed"} & {e["status"] for e in dones}


@pytest.mark.asyncio
async def test_dispatch_artifacts_event_emitted_separately(monkeypatch):
    def factory(idx, goal):
        return _FakeAgent(f"r{idx}"), {"generated_images": [f"/images/{idx}.png"]}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    out = await tool(tasks=[{"goal": "g0"}, {"goal": "g1"}])
    # Artifacts flow via a dedicated event, not into the relayed summary.
    art_events = [e for e in events if e["type"] == "subagent.artifacts"]
    assert len(art_events) == 1
    assert len(art_events[0]["items"]) == 2
    summary = json.loads(out)["chunks"][0]["content"]
    assert "/images/0.png" not in summary  # bytes/paths not in lead context


@pytest.mark.asyncio
async def test_dispatch_rejects_empty_tasks(monkeypatch):
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    out = await tool(tasks=[])
    assert "非空列表" in json.loads(out)["chunks"][0]["content"]
    assert events == []


@pytest.mark.asyncio
async def test_dispatch_forwards_agent_step_events(monkeypatch):
    """Sub-agent confirmed tool actions surface as agent.step events tagged
    with agent_id; terminate acts are NOT forwarded."""

    def factory(idx, goal):
        return (
            _FakeAgent(f"r{idx}", acts=["sql_query", "html_interpreter"]),
            {"generated_images": []},
        )

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(tasks=[{"goal": "g0", "title": "A"}])

    steps = [e for e in events if e["type"] == "agent.step"]
    # 2 real actions forwarded, terminate dropped.
    assert len(steps) == 2
    # First dispatch call => batch_id=1, so agent_id is sub_d1_0 (not sub_0).
    assert all(e["agent_id"] == "sub_d1_0" for e in steps)
    assert [e["action"] for e in steps] == ["sql_query", "html_interpreter"]
    assert steps[0]["intention"] == "doing sql_query"
    # The raw {"chunks":[...]} observation is parsed into structured chunks
    # (NOT forwarded as a raw JSON string) so the frontend renders a table.
    assert steps[0]["chunks"] == [{"output_type": "markdown", "content": "| a | b |"}]
    # start + 2 steps + done, in a sane order.
    types = [e["type"] for e in events]
    assert types[0] == "agent.start"
    assert types[-1] == "agent.done"


@pytest.mark.asyncio
async def test_dispatch_sql_step_forwards_only_executed_sql(monkeypatch):
    """A SQL step exposes its query without leaking other tool arguments."""

    def factory(idx, goal):
        return (
            _FakeAgent(
                f"r{idx}",
                acts=["sql_query", "html_interpreter"],
                action_inputs={
                    "sql_query": '{"sql": " SELECT country, COUNT(*) FROM users; "}',
                    "html_interpreter": '{"html": "<p>private report input</p>"}',
                },
            ),
            {"generated_images": []},
        )

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(tasks=[{"goal": "g0", "title": "A"}])

    steps = [e for e in events if e["type"] == "agent.step"]
    assert steps[0]["sql"] == "SELECT country, COUNT(*) FROM users"
    assert "action_input" not in steps[0]
    assert "sql" not in steps[1]
    assert "action_input" not in steps[1]


@pytest.mark.asyncio
async def test_dispatch_sql_step_recovers_sql_from_confirmed_thinking_event(
    monkeypatch,
):
    """The SQL survives when ActionOutput omits its original action_input."""

    def factory(idx, goal):
        return (
            _FakeAgent(
                f"r{idx}",
                acts=["sql_query"],
                action_inputs={"sql_query": '{"sql": "SELECT * FROM users;"}'},
                emit_thinking=True,
                drop_action_input_on_act=True,
            ),
            {"generated_images": []},
        )

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(tasks=[{"goal": "g0", "title": "A"}])

    step = next(e for e in events if e["type"] == "agent.step")
    assert step["sql"] == "SELECT * FROM users"
    assert "action_input" not in step


@pytest.mark.asyncio
async def test_dispatch_batch_ids_unique_across_calls(monkeypatch):
    """Two dispatch calls produce DIFFERENT agent_ids (batch dimension).

    Before the batch-id fix, batch 2's sub_0 would reuse batch 1's sub_0
    agent_id, overwriting the frontend row AND the working directory.
    """

    def factory(idx, goal):
        return _FakeAgent(f"r{idx}"), {"generated_images": []}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(tasks=[{"goal": "g0", "title": "A"}])
    await tool(tasks=[{"goal": "g0", "title": "B"}])

    starts = [e for e in events if e["type"] == "agent.start"]
    # batch 1 => sub_d1_0, batch 2 => sub_d2_0 — distinct, no overwrite.
    assert starts[0]["agent_id"] == "sub_d1_0"
    assert starts[1]["agent_id"] == "sub_d2_0"


@pytest.mark.asyncio
async def test_dispatch_artifacts_carry_agent_attribution(monkeypatch):
    """Each subagent.artifacts item is stamped with its source agent_id/name,
    so the frontend can count per-row and label "by <agent>" in the files tab.
    """

    def factory(idx, goal):
        return _FakeAgent(f"r{idx}"), {"generated_images": [f"/images/{idx}.png"]}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(
        tasks=[{"goal": "g0", "title": "销售分析"}, {"goal": "g1", "title": "品类分布"}]
    )

    art_events = [e for e in events if e["type"] == "subagent.artifacts"]
    assert len(art_events) == 1
    items = art_events[0]["items"]
    # Each item carries the agent that produced it.
    by_id = {it["agent_id"]: it for it in items}
    assert by_id["sub_d1_0"]["agent_name"] == "销售分析"
    assert by_id["sub_d1_0"]["url"] == "/images/0.png"
    assert by_id["sub_d1_1"]["agent_name"] == "品类分布"
    assert by_id["sub_d1_1"]["url"] == "/images/1.png"


@pytest.mark.asyncio
async def test_dispatch_keeps_image_chunks_in_agent_step(monkeypatch):
    """Image chunks are NO LONGER filtered out of agent.step — the right-panel
    process view inlines them like the main agent's OutputRenderer does.
    Artifacts still also flow via subagent.artifacts (dual channel).
    """

    def factory(idx, goal):
        agent = _FakeAgent(
            f"r{idx}",
            acts=["code_interpreter"],
        )

        # Override the canned observation with one containing an image chunk.
        async def _generate(*a, **k):
            cb = k.get("stream_callback")
            if cb is not None:
                await cb(
                    "act",
                    {
                        "round": 1,
                        "action_output": {
                            "action": "code_interpreter",
                            "action_intention": "画图",
                            "observations": (
                                '{"chunks": [{"output_type": "image", '
                                '"content": "/images/chart_0.png"}]}'
                            ),
                        },
                    },
                )
                await cb("act", {"round": 2, "action_output": {"terminate": True}})
            return _Reply(f"r{idx}")

        agent.generate_reply = _generate
        return agent, {"generated_images": ["/images/chart_0.png"]}

    _patch_builder(monkeypatch, factory)
    events, emit = _collector()
    tool = make_dispatch_tool(
        parent_conv_id="p", llm_client=_make_fake_llm_client(), emit_event=emit
    )
    await tool(tasks=[{"goal": "g0", "title": "A"}])

    steps = [e for e in events if e["type"] == "agent.step"]
    assert len(steps) == 1
    # Image chunk kept inline (not dropped).
    assert steps[0]["chunks"] == [
        {"output_type": "image", "content": "/images/chart_0.png"}
    ]
    # And the same image also flows via the artifacts channel.
    art = [e for e in events if e["type"] == "subagent.artifacts"]
    assert art and art[0]["items"][0]["url"] == "/images/chart_0.png"
