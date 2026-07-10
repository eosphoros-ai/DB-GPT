"""Unit tests for TaskScheduler."""

import asyncio
from datetime import datetime, timedelta
from typing import List

import pytest
import pytest_asyncio

from dbgpt.util.scheduler.task_scheduler import TaskScheduler


@pytest.fixture
def in_memory_db_url():
    """In-memory SQLite URL for testing."""
    return "sqlite:///:memory:"


@pytest_asyncio.fixture
async def scheduler(in_memory_db_url):
    """Create a TaskScheduler instance with in-memory jobstore."""
    sched = TaskScheduler(jobstore_url=in_memory_db_url)
    await sched.start()
    yield sched
    await sched.shutdown()


@pytest.mark.asyncio
async def test_scheduler_singleton():
    """Test TaskScheduler is a singleton."""
    s1 = TaskScheduler(jobstore_url="sqlite:///:memory:")
    s2 = TaskScheduler(jobstore_url="sqlite:///:memory:")
    assert s1 is s2, "TaskScheduler should be singleton"
    await s1.shutdown()


@pytest.mark.asyncio
async def test_start_and_shutdown(in_memory_db_url):
    """Test scheduler can start and shutdown cleanly."""
    sched = TaskScheduler(jobstore_url=in_memory_db_url)
    await sched.start()
    assert sched.is_running(), "Scheduler should be running after start"
    await sched.shutdown()
    assert not sched.is_running(), "Scheduler should stop after shutdown"


@pytest.mark.asyncio
async def test_add_job_with_cron(scheduler):
    """Test adding a cron job."""
    call_log: List[str] = []

    async def sample_task(msg: str):
        call_log.append(msg)

    job_id = "test_cron_job"
    cron_expr = "*/1 * * * *"  # every minute
    await scheduler.add_job(
        job_id=job_id,
        cron_expression=cron_expr,
        func=sample_task,
        kwargs={"msg": "cron_fired"},
    )

    # Verify job is registered
    job = scheduler.get_job(job_id)
    assert job is not None, "Job should be registered"
    assert job["job_id"] == job_id


@pytest.mark.asyncio
async def test_remove_job(scheduler):
    """Test removing a job."""

    async def dummy_task():
        pass

    job_id = "test_remove_job"
    await scheduler.add_job(job_id=job_id, cron_expression="0 0 * * *", func=dummy_task)
    assert scheduler.get_job(job_id) is not None

    await scheduler.remove_job(job_id)
    assert scheduler.get_job(job_id) is None, "Job should be removed"


@pytest.mark.asyncio
async def test_list_jobs(scheduler):
    """Test listing all jobs."""

    async def dummy_task():
        pass

    await scheduler.add_job("job1", "0 0 * * *", dummy_task)
    await scheduler.add_job("job2", "0 1 * * *", dummy_task)

    jobs = scheduler.list_jobs()
    assert len(jobs) >= 2, "Should have at least 2 jobs"
    job_ids = [j["job_id"] for j in jobs]
    assert "job1" in job_ids
    assert "job2" in job_ids


@pytest.mark.asyncio
async def test_invalid_cron_expression(scheduler):
    """Test adding job with invalid cron raises ValueError."""

    async def dummy_task():
        pass

    with pytest.raises(ValueError, match="Invalid cron expression"):
        await scheduler.add_job("bad_job", "not a cron", dummy_task)


@pytest.mark.asyncio
async def test_job_execution_with_kwargs(scheduler):
    """Test job actually executes with correct kwargs."""
    result = []

    async def capture_task(x: int, y: int):
        result.append(x + y)

    job_id = "test_exec_job"
    # Use a cron that fires immediately (next second)
    now = datetime.now()
    next_sec = now + timedelta(seconds=2)
    cron_expr = f"{next_sec.second} {next_sec.minute} {next_sec.hour} * * *"

    await scheduler.add_job(
        job_id=job_id,
        cron_expression=cron_expr,
        func=capture_task,
        kwargs={"x": 3, "y": 5},
    )

    # Wait for job to fire
    await asyncio.sleep(3)

    assert len(result) == 1, "Job should have executed once"
    assert result[0] == 8, "Job should compute 3+5=8"


@pytest.mark.asyncio
async def test_duplicate_job_id_raises(scheduler):
    """Test adding job with duplicate ID raises ValueError."""

    async def dummy_task():
        pass

    await scheduler.add_job("dup_job", "0 0 * * *", dummy_task)

    with pytest.raises(ValueError, match="already exists"):
        await scheduler.add_job("dup_job", "0 1 * * *", dummy_task)
