"""Integration tests: real TaskScheduler (MemoryJobStore) + Service.

These tests use a **real** TaskScheduler backed by MemoryJobStore (no mocks)
together with the ScheduledTaskService to verify end-to-end behaviour:
DB rows and scheduler jobs stay in sync, and the scheduler actually fires
the runner callable at the scheduled time.
"""

import asyncio
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from dbgpt.storage.metadata import db
from dbgpt.util.scheduler.task_scheduler import TaskScheduler

from ..api.schemas import ChatReplayPayload, CreateTaskRequest

# Side-effect imports: register ORM models with SQLAlchemy metadata so
# db.create_all() discovers the tables.
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401
from ..service.service import ScheduledTaskService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(**overrides) -> ChatReplayPayload:
    defaults = {
        "version": 1,
        "user_input": "integration test question",
        "chat_mode": "chat_react_agent",
        "model_name": "chatgpt_proxyllm",
        "select_param": "",
    }
    defaults.update(overrides)
    return ChatReplayPayload(**defaults)


def _make_create_request(**overrides) -> CreateTaskRequest:
    defaults = {
        "task_name": "Integration Test Task",
        "description": "Created by integration test",
        "cron_expression": "0 9 * * *",
        "payload": _make_payload(),
    }
    defaults.update(overrides)
    return CreateTaskRequest(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize in-memory SQLite and create all tables before each test."""
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest_asyncio.fixture
async def scheduler():
    """Create a real TaskScheduler with MemoryJobStore, start it, and
    shut down + reset singleton after each test.
    """
    sched = TaskScheduler(jobstore_url="sqlite:///:memory:")
    await sched.start()
    yield sched
    await sched.shutdown()


# ===========================================================================
# Test 1: create_task registers job in real scheduler
# ===========================================================================


@pytest.mark.asyncio
async def test_create_then_scheduler_has_job(scheduler):
    """After create_task, the real scheduler must contain a job with the
    matching task_id and a non-None next_run_time.
    """
    fired = []

    async def runner(task_id: str):
        fired.append(task_id)

    service = ScheduledTaskService(
        scheduler=scheduler,
        runner_callable=runner,
    )

    request = _make_create_request(cron_expression="0 9 * * *")
    result = await service.create_task(request, user_name="integ_user")

    task_id = result.task_id
    assert task_id

    # Verify the job really exists in the scheduler
    job_info = scheduler.get_job(task_id)
    assert job_info is not None, "Job should be registered in real scheduler"
    assert job_info["job_id"] == task_id
    assert job_info["next_run_time"] is not None


# ===========================================================================
# Test 2: full lifecycle — create, list, get, toggle, delete
# ===========================================================================


@pytest.mark.asyncio
async def test_full_lifecycle(scheduler):
    """End-to-end lifecycle: create -> list -> get -> toggle -> delete.
    Verifies DB and real scheduler stay in sync throughout.
    """
    fired = []

    async def runner(task_id: str):
        fired.append(task_id)

    service = ScheduledTaskService(
        scheduler=scheduler,
        runner_callable=runner,
    )

    # 1. Create
    request = _make_create_request()
    created = await service.create_task(request)
    task_id = created.task_id

    # 2. List — should have exactly 1 task
    tasks = await service.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_id == task_id

    # 3. Get — should return the task with next_run_time from scheduler
    fetched = await service.get_task(task_id)
    assert fetched is not None
    assert fetched.task_id == task_id
    assert fetched.next_run_time is not None

    # 4. Toggle disabled — scheduler should pause the job
    toggled = await service.toggle_task(task_id, enabled=False)
    assert toggled.enabled is False
    # After pause, get_job still returns the job but next_run_time is None
    paused_job = scheduler.get_job(task_id)
    assert paused_job is not None
    assert paused_job["next_run_time"] is None

    # 5. Delete — both DB row and scheduler job removed
    await service.delete_task(task_id)
    tasks_after = await service.list_tasks()
    assert len(tasks_after) == 0
    assert scheduler.get_job(task_id) is None


# ===========================================================================
# Test 3: scheduler actually fires the runner callable
# ===========================================================================


@pytest.mark.asyncio
async def test_scheduler_actually_fires_runner(scheduler):
    """The critical integration test: verify the real scheduler actually
    invokes the runner callable at the scheduled time.

    Uses a 6-field cron (with seconds) targeting ~2 seconds from now.
    Pattern taken from TaskScheduler's own test_job_execution_with_kwargs.
    """
    fired = []

    async def runner(task_id: str):
        fired.append(task_id)

    service = ScheduledTaskService(
        scheduler=scheduler,
        runner_callable=runner,
    )

    # Build a 6-field cron that fires ~2 seconds from now
    now = datetime.now()
    target = now + timedelta(seconds=2)
    cron_expr = f"{target.second} {target.minute} {target.hour} * * *"

    request = _make_create_request(cron_expression=cron_expr)
    created = await service.create_task(request)
    task_id = created.task_id

    # Wait for the scheduler to fire
    await asyncio.sleep(4)

    assert len(fired) >= 1, (
        f"Runner should have been called at least once, but fired={fired}"
    )
    assert task_id in fired, (
        f"Runner should have been called with task_id={task_id}, got {fired}"
    )


# ===========================================================================
# Test 4: delete stops future runs
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_stops_future_runs(scheduler):
    """After deleting a task, the scheduler must not fire the runner again.

    Creates a task with a near-future cron, deletes it immediately,
    then waits past the scheduled time — runner must NOT be called.
    """
    fired = []

    async def runner(task_id: str):
        fired.append(task_id)

    service = ScheduledTaskService(
        scheduler=scheduler,
        runner_callable=runner,
    )

    # Build a 6-field cron that would fire ~3 seconds from now
    now = datetime.now()
    target = now + timedelta(seconds=3)
    cron_expr = f"{target.second} {target.minute} {target.hour} * * *"

    request = _make_create_request(cron_expression=cron_expr)
    created = await service.create_task(request)
    task_id = created.task_id

    # Delete immediately — before the scheduled time
    await service.delete_task(task_id)

    # Wait past the would-be trigger time
    await asyncio.sleep(5)

    assert len(fired) == 0, (
        f"Runner should NOT have been called after delete, but fired={fired}"
    )
