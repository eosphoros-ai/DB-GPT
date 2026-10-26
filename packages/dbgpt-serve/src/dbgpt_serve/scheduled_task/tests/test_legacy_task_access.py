"""Preserve the upstream shared contract only for ownerless legacy chat tasks."""

import pytest

from dbgpt.storage.metadata import db

from ..dao.task_dao import ScheduledTaskDao


@pytest.fixture
def tasks():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    dao = ScheduledTaskDao()
    for task_id, task_type, owner in (
        ("legacy-chat", "chat_replay", None),
        ("private-chat", "chat_replay", "alice-id"),
        ("dashboard", "dashboard_refresh", "alice-id"),
        ("ownerless-dashboard", "dashboard_refresh", None),
    ):
        dao.create(
            {
                "task_id": task_id,
                "task_name": task_id,
                "task_type": task_type,
                "cron_expression": "0 0 * * *",
                "payload_json": "{}",
                "enabled": True,
                "owner_id": owner,
                "user_name": "Alice display name",
            }
        )
    return dao


def test_legacy_display_name_is_not_treated_as_a_user_id(tasks):
    assert tasks.get_owned("legacy-chat", "001")["user_name"] == "Alice display name"
    assert {row["task_id"] for row in tasks.list_owned("001")} == {"legacy-chat"}


def test_new_and_dashboard_tasks_keep_owner_isolation(tasks):
    assert tasks.get_owned("private-chat", "bob-id") is None
    assert tasks.get_owned("dashboard", "bob-id") is None
    assert tasks.get_owned("ownerless-dashboard", "bob-id") is None
    assert tasks.get_owned("private-chat", "alice-id") is not None
    assert tasks.get_owned("dashboard", "alice-id") is not None
