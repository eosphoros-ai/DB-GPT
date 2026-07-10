"""TDD tests for ScheduledTaskService.

These tests define the Service-layer contract that Task 4.3 will implement.
Core invariant: **DB row + scheduler job must be kept in sync** (dual-write).
If scheduler.add_job fails after DB write, the DB row must be rolled back.

All tests use an in-memory SQLite via the global ``db`` DatabaseManager,
following the same pattern as ``connector/tests/test_service.py`` and
``scheduled_task/tests/test_dao.py``.

Service under test (not yet implemented -- expect ImportError on collect):
- ``ScheduledTaskService`` -> .../scheduled_task/service/service.py
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from dbgpt.storage.metadata import db

from ..api.schemas import (
    ChatReplayPayload,
    CreateTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)
from ..dao.run_dao import ScheduledRunDao

# Side-effect imports: registering ORM models with SQLAlchemy metadata so
# db.create_all() can discover the tables. Not referenced directly.
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401
from ..service.service import ScheduledTaskService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(**overrides) -> ChatReplayPayload:
    """Build a valid ChatReplayPayload with sensible defaults."""
    defaults = {
        "version": 1,
        "user_input": "生成销售日报",
        "chat_mode": "chat_react_agent",
        "model_name": "chatgpt_proxyllm",
        "select_param": "",
    }
    defaults.update(overrides)
    return ChatReplayPayload(**defaults)


def _make_create_request(**overrides) -> CreateTaskRequest:
    """Build a valid CreateTaskRequest with sensible defaults."""
    defaults = {
        "task_name": "Daily Sales Report",
        "description": "Replay the sales conversation every morning",
        "cron_expression": "0 9 * * *",
        "payload": _make_payload(),
    }
    defaults.update(overrides)
    return CreateTaskRequest(**defaults)


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
def scheduler_mock() -> MagicMock:
    """Mock for TaskScheduler.

    - add_job / remove_job are AsyncMock (the real ones are async).
    - pause_job / resume_job / get_job / list_jobs are sync MagicMock.
    - get_job returns None by default (no pre-existing jobs).
    - list_jobs returns [] by default.
    """
    mock = MagicMock()
    mock.add_job = AsyncMock()
    mock.remove_job = AsyncMock()
    mock.pause_job = MagicMock()
    mock.resume_job = MagicMock()
    mock.get_job = MagicMock(return_value=None)
    mock.list_jobs = MagicMock(return_value=[])
    return mock


@pytest.fixture
def runner_mock() -> MagicMock:
    """Mock callable used as runner_callable for the service."""
    return MagicMock()


@pytest.fixture
def resource_validator_mock() -> MagicMock:
    """Mock resource validator. Returns None (= validation passes) by default."""
    return MagicMock(return_value=None)


@pytest.fixture
def service(
    scheduler_mock: MagicMock,
    runner_mock: MagicMock,
    resource_validator_mock: MagicMock,
) -> ScheduledTaskService:
    """Create a ScheduledTaskService with all dependencies mocked/injected."""
    return ScheduledTaskService(
        scheduler=scheduler_mock,
        runner_callable=runner_mock,
        resource_validator=resource_validator_mock,
    )


# ===========================================================================
# Test 1: create_task writes DB and adds scheduler job
# ===========================================================================


@pytest.mark.asyncio
async def test_create_writes_db_and_adds_job(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """create_task should:
    1. Return a TaskResponse with a non-empty task_id
    2. Persist a row in the DB (verifiable via get_task)
    3. Call scheduler.add_job exactly once with job_id == task_id
    """
    request = _make_create_request()
    result = await service.create_task(request, user_name="test_user")

    # Returns TaskResponse with valid task_id
    assert isinstance(result, TaskResponse)
    assert result.task_id
    assert result.task_name == "Daily Sales Report"
    assert result.enabled is True

    # scheduler.add_job called once, job_id matches task_id
    scheduler_mock.add_job.assert_awaited_once()
    call_kwargs = scheduler_mock.add_job.call_args
    assert call_kwargs[1].get("job_id") or call_kwargs[0][0] == result.task_id

    # DB row exists
    fetched = await service.get_task(result.task_id)
    assert fetched is not None
    assert fetched.task_id == result.task_id


# ===========================================================================
# Test 2: create_task validates cron expression
# ===========================================================================


@pytest.mark.asyncio
async def test_create_validates_cron(
    service: ScheduledTaskService,
):
    """create_task with an invalid cron expression should raise ValueError
    before writing to DB or calling scheduler.add_job.
    """
    request = _make_create_request(cron_expression="not a cron")
    with pytest.raises(ValueError):
        await service.create_task(request)


# ===========================================================================
# Test 3: create_task rolls back DB when scheduler.add_job fails
# ===========================================================================


@pytest.mark.asyncio
async def test_create_rolls_back_db_when_add_job_fails(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """If scheduler.add_job raises RuntimeError after DB write:
    1. The exception propagates to the caller
    2. The DB row must be deleted (no residual data)
    """
    scheduler_mock.add_job = AsyncMock(
        side_effect=RuntimeError("scheduler unavailable")
    )

    request = _make_create_request()
    with pytest.raises(RuntimeError, match="scheduler unavailable"):
        await service.create_task(request)

    # DB must have no residual rows
    all_tasks = await service.list_tasks()
    assert len(all_tasks) == 0


# ===========================================================================
# Test 4: create_task validates referenced resources via validator
# ===========================================================================


@pytest.mark.asyncio
async def test_create_validates_referenced_resources(
    service: ScheduledTaskService,
    resource_validator_mock: MagicMock,
):
    """If resource_validator raises ValueError, create_task should propagate
    the error without writing to DB.
    """
    resource_validator_mock.side_effect = ValueError("skill not found")

    request = _make_create_request()
    with pytest.raises(ValueError, match="skill not found"):
        await service.create_task(request)

    # No DB write should have happened
    all_tasks = await service.list_tasks()
    assert len(all_tasks) == 0


# ===========================================================================
# Test 5: update_task with new cron replaces scheduler job
# ===========================================================================


@pytest.mark.asyncio
async def test_update_cron_replaces_existing_job(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """When updating cron_expression, the service should call
    scheduler.add_job again (to replace/update the job trigger).
    """
    request = _make_create_request(cron_expression="0 9 * * *")
    created = await service.create_task(request)
    assert scheduler_mock.add_job.await_count == 1

    # Update cron
    update_req = UpdateTaskRequest(cron_expression="30 18 * * *")
    updated = await service.update_task(created.task_id, update_req)

    assert updated.task_id == created.task_id
    # add_job should have been called again (for replace/reschedule)
    assert (
        scheduler_mock.add_job.await_count >= 2
        or scheduler_mock.remove_job.await_count >= 1
    )


# ===========================================================================
# Test 6: toggle_task pauses / resumes scheduler job
# ===========================================================================


@pytest.mark.asyncio
async def test_toggle_pause_pauses_scheduler(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """toggle_task(enabled=False) should call scheduler.pause_job;
    toggle_task(enabled=True) should call scheduler.resume_job.
    """
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    # Disable -> pause
    result_off = await service.toggle_task(task_id, enabled=False)
    assert result_off.enabled is False
    scheduler_mock.pause_job.assert_called_once_with(task_id)

    # Enable -> resume
    result_on = await service.toggle_task(task_id, enabled=True)
    assert result_on.enabled is True
    scheduler_mock.resume_job.assert_called_once_with(task_id)


# ===========================================================================
# Test 7: delete_task removes both DB row and scheduler job
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_removes_db_and_job(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """delete_task should:
    1. Call scheduler.remove_job with the task_id
    2. Delete the DB row (get_task returns None afterwards)
    """
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    await service.delete_task(task_id)

    scheduler_mock.remove_job.assert_awaited_once_with(task_id)

    fetched = await service.get_task(task_id)
    assert fetched is None


# ===========================================================================
# Test 8: list_tasks returns all created tasks
# ===========================================================================


@pytest.mark.asyncio
async def test_list_tasks(
    service: ScheduledTaskService,
):
    """Create 2 tasks, list_tasks should return both."""
    await service.create_task(_make_create_request(task_name="Task Alpha"))
    await service.create_task(_make_create_request(task_name="Task Beta"))

    tasks = await service.list_tasks()
    assert len(tasks) == 2
    names = {t.task_name for t in tasks}
    assert names == {"Task Alpha", "Task Beta"}


# ===========================================================================
# Test 9: list_runs returns runs in descending order
# ===========================================================================


@pytest.mark.asyncio
async def test_list_runs_orders_desc(
    service: ScheduledTaskService,
):
    """Insert run records directly via ScheduledRunDao, then verify
    service.list_runs returns them in descending started_at order.

    Note: Run records are normally created by the Runner, not the Service.
    We insert them directly via DAO to test the read path.
    """
    # First create a task so we have a valid task_id
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    # Insert 3 runs directly via DAO with different started_at
    run_dao = ScheduledRunDao()
    base_time = datetime(2026, 6, 1, 8, 0, 0)
    for i in range(3):
        run_dao.create(
            {
                "run_id": str(uuid.uuid4()),
                "task_id": task_id,
                "started_at": base_time + timedelta(hours=i),
                "status": "success",
            }
        )

    runs = await service.list_runs(task_id)
    assert len(runs) == 3
    # Verify descending order by started_at
    for i in range(len(runs) - 1):
        assert runs[i].started_at >= runs[i + 1].started_at


# ===========================================================================
# Test 10: get_task includes next_run_time from scheduler
# ===========================================================================


@pytest.mark.asyncio
async def test_get_task_includes_next_run_time(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """get_task should merge next_run_time from scheduler.get_job
    into the TaskResponse.
    """
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    # Configure scheduler mock to return next_run_time
    expected_next = "2026-06-01 09:00:00"
    scheduler_mock.get_job.return_value = {
        "job_id": task_id,
        "next_run_time": expected_next,
        "name": "test_job",
    }

    result = await service.get_task(task_id)
    assert result is not None
    assert result.next_run_time == expected_next


# ===========================================================================
# Test 11: delete_task succeeds when scheduler job is missing
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_task_when_job_missing(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """When scheduler.remove_job raises ValueError (job lost after restart),
    delete_task should NOT propagate the error and should still delete the
    DB row (no zombie tasks).
    """
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    # Simulate scheduler restart: remove_job raises ValueError
    scheduler_mock.remove_job = AsyncMock(side_effect=ValueError("Job not found"))

    # Should NOT raise
    await service.delete_task(task_id)

    # DB row must be gone
    fetched = await service.get_task(task_id)
    assert fetched is None


# ===========================================================================
# Test 12: toggle_task succeeds when scheduler job is missing
# ===========================================================================


@pytest.mark.asyncio
async def test_toggle_task_when_job_missing(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """When scheduler.pause_job raises ValueError (job lost after restart),
    toggle_task should NOT propagate the error. The DB enabled flag must
    still be updated and reflected in the returned TaskResponse.
    """
    created = await service.create_task(_make_create_request())
    task_id = created.task_id

    # Simulate scheduler restart: pause_job raises ValueError
    scheduler_mock.pause_job = MagicMock(side_effect=ValueError("Job not found"))

    # Should NOT raise
    result = await service.toggle_task(task_id, enabled=False)

    # DB enabled must be updated
    assert result.enabled is False

    # Verify DB state independently
    fetched = await service.get_task(task_id)
    assert fetched is not None
    assert fetched.enabled is False


# ===========================================================================
# Test 13: update_task cron change rolls back when add_job fails
# ===========================================================================


@pytest.mark.asyncio
async def test_update_cron_rollback_when_add_fails(
    service: ScheduledTaskService,
    scheduler_mock: MagicMock,
):
    """When updating cron_expression, if scheduler.add_job fails on the
    second call (first call is create_task), the DB cron must remain
    unchanged (scheduler-first strategy: DB is never written on failure).
    """
    original_cron = "0 9 * * *"
    created = await service.create_task(
        _make_create_request(cron_expression=original_cron)
    )
    task_id = created.task_id

    # After create succeeds, make add_job fail for the update call
    scheduler_mock.add_job = AsyncMock(
        side_effect=RuntimeError("scheduler add_job failed")
    )

    # Attempt to update cron — should raise
    new_cron = "30 18 * * *"
    update_req = UpdateTaskRequest(cron_expression=new_cron)
    with pytest.raises(RuntimeError, match="scheduler add_job failed"):
        await service.update_task(task_id, update_req)

    # DB cron must still be the original value (no DB write happened)
    fetched = await service.get_task(task_id)
    assert fetched is not None
    assert fetched.cron_expression == original_cron
