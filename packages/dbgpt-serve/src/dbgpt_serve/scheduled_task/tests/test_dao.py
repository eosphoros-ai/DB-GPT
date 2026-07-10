"""TDD tests for ScheduledTaskDao and ScheduledRunDao.

These tests define the DAO contract that Task 3.6 / 3.7 will implement.
All tests use an in-memory SQLite via the global ``db`` DatabaseManager,
following the same pattern as ``connector/tests/test_service.py``.

DAO classes under test (not yet implemented — expect ImportError on collect):
- ``ScheduledTaskDao``  → packages/dbgpt-serve/.../scheduled_task/dao/task_dao.py
- ``ScheduledRunDao``   → packages/dbgpt-serve/.../scheduled_task/dao/run_dao.py
"""

import json
import uuid
from datetime import datetime, timedelta

import pytest

from dbgpt.storage.metadata import db

from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao

# Side-effect imports: register ORM models with SQLAlchemy metadata so
# db.create_all() can discover the tables. Not referenced directly.
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401

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
def task_dao() -> ScheduledTaskDao:
    """Provide a fresh ScheduledTaskDao instance (uses global ``db``)."""
    return ScheduledTaskDao()


@pytest.fixture
def run_dao() -> ScheduledRunDao:
    """Provide a fresh ScheduledRunDao instance (uses global ``db``)."""
    return ScheduledRunDao()


def _make_task_dict(**overrides) -> dict:
    """Helper: build a valid task request dict with sensible defaults."""
    base = {
        "task_id": str(uuid.uuid4()),
        "task_name": "Nightly Sales Report",
        "description": "Replay the sales-summary conversation every night",
        "task_type": "chat_replay",
        "cron_expression": "0 2 * * *",
        "payload_json": json.dumps(
            {"version": 1, "conv_uid": "conv-001", "user_input": "生成销售报告"}
        ),
        "enabled": True,
        "user_name": "test_user",
        "sys_code": "dbgpt",
    }
    base.update(overrides)
    return base


def _make_run_dict(**overrides) -> dict:
    """Helper: build a valid run request dict with sensible defaults."""
    base = {
        "run_id": str(uuid.uuid4()),
        "task_id": "task-placeholder",
        "started_at": datetime.now(),
        "status": "running",
    }
    base.update(overrides)
    return base


# ===========================================================================
# ScheduledTaskDao tests (5)
# ===========================================================================


class TestScheduledTaskDao:
    """Contract tests for ScheduledTaskDao (to be implemented in Task 3.6)."""

    def test_task_save_and_get(self, task_dao: ScheduledTaskDao):
        """Save a task and retrieve it by task_id; all fields must match."""
        task_id = str(uuid.uuid4())
        data = _make_task_dict(task_id=task_id, task_name="Daily Digest")

        # create returns a response dict
        result = task_dao.create(data)
        assert result is not None
        assert result["task_id"] == task_id
        assert result["task_name"] == "Daily Digest"

        # get_one by task_id
        fetched = task_dao.get_one({"task_id": task_id})
        assert fetched is not None
        assert fetched["task_id"] == task_id
        assert fetched["task_name"] == "Daily Digest"
        assert fetched["task_type"] == "chat_replay"
        assert fetched["cron_expression"] == "0 2 * * *"
        assert fetched["enabled"] is True
        assert fetched["user_name"] == "test_user"

    def test_task_update(self, task_dao: ScheduledTaskDao):
        """Save, update task_name, then verify the change persisted."""
        task_id = str(uuid.uuid4())
        data = _make_task_dict(task_id=task_id, task_name="Old Name")
        task_dao.create(data)

        # Update via BaseDao.update(query_request, update_request)
        updated = task_dao.update(
            query_request={"task_id": task_id},
            update_request={"task_name": "New Name"},
        )
        assert updated is not None
        assert updated["task_name"] == "New Name"

        # Re-fetch to confirm persistence
        fetched = task_dao.get_one({"task_id": task_id})
        assert fetched is not None
        assert fetched["task_name"] == "New Name"

    def test_task_delete(self, task_dao: ScheduledTaskDao):
        """Save then delete; get_one should return None afterwards."""
        task_id = str(uuid.uuid4())
        data = _make_task_dict(task_id=task_id)
        task_dao.create(data)

        # Confirm it exists
        assert task_dao.get_one({"task_id": task_id}) is not None

        # Delete
        task_dao.delete({"task_id": task_id})

        # Should be gone
        assert task_dao.get_one({"task_id": task_id}) is None

    def test_task_list_all(self, task_dao: ScheduledTaskDao):
        """Save 2 tasks, get_list with empty query returns both."""
        task_dao.create(_make_task_dict(task_name="Task A"))
        task_dao.create(_make_task_dict(task_name="Task B"))

        all_tasks = task_dao.get_list({})
        assert len(all_tasks) == 2
        names = {t["task_name"] for t in all_tasks}
        assert names == {"Task A", "Task B"}

    def test_task_list_enabled(self, task_dao: ScheduledTaskDao):
        """Save 1 enabled + 1 disabled; list_enabled returns only enabled."""
        task_dao.create(_make_task_dict(task_name="Enabled", enabled=True))
        task_dao.create(_make_task_dict(task_name="Disabled", enabled=False))

        enabled_tasks = task_dao.list_enabled()
        assert len(enabled_tasks) == 1
        assert enabled_tasks[0]["task_name"] == "Enabled"
        assert enabled_tasks[0]["enabled"] is True


# ===========================================================================
# ScheduledRunDao tests (4)
# ===========================================================================


class TestScheduledRunDao:
    """Contract tests for ScheduledRunDao (to be implemented in Task 3.7)."""

    def test_run_insert_and_get(self, run_dao: ScheduledRunDao):
        """Insert a run record, retrieve by run_id, verify fields."""
        run_id = str(uuid.uuid4())
        task_id = "task-abc"
        now = datetime.now()

        data = _make_run_dict(
            run_id=run_id, task_id=task_id, started_at=now, status="running"
        )
        result = run_dao.create(data)
        assert result is not None
        assert result["run_id"] == run_id
        assert result["task_id"] == task_id
        assert result["status"] == "running"

        fetched = run_dao.get_one({"run_id": run_id})
        assert fetched is not None
        assert fetched["run_id"] == run_id
        assert fetched["task_id"] == task_id
        assert fetched["status"] == "running"

    def test_run_update_status(self, run_dao: ScheduledRunDao):
        """Insert running, update to success with output_conv_uid."""
        run_id = str(uuid.uuid4())
        data = _make_run_dict(run_id=run_id, task_id="task-xyz", status="running")
        run_dao.create(data)

        updated = run_dao.update(
            query_request={"run_id": run_id},
            update_request={
                "status": "success",
                "finished_at": datetime.now(),
                "result_summary": "Generated report OK",
                "output_conv_uid": "conv-out-001",
            },
        )
        assert updated is not None
        assert updated["status"] == "success"
        assert updated["output_conv_uid"] == "conv-out-001"

        fetched = run_dao.get_one({"run_id": run_id})
        assert fetched is not None
        assert fetched["status"] == "success"
        assert fetched["result_summary"] == "Generated report OK"
        assert fetched["output_conv_uid"] == "conv-out-001"

    def test_run_list_by_task_id_desc(self, run_dao: ScheduledRunDao):
        """Insert 3 runs with different started_at; list_by_task_id returns
        them in descending order of started_at."""
        task_id = "task-order-test"
        base_time = datetime(2026, 5, 1, 10, 0, 0)

        for i in range(3):
            run_dao.create(
                _make_run_dict(
                    task_id=task_id,
                    started_at=base_time + timedelta(hours=i),
                    status="success",
                )
            )

        runs = run_dao.list_by_task_id(task_id)
        assert len(runs) == 3
        # Descending: newest first
        for i in range(len(runs) - 1):
            assert runs[i]["started_at"] >= runs[i + 1]["started_at"]

    def test_run_list_respects_limit(self, run_dao: ScheduledRunDao):
        """Insert 5 runs, list_by_task_id(limit=2) returns exactly 2."""
        task_id = "task-limit-test"
        base_time = datetime(2026, 6, 1, 8, 0, 0)

        for i in range(5):
            run_dao.create(
                _make_run_dict(
                    task_id=task_id,
                    started_at=base_time + timedelta(minutes=i),
                    status="success",
                )
            )

        runs = run_dao.list_by_task_id(task_id, limit=2)
        assert len(runs) == 2
