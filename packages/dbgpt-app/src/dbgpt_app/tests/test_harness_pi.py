"""Tests for the pi harness engine.

Transport and runner are exercised against a fake pi
subprocess (a Python stub speaking the same LF-framed
JSONL protocol), so no real pi install is needed.
Event mapping is covered with records straight from the
pi docs' JSON event stream examples.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from dbgpt_app.agent_harness.base import (
    HarnessEventKind,
    HarnessResult,
)
from dbgpt_app.agent_harness.pi.config import PiHarnessConfig
from dbgpt_app.agent_harness.pi.events import (
    _assistant_text_from_message,
    map_rpc_event,
)
from dbgpt_app.agent_harness.pi.runner import PiHarnessRunner

# A fake pi: same wire protocol as `pi --mode rpc`.
_FAKE_PI = r"""
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    rec = json.loads(line)
    rid = rec.get("id")
    typ = rec.get("type")
    if typ == "abort":
        print(json.dumps({"id": rid, "type": "response",
                          "command": "abort", "success": True}),
              flush=True)
        continue
    if typ == "prompt":
        print(json.dumps({"id": rid, "type": "response",
                          "command": "prompt", "success": True,
                          "data": {"disposition": "started"}}),
              flush=True)
        events = [
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_update",
             "usage": {"totalTokens": 5},
             "assistantMessageEvent":
                 {"type": "text_delta", "contentIndex": 0,
                  "delta": "Hel"}},
            {"type": "tool_execution_start",
             "toolCallId": "c1", "toolName": "read", "args": {}},
            {"type": "tool_execution_end",
             "toolCallId": "c1", "toolName": "read",
             "result": {"content": [{"type": "text",
                                     "text": "ok"}]},
             "isError": False, "durationMs": 5},
            {"type": "message_end",
             "message": {"role": "assistant",
                         "content": [{"type": "text",
                                      "text": "Hello done"}]}},
            {"type": "turn_end", "message": {"role": "assistant"},
             "toolResults": []},
            {"type": "agent_end", "messages": [],
             "willRetry": False},
            {"type": "agent_settled", "aborted": False},
        ]
        for ev in events:
            print(json.dumps(ev), flush=True)
    else:
        print(json.dumps({"id": rid, "type": "response",
                          "command": typ, "success": True,
                          "data": {}}), flush=True)
"""


def _make_config(tmpdir: str) -> PiHarnessConfig:
    script = Path(tmpdir) / "fake_pi.py"
    if not script.exists():
        script.write_text(_FAKE_PI, encoding="utf-8")
    return PiHarnessConfig(
        pi_cli=str(script),
        command_prefix=[sys.executable],
        cwd=tmpdir,
        idle_timeout_s=0,
        run_timeout_s=60,
        command_timeout_s=10,
        excluded_tools=["bash"],
        extra_args=["--exclude-tools", "edit"],
    )


def test_resolve_command():
    cfg = PiHarnessConfig(
        pi_cli="/opt/pi/dist/cli.js",
        excluded_tools=[],
        model="gpt-x",
        provider="openai",
    )
    argv = cfg.resolve_command()
    assert argv[:2] == [
        shutil.which("node") or "node",
        "/opt/pi/dist/cli.js",
    ]
    assert argv[2:4] == ["--mode", "rpc"]
    assert "--no-session" in argv
    assert "--model" in argv and "gpt-x" in argv
    argv2 = PiHarnessConfig(pi_cli="pi").resolve_command()
    assert argv2[0] == "pi"
    assert "--no-session" in argv2


def test_resolve_command_prefix():
    cfg = PiHarnessConfig(
        pi_cli="/tmp/fake.py",
        command_prefix=["/usr/bin/env"],
        excluded_tools=[],
    )
    argv = cfg.resolve_command()
    assert argv == [
        "/usr/bin/env",
        "/tmp/fake.py",
        "--mode",
        "rpc",
        "--no-session",
    ]


def test_prepare_agent_dir_env_interpolation():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = PiHarnessConfig(
            cwd=tmp,
            model_api_base="http://127.0.0.1:5670/api/v2",
            model="glm-5.3-flash",
            api_key_env="TEST_HARNESS_KEY",
        )
        cfg.prepare_agent_dir()
        path = os.path.join(cfg.agent_dir, "models.json")
        with open(path) as f:
            data = json.load(f)
        provider = data["providers"]["dbgpt"]
        assert provider["baseUrl"] == ("http://127.0.0.1:5670/api/v2")
        # key never lands on disk
        assert provider["apiKey"] == "$TEST_HARNESS_KEY"
        assert cfg.build_env()["PI_CODING_AGENT_DIR"]


def test_map_text_delta():
    ev = map_rpc_event(
        {
            "type": "message_update",
            "usage": {"totalTokens": 5},
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 0,
                "delta": "Hello ",
            },
        },
        1,
    )
    assert ev.kind == HarnessEventKind.THINKING_DELTA
    assert ev.text == "Hello "
    assert ev.round == 1
    assert ev.data["stream"] == "text"


def test_map_tool_events():
    start = map_rpc_event(
        {
            "type": "tool_execution_start",
            "toolCallId": "c1",
            "toolName": "bash",
            "args": {"command": "ls"},
        },
        2,
    )
    assert start.kind == HarnessEventKind.TOOL_START
    assert start.tool_name == "bash"
    end = map_rpc_event(
        {
            "type": "tool_execution_end",
            "toolCallId": "c1",
            "toolName": "bash",
            "result": {"content": [{"type": "text", "text": "total 48\n"}]},
            "isError": False,
            "durationMs": 12,
        },
        2,
    )
    assert end.kind == HarnessEventKind.TOOL_END
    assert end.text == "total 48\n"
    assert end.data["is_error"] is False
    assert end.data["duration_ms"] == 12


def test_map_settled_and_noises():
    assert (
        map_rpc_event({"type": "agent_settled", "aborted": False}, 1).kind
        == HarnessEventKind.SETTLED
    )
    # noise records have no neutral representation
    assert (
        map_rpc_event({"type": "queue_update", "steering": [], "followUp": []}, 1)
        is None
    )
    assert map_rpc_event({"type": "session_info_changed"}, 1) is None


def test_assistant_text_from_content_blocks():
    msg = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "hmm"},
            {"type": "text", "text": "ab"},
            {"type": "text", "text": "c"},
        ],
    }
    assert _assistant_text_from_message(msg) == "abc"
    # thinking-only fallback
    assert (
        _assistant_text_from_message(
            {"content": [{"type": "thinking", "thinking": "hmm"}]}
        )
        == "hmm"
    )
    assert _assistant_text_from_message(None) == ""


@pytest.mark.asyncio
async def test_runner_end_to_end_fake_pi():
    with tempfile.TemporaryDirectory() as tmp:
        runner = PiHarnessRunner(_make_config(tmp), conv_id="conv-test-1")
        events = []

        async def on_event(ev):
            events.append(ev)

        try:
            result: HarnessResult = await runner.run("hello", on_event=on_event)
        finally:
            await runner.dispose()
        assert result.error is None
        assert result.aborted is False
        assert result.final_text == "Hello done"
        assert result.rounds == 1
        kinds = [e.kind for e in events]
        assert kinds[0] == HarnessEventKind.TURN_START
        assert HarnessEventKind.TOOL_START in kinds
        assert HarnessEventKind.TOOL_END in kinds
        assert HarnessEventKind.MESSAGE_END in kinds
        assert kinds[-1] == HarnessEventKind.SETTLED


@pytest.mark.asyncio
async def test_runner_reuse_same_child():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        runner = PiHarnessRunner(cfg, conv_id="conv-test-2")
        try:
            await runner.run("one")
            assert runner.alive
            await runner.run("two")
            assert runner.alive
        finally:
            await runner.dispose()
        assert not runner.alive


@pytest.mark.asyncio
async def test_registry_per_conv():
    from dbgpt_app.agent_harness.registry import (
        HarnessRunnerRegistry,
    )

    with tempfile.TemporaryDirectory() as tmp:
        registry = HarnessRunnerRegistry()
        cfg = _make_config(tmp)
        r1 = await registry.get("pi", "conv-a", lambda: cfg)
        r2 = await registry.get("pi", "conv-a", lambda: cfg)
        assert r1 is r2
        r3 = await registry.get("pi", "conv-b", lambda: cfg)
        assert r3 is not r1
        await registry.pop("pi", "conv-b")
        await registry.pop("pi", "conv-a")


@pytest.mark.asyncio
async def test_registry_unknown_engine():
    from dbgpt_app.agent_harness.base import HarnessError
    from dbgpt_app.agent_harness.registry import (
        HarnessRunnerRegistry,
    )

    registry = HarnessRunnerRegistry()
    with pytest.raises(HarnessError):
        await registry.get("dsh", "conv-x", lambda: PiHarnessConfig())
