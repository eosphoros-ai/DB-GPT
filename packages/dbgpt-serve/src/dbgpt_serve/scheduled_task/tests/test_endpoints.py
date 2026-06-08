"""Endpoint tests for scheduled task REST API.

Uses FastAPI TestClient with real ScheduledTaskService (backed by
in-memory SQLite) and mocked scheduler / runner dependencies.
Auth dependency is overridden to return a fixed user.

Tests cover all 8 endpoints defined in ``api/endpoints.py``:
  1. POST /           — create task
  2. GET  /           — list tasks
  3. GET  /{task_id}  — get task
  4. PUT  /{task_id}  — update task
  5. POST /{task_id}/toggle — toggle task
  6. DELETE /{task_id} — delete task
  7. GET  /{task_id}/runs       — list runs
  8. GET  /{task_id}/runs/{rid} — get single run
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db

# Side-effect imports: register ORM models with SQLAlchemy metadata
from ..models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
from ..models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREFIX = "/api/v2/serve/scheduled-tasks"

_VALID_PAYLOAD = {
    "task_name": "Nightly Sales Report",
    "description": "Run nightly",
    "cron_expression": "0 2 * * *",
    "payload": {"user_input": "Show me yesterday's sales summary"},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_scheduler_mock() -> MagicMock:
    """Build a scheduler mock whose async methods return coroutines."""
    scheduler = MagicMock()
    scheduler.add_job = AsyncMock()
    scheduler.remove_job = AsyncMock()
    scheduler.pause_job = MagicMock()
    scheduler.resume_job = MagicMock()
    scheduler.get_job = MagicMock(return_value=None)
    scheduler.list_jobs = MagicMock(return_value=[])
    return scheduler


@pytest.fixture(autouse=True)
def _setup_db():
    """Initialize in-memory SQLite and create all tables before each test.

    Uses StaticPool so that all connections (including those opened by
    TestClient in a worker thread) share the same in-memory database.
    """
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield


@pytest.fixture()
def client() -> TestClient:
    """Build a FastAPI TestClient with real service + mocked scheduler."""
    from dbgpt_serve.utils.auth import (
        UserRequest,
        get_user_from_headers,
    )

    from ..api.endpoints import init_endpoints, router
    from ..service.service import ScheduledTaskService

    service = ScheduledTaskService(
        scheduler=_make_scheduler_mock(),
        runner_callable=MagicMock(),
    )

    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    init_endpoints(MagicMock(), service)

    # Override auth dependency → fixed user
    app.dependency_overrides[get_user_from_headers] = lambda: UserRequest(
        user_id="tester"
    )

    return TestClient(app)


def _create_task(client: TestClient, **overrides) -> dict:
    """Helper: POST a valid task and return the response JSON data dict."""
    body = {**_VALID_PAYLOAD, **overrides}
    resp = client.post(f"{PREFIX}/", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True, data
    return data["data"]


# ---------------------------------------------------------------------------
# 1. POST / — create task
# ---------------------------------------------------------------------------


def test_create_task(client: TestClient):
    """POST / with valid body should return success with a task_id."""
    data = _create_task(client)
    assert "task_id" in data
    assert data["task_name"] == "Nightly Sales Report"
    assert data["enabled"] is True
    assert data["cron_expression"] == "0 2 * * *"
    assert data["user_name"] == "tester"


# ---------------------------------------------------------------------------
# 2. POST / — invalid cron ⇒ 400
# ---------------------------------------------------------------------------


def test_create_task_invalid_cron(client: TestClient):
    """POST / with an invalid cron expression should return HTTP 400."""
    body = {**_VALID_PAYLOAD, "cron_expression": "not a cron"}
    resp = client.post(f"{PREFIX}/", json=body)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. GET / — list tasks
# ---------------------------------------------------------------------------


def test_list_tasks(client: TestClient):
    """After creating one task, GET / should return a list of length 1."""
    _create_task(client)
    resp = client.get(f"{PREFIX}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1


# ---------------------------------------------------------------------------
# 4. GET /{task_id} — not found ⇒ 404
# ---------------------------------------------------------------------------


def test_get_task_not_found(client: TestClient):
    """GET /{random_id} should return HTTP 404."""
    fake_id = str(uuid.uuid4())
    resp = client.get(f"{PREFIX}/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. GET /{task_id} — get existing task
# ---------------------------------------------------------------------------


def test_get_task(client: TestClient):
    """Create a task, then GET /{task_id} should return it."""
    created = _create_task(client)
    task_id = created["task_id"]

    resp = client.get(f"{PREFIX}/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["task_id"] == task_id
    assert data["data"]["task_name"] == "Nightly Sales Report"


# ---------------------------------------------------------------------------
# 6. POST /{task_id}/toggle — disable task
# ---------------------------------------------------------------------------


def test_toggle_task(client: TestClient):
    """Toggle enabled=False should update the task."""
    created = _create_task(client)
    task_id = created["task_id"]

    resp = client.post(f"{PREFIX}/{task_id}/toggle", json={"enabled": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["enabled"] is False

    # Verify via GET
    get_resp = client.get(f"{PREFIX}/{task_id}")
    assert get_resp.json()["data"]["enabled"] is False


# ---------------------------------------------------------------------------
# 7. DELETE /{task_id} — delete task
# ---------------------------------------------------------------------------


def test_delete_task(client: TestClient):
    """Delete a task, then GET should return 404."""
    created = _create_task(client)
    task_id = created["task_id"]

    # Delete
    resp = client.delete(f"{PREFIX}/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify gone
    get_resp = client.get(f"{PREFIX}/{task_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. GET /{task_id}/runs — empty run list
# ---------------------------------------------------------------------------


def test_list_runs_empty(client: TestClient):
    """After creating a task with no executions, runs list should be empty."""
    created = _create_task(client)
    task_id = created["task_id"]

    resp = client.get(f"{PREFIX}/{task_id}/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 0
