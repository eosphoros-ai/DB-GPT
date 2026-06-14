"""Tests for ChatReplayRunner (in-process agent stream).

ChatReplayRunner is the execution core: called by the scheduler at cron time,
it replays a conversation via a direct in-process call to
``_react_agent_stream`` and records the result in the run table.

All tests use an in-memory SQLite via the global ``db`` DatabaseManager.
``_react_agent_stream`` is mocked as an async generator (no HTTP involved).
"""

import asyncio
import json
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from dbgpt.storage.metadata import db

from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao

# Side-effect imports: registering ORM models with SQLAlchemy metadata so
# db.create_all() can discover the tables.
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401
from ..service.chat_replay_runner import ChatReplayRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_PAYLOAD = {
    "version": 1,
    "user_input": "generate daily report",
    "chat_mode": "chat_react_agent",
    "model_name": "proxyllm",
    "select_param": "",
}


def _seed_task(
    task_id: str = "t1",
    enabled: bool = True,
    user_name: str = "alice",
    sys_code: str = "sys-A",
    payload_overrides: dict = None,
) -> None:
    """Insert a task row into the in-memory DB."""
    payload = dict(_DEFAULT_PAYLOAD)
    if payload_overrides:
        payload.update(payload_overrides)
    ScheduledTaskDao().create(
        {
            "task_id": task_id,
            "task_name": "Test Task",
            "description": "test",
            "task_type": "chat_replay",
            "cron_expression": "0 9 * * *",
            "payload_json": json.dumps(payload),
            "enabled": enabled,
            "user_name": user_name,
            "sys_code": sys_code,
        }
    )


def _success_sse_lines() -> List[str]:
    """Return SSE lines simulating a successful chat replay response.

    Uses the real SSE event types from the ReAct agent stream:
    step.start, step.chunk, step.done, final, done.
    """
    return [
        'data: {"type":"step.start","id":"s1","title":"分析数据"}',
        'data: {"type":"step.chunk","id":"s1","output_type":"text","content":"分析中"}',
        'data: {"type":"step.chunk","id":"s1",'
        '"output_type":"code","content":"SELECT 1"}',
        'data: {"type":"step.done","id":"s1","status":"done"}',
        'data: {"type":"final","content":"分析完成:今日订单 100 单"}',
        'data: {"type":"done"}',
    ]


async def _fake_stream(dialogue, sse_lines=None):
    """Async generator that yields SSE lines, simulating _react_agent_stream."""
    if sse_lines is None:
        sse_lines = _success_sse_lines()
    for line in sse_lines:
        yield line


def _make_fake_stream(sse_lines: List[str] = None):
    """Return an async generator function that yields the given SSE lines."""

    async def _stream(dialogue):
        lines = sse_lines if sse_lines is not None else _success_sse_lines()
        for line in lines:
            yield line

    return _stream


def _make_error_stream(exc: Exception):
    """Return an async generator function that raises an exception."""

    async def _stream(dialogue):
        raise exc
        yield  # noqa: F841 — unreachable, makes this an async generator

    return _stream


def _make_hanging_stream():
    """Return an async generator function that hangs forever (for timeout tests)."""

    async def _stream(dialogue):
        await asyncio.sleep(60)
        yield 'data: {"type":"done"}'

    return _stream


# Patch targets — runner uses lazy import inside _run_agent_stream
_PATCH_REACT = "dbgpt_app.openapi.api_v1.agentic_data_api._react_agent_stream"
_PATCH_CONV_VO = "dbgpt_app.openapi.api_view_model.ConversationVo"


def _make_mock_conv_vo():
    """Create a mock ConversationVo class that accepts any kwargs."""
    mock_cls = MagicMock()
    mock_cls.side_effect = lambda **kwargs: MagicMock(**kwargs)
    return mock_cls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Initialize an in-memory SQLite and create all tables before each test."""
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest.fixture
def runner() -> ChatReplayRunner:
    """Create a ChatReplayRunner with test configuration."""
    return ChatReplayRunner(request_timeout=5.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_writes_running_then_success(runner: ChatReplayRunner):
    """Runner should create a run with status='success' after consuming SSE.

    The result_summary should contain the concatenated text content
    and/or mention the artifact.
    """
    _seed_task()

    with (
        patch(_PATCH_REACT, new=_make_fake_stream()),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "success"
    assert run["output_conv_uid"] is not None
    assert run["output_conv_uid"] != ""
    # result_summary should contain final event content + artifact marker
    summary = run["result_summary"] or ""
    assert "分析完成" in summary, (
        f"summary should contain final event content, got '{summary}'"
    )
    assert "[artifacts: 1]" in summary, (
        f"summary should contain artifact count (1 code chunk), got '{summary}'"
    )


@pytest.mark.asyncio
async def test_runner_writes_failed_on_exception(runner: ChatReplayRunner):
    """Runner should write status='failed' when _react_agent_stream raises.

    The error_message should be populated, and output_conv_uid should
    still be written (for debugging purposes).
    """
    _seed_task()

    with (
        patch(_PATCH_REACT, new=_make_error_stream(RuntimeError("agent crashed"))),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "failed"
    assert run["error_message"] is not None
    assert run["error_message"] != ""
    # output_conv_uid should still be written even on failure
    assert run["output_conv_uid"] is not None


@pytest.mark.asyncio
async def test_runner_writes_timeout():
    """Runner should write status='timeout' when stream hangs too long.

    Must never raise an exception to the scheduler.
    """
    _seed_task()

    # Use a very short timeout to trigger timeout quickly
    runner = ChatReplayRunner(request_timeout=0.5)

    with (
        patch(_PATCH_REACT, new=_make_hanging_stream()),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        # Must not raise — runner catches all exceptions
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "timeout"
    assert run["error_message"] is not None
    assert "timeout" in run["error_message"].lower() or (
        "exceeded" in run["error_message"].lower()
    )


@pytest.mark.asyncio
async def test_runner_writes_failed_when_task_disabled(runner: ChatReplayRunner):
    """Runner should write status='failed' without calling stream when disabled."""
    _seed_task(enabled=False)

    mock_stream = MagicMock()

    with (
        patch(_PATCH_REACT, new=mock_stream),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")
        # The stream function should not have been called
        mock_stream.assert_not_called()

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "failed"
    assert run["error_message"] is not None
    assert "disabled" in run["error_message"].lower()


@pytest.mark.asyncio
async def test_runner_writes_failed_when_task_not_found(runner: ChatReplayRunner):
    """Runner should write status='failed' when task_id doesn't exist in DB."""
    # Do NOT seed any task — "nonexistent" won't be found
    with (
        patch(_PATCH_REACT, new=_make_fake_stream()),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("nonexistent")

    runs = ScheduledRunDao().list_by_task_id("nonexistent", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "failed"
    assert run["error_message"] is not None
    assert "not found" in run["error_message"].lower()


@pytest.mark.asyncio
async def test_runner_uses_fresh_conv_uid_per_call(runner: ChatReplayRunner):
    """Each replay call should generate a unique output_conv_uid."""
    _seed_task()

    with (
        patch(_PATCH_REACT, new=_make_fake_stream()),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    # Second call — fresh stream
    with (
        patch(_PATCH_REACT, new=_make_fake_stream()),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 2

    conv_uids = {r["output_conv_uid"] for r in runs}
    assert len(conv_uids) == 2, "Each call must produce a distinct conv_uid"


@pytest.mark.asyncio
async def test_runner_summary_truncates_long_text(runner: ChatReplayRunner):
    """Runner should truncate result_summary to at most 1024 characters."""
    _seed_task()

    # Create SSE lines with a very long final content (5000 chars)
    long_text = "A" * 5000
    sse_lines = [
        f'data: {{"type":"final","content":"{long_text}"}}',
    ]

    with (
        patch(_PATCH_REACT, new=_make_fake_stream(sse_lines)),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "success"
    assert run["result_summary"] is not None
    assert len(run["result_summary"]) <= 1024, (
        f"result_summary should be truncated to <= 1024 chars, "
        f"got {len(run['result_summary'])}"
    )


@pytest.mark.asyncio
async def test_runner_handles_sse_parse_errors_gracefully(runner: ChatReplayRunner):
    """Runner should skip malformed SSE lines and still succeed.

    A bad JSON line should not crash the runner; subsequent valid lines
    should still be processed.
    """
    _seed_task()

    sse_lines = [
        "data: {not valid json!!!}",
        'data: {"type":"final","content":"ok"}',
    ]

    with (
        patch(_PATCH_REACT, new=_make_fake_stream(sse_lines)),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "success"
    summary = run["result_summary"] or ""
    assert "ok" in summary, (
        f"Valid SSE line should be processed despite earlier parse error, "
        f"got summary='{summary}'"
    )


@pytest.mark.asyncio
async def test_runner_collects_final_event_as_summary(runner: ChatReplayRunner):
    """Runner should use the 'final' event content as result_summary.

    This test anchors the real SSE contract: type=='final' is the primary
    source for result_summary, preventing regressions to the old
    (incorrect) type=='text' parsing.
    """
    _seed_task()

    sse_lines = [
        'data: {"type":"step.start","id":"s1","title":"查询"}',
        'data: {"type":"step.chunk","id":"s1","output_type":"text","content":"查询中"}',
        'data: {"type":"step.done","id":"s1","status":"done"}',
        'data: {"type":"final","content":"最终报告内容"}',
        'data: {"type":"done"}',
    ]

    with (
        patch(_PATCH_REACT, new=_make_fake_stream(sse_lines)),
        patch(_PATCH_CONV_VO, new=_make_mock_conv_vo()),
    ):
        await runner.replay_chat_task("t1")

    runs = ScheduledRunDao().list_by_task_id("t1", limit=5, offset=0)
    assert len(runs) == 1

    run = runs[0]
    assert run["status"] == "success"
    summary = run["result_summary"] or ""
    # Summary must contain the final event content (not step.chunk text)
    assert "最终报告内容" in summary, (
        f"summary should come from 'final' event, got '{summary}'"
    )
    # Step text should NOT appear when final event is present
    assert "查询中" not in summary, (
        f"summary should prefer 'final' over step.chunk text, got '{summary}'"
    )
