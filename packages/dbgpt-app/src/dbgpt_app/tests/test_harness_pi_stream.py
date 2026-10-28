"""Tests for the pi branch SSE translation layer."""

import json
from types import SimpleNamespace

from dbgpt_app.agent_harness.base import HarnessEvent, HarnessEventKind
from dbgpt_app.openapi.api_v1.harness_pi_stream import (
    _close_dangling_steps,
    _PiSessionState,
    _sse_event,
    _translate_event,
    resolve_harness_engine,
)


def _decode(sse: str) -> dict:
    assert sse.startswith("data: ")
    return json.loads(sse.removeprefix("data: "))


def _tool_start(state):
    return _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.TOOL_START,
            tool_name="read",
            round=1,
        ),
    )


def test_pi_protocol_text_is_filtered_during_streaming_and_history():
    state = _PiSessionState()
    state.round_no = 1
    raw = (
        "Thought: private reasoning\n"
        "Action Intention: 读取数据，再核对结果。\nAction: read"
    )
    for character in raw:
        frames = _translate_event(
            state,
            HarnessEvent(kind=HarnessEventKind.TEXT_DELTA, text=character, round=1),
        )
        for frame in frames:
            event = _decode(frame)
            assert event["type"] == "progress"
            assert event["content"] in "读取数据，再核对结果。"
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.MESSAGE_END,
            text=raw,
            round=1,
            data={"has_tool_calls": True},
        ),
    )
    assert _decode(frames[0])["streaming"] is False
    assert state.history_steps[0]["progress_content"] == "读取数据，再核对结果。"
    assert state.history_steps[0]["status"] == "done"


def test_resolve_engine_default(monkeypatch, tmp_path):
    from dbgpt_app.openapi.api_v1 import harness_pi_stream as hs

    monkeypatch.setattr(hs, "get_harness_engine_pref", lambda: "dbgpt")

    class _D:
        ext_info = {"harness_engine": "pi"}
        user_input = ""

    assert resolve_harness_engine(_D()) == "pi"

    class _D2:
        ext_info = None
        user_input = ""

    assert resolve_harness_engine(_D2()) == "dbgpt"

    class _D3:
        ext_info = {"harness_engine": "unknown-engine"}

    assert resolve_harness_engine(_D3()) == "dbgpt"


def test_pi_loopback_port_matches_running_app(monkeypatch):
    from dbgpt_app.openapi.api_v1 import harness_pi_stream as hs

    monkeypatch.setattr(
        hs.CFG,
        "SYSTEM_APP",
        SimpleNamespace(
            config=SimpleNamespace(
                configs={
                    "app_config": SimpleNamespace(
                        service=SimpleNamespace(web=SimpleNamespace(port=5671))
                    )
                }
            )
        ),
    )
    assert hs._web_port() == 5671


def test_resolve_engine_pref_fallback(monkeypatch):
    from dbgpt_app.openapi.api_v1 import harness_pi_stream as hs

    monkeypatch.setattr(hs, "get_harness_engine_pref", lambda: "pi")

    class _D:
        ext_info = {}
        user_input = ""

    assert resolve_harness_engine(_D()) == "pi"


def test_tool_flow_to_sse():
    state = _PiSessionState()
    # thinking streams live: first delta opens a "思考中"
    # step, later deltas append thought chunks
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.THINKING_DELTA,
            text="Think...",
            round=1,
        ),
    )
    types = [_decode(f)["type"] for f in frames]
    assert types == ["step.start", "step.chunk"]
    assert _decode(frames[0])["title"] == "思考中"
    assert _decode(frames[1])["output_type"] == "thought"
    assert _decode(frames[1])["content"] == "Think..."
    # tool start closes the thought step, then opens the
    # tool step with meta carrying the thought
    state.round_no = 1
    frames = _tool_start(state)
    types = [_decode(f)["type"] for f in frames]
    assert types == ["step.done", "step.start", "step.meta"]
    meta = _decode(frames[2])
    assert meta["action"] == "read"
    assert meta["thought"] == "Think..."
    # tool end chunks output then closes the step
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.TOOL_END,
            tool_name="read",
            text="file content",
            data={"is_error": False, "duration_ms": 5},
            round=1,
        ),
    )
    types = [_decode(f)["type"] for f in frames]
    assert types == ["step.chunk", "step.done"]
    assert _decode(frames[-1])["status"] == "done"
    # thought step + tool step both land in history
    assert len(state.history_steps) == 2
    assert state.history_steps[0]["detail"] == "pi agent thinking"
    assert state.history_steps[1]["action"] == "read"


def test_tool_error_marks_failed():
    state = _PiSessionState()
    state.round_no = 2
    _tool_start(state)
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.TOOL_END,
            tool_name="bash",
            text="boom",
            data={"is_error": True},
            round=2,
        ),
    )
    assert _decode(frames[-1])["status"] == "failed"


def test_settled_and_dangling_close():
    state = _PiSessionState()
    state.round_no = 1
    _tool_start(state)
    # settled without a tool end -> dangling step closed
    frames = _translate_event(
        state,
        HarnessEvent(kind=HarnessEventKind.SETTLED, data={"aborted": False}),
    )
    assert frames == []
    assert state.done is True
    frames = _close_dangling_steps(state)
    assert [_decode(f)["type"] for f in frames] == ["step.done"]
    assert _decode(frames[0])["status"] == "done"


def test_message_end_carries_final_text():
    state = _PiSessionState()
    state.round_no = 1
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.MESSAGE_END,
            text="final answer text",
            round=1,
        ),
    )
    assert frames == []
    assert state.final_text == "final answer text"


def test_sse_frame_shape():
    frame = _sse_event({"type": "done"})
    assert frame == 'data: {"type": "done"}\n\n'


def test_public_progress_is_persisted_before_tools_and_not_a_final_answer():
    state = _PiSessionState()
    state.round_no = 1
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.MESSAGE_END,
            text="先核对指标口径，然后查询数据。",
            round=1,
            data={"has_tool_calls": True},
        ),
    )
    assert _decode(frames[0])["type"] == "progress"
    assert state.final_text == ""
    assert (
        state.history_steps[0]["progress_content"] == "先核对指标口径，然后查询数据。"
    )
    _tool_start(state)
    _translate_event(
        state,
        HarnessEvent(kind=HarnessEventKind.TOOL_END, tool_name="read", text="ok"),
    )
    assert [step["action"] for step in state.history_steps] == ["__progress__", "read"]


def test_parallel_calls_have_independent_ids_and_completion():
    state = _PiSessionState()
    starts = []
    for call_id in ("a", "b"):
        starts.append(
            _translate_event(
                state,
                HarnessEvent(
                    kind=HarnessEventKind.TOOL_START,
                    tool_name="read",
                    data={"tool_call_id": call_id, "args": {"path": call_id}},
                ),
            )
        )
    ids = [_decode(frames[0])["id"] for frames in starts]
    assert ids[0] != ids[1]
    _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.TOOL_END,
            tool_name="read",
            data={"tool_call_id": "b", "is_error": True},
        ),
    )
    assert state.call_step_map["a"]["status"] == "running"
    _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.TOOL_END, tool_name="read", data={"tool_call_id": "a"}
        ),
    )
    assert {step["id"]: step["status"] for step in state.history_steps} == {
        ids[0]: "done",
        ids[1]: "failed",
    }
    assert [step["id"] for step in state.history_steps] == ids


def test_progress_streams_before_message_end_and_updates_history_in_place():
    state = _PiSessionState()
    state.round_no = 1
    for fragment, expected in [
        ("先核对", "先核对"),
        ("指标口径。", "先核对指标口径。"),
    ]:
        frames = _translate_event(
            state, HarnessEvent(kind=HarnessEventKind.TEXT_DELTA, text=fragment)
        )
        event = _decode(frames[0])
        assert event["content"] == expected
        assert event["streaming"] is True
        assert event["id"] == "progress-1"
        assert len(state.history_steps) == 1
    frames = _translate_event(
        state,
        HarnessEvent(
            kind=HarnessEventKind.MESSAGE_END,
            text="先核对指标口径。",
            data={"has_tool_calls": True},
        ),
    )
    assert _decode(frames[-1])["streaming"] is False
    assert len(state.history_steps) == 1
    assert state.history_steps[0]["status"] == "done"


def test_streamed_final_text_moves_out_of_progress_without_duplicate_history():
    state = _PiSessionState()
    state.round_no = 1
    _translate_event(
        state, HarnessEvent(kind=HarnessEventKind.TEXT_DELTA, text="最终答案")
    )
    frames = _translate_event(
        state, HarnessEvent(kind=HarnessEventKind.MESSAGE_END, text="最终答案")
    )
    assert [_decode(frame)["type"] for frame in frames] == [
        "progress.remove",
        "final.chunk",
    ]
    assert state.history_steps == []
    assert state.final_text == "最终答案"
