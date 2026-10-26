"""Snapshots must survive a new conversation object, without duplicate turns."""

import json

import pytest

from dbgpt.core import StorageConversation
from dbgpt.core.interface.storage import InMemoryStorage
from dbgpt_app.openapi.api_v1 import agentic_data_api
from dbgpt_app.openapi.api_v1.react_final import AgentFinalAnswer
from dbgpt_app.openapi.api_v1.react_history import (
    ReactHistoryCheckpoint,
    save_history_view,
)


@pytest.fixture
def conversation_factory():
    conversations, messages = InMemoryStorage(), InMemoryStorage()

    def create():
        return StorageConversation(
            conv_uid="history-recovery-test",
            conv_storage=conversations,
            message_storage=messages,
        )

    return create


def test_running_progress_and_final_replace_one_persisted_view(conversation_factory):
    storage = conversation_factory()
    storage.start_new_round()
    storage.add_user_message("分析年报")
    checkpoint = ReactHistoryCheckpoint()
    checkpoint.bind(storage, lambda status: json.dumps({"execution_status": status}))
    checkpoint.flush(force=True)
    restored = conversation_factory()
    assert [m.type for m in restored.messages] == ["human", "view"]
    assert json.loads(restored.messages[-1].content)["execution_status"] == "running"

    checkpoint.flush(status="interrupted", force=True)
    restored = conversation_factory()
    assert len(restored.messages) == 2
    assert (
        json.loads(restored.messages[-1].content)["execution_status"] == "interrupted"
    )

    agentic_data_api._react_terminal_events(
        storage,
        '{"final_content":"完整回答"}',
        AgentFinalAnswer(content="完整回答"),
        checkpoint,
    )
    checkpoint.flush(status="interrupted", force=True)
    restored = conversation_factory()
    assert len(restored.messages) == 2
    assert json.loads(restored.messages[-1].content) == {"final_content": "完整回答"}


def test_followup_keeps_previous_round_and_uses_a_new_view(conversation_factory):
    storage = conversation_factory()
    storage.start_new_round()
    storage.add_user_message("first")
    save_history_view(storage, "first answer")
    storage = conversation_factory()
    storage.start_new_round()
    storage.add_user_message("second")
    save_history_view(storage, "second progress")
    save_history_view(storage, "second answer")
    restored = conversation_factory()
    assert [m.content for m in restored.messages] == [
        "first",
        "first answer",
        "second",
        "second answer",
    ]
    assert [m.round_index for m in restored.messages] == [1, 1, 2, 2]


def test_progress_writes_are_throttled_but_disconnect_is_always_saved(
    conversation_factory,
):
    storage = conversation_factory()
    storage.start_new_round()
    storage.add_user_message("question")
    clock = [0.0]
    snapshots = []

    def snapshot(status):
        snapshots.append(status)
        return status

    checkpoint = ReactHistoryCheckpoint(clock=lambda: clock[0])
    checkpoint.bind(storage, snapshot)
    checkpoint.flush()
    clock[0] = 1.0
    checkpoint.flush()
    assert snapshots == ["running"]
    clock[0] = 2.1
    checkpoint.flush()
    checkpoint.flush(status="interrupted", force=True)
    assert snapshots == ["running", "running", "interrupted"]
    assert conversation_factory().messages[-1].content == "interrupted"


def test_storage_failure_does_not_fail_stream_or_retry_on_every_token(caplog):
    class BrokenStorage:
        def add_view_message(self, payload):
            raise RuntimeError("storage unavailable")

    checkpoint = ReactHistoryCheckpoint(clock=lambda: 0)
    checkpoint.bind(BrokenStorage(), lambda status: status)
    checkpoint.flush()
    checkpoint.flush()
    assert caplog.text.count("Failed to persist ReAct progress checkpoint") == 1
