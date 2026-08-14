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
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.registry import SessionFileRegistryError

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


# ---------------------------------------------------------------------------
# Task 9: payload v2 frozen session files at the HTTP boundary
# ---------------------------------------------------------------------------


class _FakeSessionFileRegistry:
    """Minimal in-memory copy seam double for endpoint-level tests."""

    def __init__(self, session_files: dict):
        # {(owner_id, session_id): [session_scoped_file_id, ...]}
        self._session_files = dict(session_files)
        self.task_files = {}  # {task_id: [task_scoped_file_id, ...]}
        self.copy_calls = []  # [(owner_id, session_id, file_ids, task_id)]

    def copy_session_to_task(self, *, owner_id, session_id, file_ids, task_id):
        self.copy_calls.append((owner_id, session_id, list(file_ids), task_id))
        known = self._session_files.get((owner_id, session_id), [])
        missing = [fid for fid in file_ids if fid not in known]
        if missing:
            raise SessionFileRegistryError("SESSION_FILE_NOT_FOUND", "File not found.")
        created = [
            f"sf_task_{task_id}_{index}" for index, _ in enumerate(file_ids, start=1)
        ]
        self.task_files.setdefault(task_id, []).extend(created)
        return [SimpleNamespace(file_id=fid) for fid in created]

    def list_task_files(self, *, owner_id, task_id):
        return [
            SimpleNamespace(file_id=fid) for fid in self.task_files.get(task_id, [])
        ]

    def delete_task_file(self, *, owner_id, task_id, file_id):
        files = self.task_files.get(task_id, [])
        if file_id in files:
            files.remove(file_id)
            return True
        return False


@pytest.fixture()
def client_with_registry():
    """TestClient whose service is wired to an in-memory registry double."""
    from dbgpt_serve.utils.auth import (
        UserRequest,
        get_user_from_headers,
    )

    from ..api.endpoints import init_endpoints, router
    from ..service.service import ScheduledTaskService

    registry = _FakeSessionFileRegistry({("tester", "sess-1"): ["sf_alpha", "sf_beta"]})
    service = ScheduledTaskService(
        scheduler=_make_scheduler_mock(),
        runner_callable=MagicMock(),
        session_file_registry=registry,
    )

    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    init_endpoints(MagicMock(), service)

    app.dependency_overrides[get_user_from_headers] = lambda: UserRequest(
        user_id="tester"
    )

    return TestClient(app), registry


_FROZEN_PAYLOAD = {
    "task_name": "Frozen CSV Report",
    "cron_expression": "0 8 * * *",
    "payload": {
        "user_input": "分析这份 CSV 并生成日报",
        "ext_info": {
            "session_id": "sess-1",
            "file_ids": ["sf_alpha", "sf_beta"],
            "skill_id": "daily-report",
        },
    },
}


def test_create_task_freezes_session_files(client_with_registry):
    """POST / with ext_info.file_ids persists task-scoped IDs only."""
    client, registry = client_with_registry
    resp = client.post(f"{PREFIX}/", json=_FROZEN_PAYLOAD)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True, data

    task = data["data"]
    ext_info = task["payload"]["ext_info"]
    frozen_ids = registry.task_files[task["task_id"]]
    assert ext_info["file_ids"] == frozen_ids
    # Session-scoped IDs and file_path never leak into the stored payload
    assert "sf_alpha" not in frozen_ids
    assert "sf_beta" not in frozen_ids
    assert "file_path" not in ext_info
    assert ext_info["skill_id"] == "daily-report"

    # Registry copy ran under the authenticated owner
    assert registry.copy_calls == [
        ("tester", "sess-1", ["sf_alpha", "sf_beta"], task["task_id"])
    ]


def test_create_task_rejects_foreign_or_wrong_session_files(
    client_with_registry,
):
    """Foreign/wrong-session file_ids are rejected with one
    indistinguishable 400, creating no task."""
    client, _ = client_with_registry
    responses = []
    for session_id in ("sess-2", "sess-bob"):
        body = {
            **_FROZEN_PAYLOAD,
            "payload": {
                **_FROZEN_PAYLOAD["payload"],
                "ext_info": {
                    "session_id": session_id,
                    "file_ids": ["sf_alpha"],
                },
            },
        }
        resp = client.post(f"{PREFIX}/", json=body)
        assert resp.status_code == 400, resp.text
        responses.append(resp.json())

    # Non-enumerating: identical error surface for both rejection classes
    assert responses[0] == responses[1]

    # Zero side effects: nothing persisted
    list_resp = client.get(f"{PREFIX}/")
    assert list_resp.status_code == 200
    assert list_resp.json()["data"] == []
