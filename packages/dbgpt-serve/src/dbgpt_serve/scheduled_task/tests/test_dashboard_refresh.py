"""Deterministic tests for dashboard schedules and their safety boundaries."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from dbgpt.storage.metadata import db

from ..api.schemas import (
    CreateTaskRequest,
    DashboardRefreshPayload,
    UpdateTaskRequest,
)
from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401
from ..service.chat_replay_runner import run_scheduled_task
from ..service.dashboard_refresh_runner import DashboardRefreshRunner
from ..service.service import ScheduledTaskService


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


def _payload(**overrides) -> DashboardRefreshPayload:
    values = {
        "dashboard_id": "dashboard-1",
        "filters": {"region": "secret-filter-value"},
        "timeout_seconds": 30,
        "max_attempts": 2,
    }
    values.update(overrides)
    return DashboardRefreshPayload(**values)


def _seed_dashboard_task(*, enabled: bool = True, **payload_overrides) -> str:
    task_id = "schedule-1"
    payload = _payload(**payload_overrides)
    ScheduledTaskDao().create(
        {
            "task_id": task_id,
            "task_name": "Refresh dashboard",
            "task_type": "dashboard_refresh",
            "cron_expression": "0 2 * * *",
            "payload_json": payload.model_dump_json(),
            "enabled": enabled,
            "user_name": "Alice",
            "owner_id": "alice-id",
            "resource_type": "dashboard",
            "resource_id": payload.dashboard_id,
        }
    )
    return task_id


class FakeDashboardService:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [None])
        self.refresh_calls = 0
        self.publish_calls = 0

    def require_permission(self, dashboard_id, owner_id, action):
        assert dashboard_id == "dashboard-1"
        assert owner_id == "alice-id"

    def refresh_dashboard(self, dashboard_id, filters, owner_id):
        self.refresh_calls += 1
        outcome = self.outcomes[min(self.refresh_calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        failed = set(outcome or [])
        return SimpleNamespace(
            refreshed_at=datetime(2026, 8, 11, 12, 0, 0),
            widgets={
                "sales": SimpleNamespace(error=None),
                "profit": SimpleNamespace(
                    error="query failed" if "profit" in failed else None
                ),
            },
        )

    def get_dashboard(self, dashboard_id, owner_id):
        return SimpleNamespace(current_revision=3)

    def publish_dashboard(self, dashboard_id, revision, filters, owner_id):
        self.publish_calls += 1
        return SimpleNamespace(
            published_revision=revision,
            share_path="/dashboard-share/safe-token",
        )


@pytest.mark.asyncio
async def test_dashboard_refresh_records_safe_success_and_publish():
    task_id = _seed_dashboard_task(publish_after_refresh=True)
    service = FakeDashboardService()
    runner = DashboardRefreshRunner(dashboard_service_factory=lambda: service)

    await runner.refresh_dashboard_task(task_id)

    run = ScheduledRunDao().list_by_task_id(task_id)[0]
    result = json.loads(run["result_json"])
    assert run["status"] == "success"
    assert run["attempt_count"] == 1
    assert run["output_resource_id"] == "/dashboard-share/safe-token"
    assert result["filter_keys"] == ["region"]
    assert "secret-filter-value" not in run["result_json"]
    assert result["published"] is True
    assert service.publish_calls == 1


@pytest.mark.asyncio
async def test_dashboard_refresh_retries_then_succeeds():
    task_id = _seed_dashboard_task()
    service = FakeDashboardService([RuntimeError("temporary"), None])
    runner = DashboardRefreshRunner(dashboard_service_factory=lambda: service)

    with patch(
        "dbgpt_serve.scheduled_task.service.dashboard_refresh_runner.asyncio.sleep",
        new=AsyncMock(),
    ):
        await runner.refresh_dashboard_task(task_id)

    run = ScheduledRunDao().list_by_task_id(task_id)[0]
    assert run["status"] == "success"
    assert run["attempt_count"] == 2
    assert service.refresh_calls == 2


@pytest.mark.asyncio
async def test_dashboard_refresh_preserves_partial_result_without_publishing():
    task_id = _seed_dashboard_task(publish_after_refresh=True)
    service = FakeDashboardService([{"profit"}, {"profit"}])
    runner = DashboardRefreshRunner(dashboard_service_factory=lambda: service)

    with patch(
        "dbgpt_serve.scheduled_task.service.dashboard_refresh_runner.asyncio.sleep",
        new=AsyncMock(),
    ):
        await runner.refresh_dashboard_task(task_id)

    run = ScheduledRunDao().list_by_task_id(task_id)[0]
    result = json.loads(run["result_json"])
    assert run["status"] == "partial_success"
    assert result["successful_widget_count"] == 1
    assert result["failed_widget_ids"] == ["profit"]
    assert result["published"] is False
    assert service.publish_calls == 0


@pytest.mark.asyncio
async def test_dashboard_task_service_isolates_owners_and_payload_updates():
    service = ScheduledTaskService()
    created = await service.create_task(
        CreateTaskRequest(
            task_name="Owner-only dashboard refresh",
            task_type="dashboard_refresh",
            cron_expression="0 3 * * *",
            payload=_payload(),
        ),
        user_name="Alice",
        owner_id="alice-id",
    )

    assert await service.get_task(created.task_id, owner_id="bob-id") is None
    assert await service.list_tasks(owner_id="bob-id") == []
    with pytest.raises(ValueError, match="Task not found"):
        await service.update_task(
            created.task_id,
            UpdateTaskRequest(filters={"region": "east"}),
            owner_id="bob-id",
        )

    updated = await service.update_task(
        created.task_id,
        UpdateTaskRequest(
            filters={"region": "east"},
            publish_after_refresh=True,
            max_attempts=3,
        ),
        owner_id="alice-id",
    )
    assert updated.payload.filters == {"region": "east"}
    assert updated.payload.publish_after_refresh is True
    assert updated.payload.max_attempts == 3


def test_persistent_lease_is_exclusive_and_releasable():
    task_id = _seed_dashboard_task()
    dao = ScheduledTaskDao()

    assert dao.try_acquire_lease(task_id, "worker-a", ttl_seconds=120) is True
    assert dao.try_acquire_lease(task_id, "worker-b", ttl_seconds=120) is False
    dao.release_lease(task_id, "worker-a")
    assert dao.try_acquire_lease(task_id, "worker-b", ttl_seconds=120) is True


def test_paused_schedule_only_allows_an_explicit_manual_lease():
    task_id = _seed_dashboard_task(enabled=False)
    dao = ScheduledTaskDao()

    assert dao.try_acquire_lease(task_id, "scheduler", ttl_seconds=120) is False
    assert (
        dao.try_acquire_lease(
            task_id,
            "manual-run",
            ttl_seconds=120,
            require_enabled=False,
        )
        is True
    )


@pytest.mark.asyncio
async def test_paused_dashboard_schedule_can_run_once_without_becoming_enabled():
    task_id = _seed_dashboard_task(enabled=False)
    service = FakeDashboardService()

    with patch(
        "dbgpt_serve.scheduled_task.service.dashboard_refresh_runner.DashboardRefreshRunner._dashboard_service",
        return_value=service,
    ):
        assert await run_scheduled_task(task_id, allow_disabled=True) is True

    task = ScheduledTaskDao().get_one({"task_id": task_id})
    run = ScheduledRunDao().list_by_task_id(task_id)[0]
    assert task["enabled"] is False
    assert run["status"] == "success"
    assert service.refresh_calls == 1
