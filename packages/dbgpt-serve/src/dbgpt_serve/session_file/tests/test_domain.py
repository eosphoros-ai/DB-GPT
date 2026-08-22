"""Tests for session file domain value objects."""

from dataclasses import FrozenInstanceError

import pytest

from dbgpt_serve.session_file.domain import (
    FileScope,
    SessionFileManifest,
    SessionFileSnapshot,
    SessionFileStatus,
)


def test_session_scope_requires_exactly_one_session_or_task():
    with pytest.raises(ValueError):
        FileScope(owner_id="alice")

    with pytest.raises(ValueError):
        FileScope(owner_id="alice", session_id="conv-1", task_id="task-1")


@pytest.mark.parametrize("owner_id", ["", "   "])
def test_session_scope_rejects_blank_owner(owner_id):
    with pytest.raises(ValueError):
        FileScope(owner_id=owner_id, session_id="conv-1")


@pytest.mark.parametrize(
    ("session_id", "task_id"), [("", None), ("   ", None), (None, ""), (None, "   ")]
)
def test_session_scope_rejects_blank_selected_scope(session_id, task_id):
    with pytest.raises(ValueError):
        FileScope(owner_id="alice", session_id=session_id, task_id=task_id)


def test_session_scope_is_immutable():
    scope = FileScope(owner_id="alice", session_id="conv-1")

    with pytest.raises(FrozenInstanceError):
        scope.owner_id = "bob"


def test_public_file_types_are_immutable_and_do_not_expose_storage_location():
    manifest = SessionFileManifest(
        file_id="sf_a",
        name="sales.csv",
        size=42,
        media_type="text/csv",
        kind="table",
        status=SessionFileStatus.READY,
        ordinal=0,
    )
    snapshot = SessionFileSnapshot(
        file_id="sf_a",
        name="sales.csv",
        size=42,
        media_type="text/csv",
        kind="table",
        status=SessionFileStatus.READY,
        ordinal=0,
    )

    assert "storage_uri" not in manifest.__dataclass_fields__
    assert "path" not in manifest.__dataclass_fields__
    assert "storage_uri" not in snapshot.__dataclass_fields__
    assert "path" not in snapshot.__dataclass_fields__
    with pytest.raises(FrozenInstanceError):
        manifest.name = "changed.csv"
    with pytest.raises(FrozenInstanceError):
        snapshot.name = "changed.csv"
