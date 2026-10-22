"""Tests for the pi branch SSE translation layer."""

import json

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
