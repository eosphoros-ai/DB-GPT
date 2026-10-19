"""Unified task management must preserve the dashboard API's resource guard."""

import asyncio
from unittest.mock import MagicMock

import pytest

from .test_endpoints import PREFIX, _create_task, _setup_db, client  # noqa: F401


@pytest.fixture()
def dashboard_tasks(client, monkeypatch):
    from dbgpt_app.openapi.api_v1.dashboard import api as dashboard_api
    from dbgpt_app.openapi.api_v1.dashboard.models import DashboardAccessDeniedError

    from ..api.endpoints import get_service
    from ..api.schemas import CreateTaskRequest, DashboardRefreshPayload

    guard = MagicMock()

    def require_permission(dashboard_id, actor, action, schema=None):
        assert actor == "tester"
        assert action == dashboard_api.DashboardAction.MANAGE_SCHEDULE
        if dashboard_id == "revoked-board":
            raise DashboardAccessDeniedError("Membership revoked")

    guard.require_permission.side_effect = require_permission
    monkeypatch.setattr(dashboard_api, "get_dashboard_service", lambda: guard)
    service = get_service()

    def create(board, owner="tester"):
        return asyncio.run(
            service.create_task(
                CreateTaskRequest(
                    task_name=board,
                    task_type="dashboard_refresh",
                    cron_expression="*/5 * * * *",
                    payload=DashboardRefreshPayload(
                        dashboard_id=board, filters={"year": 2026}
                    ),
                ),
                owner_id=owner,
            )
        ).task_id

    return {
        "allowed": create("allowed-board"),
        "revoked": create("revoked-board"),
        "foreign": create("allowed-board", "someone-else"),
        "guard": guard,
        "service": service,
    }


def test_list_combines_chat_and_authorized_dashboard_tasks(client, dashboard_tasks):
    chat = _create_task(client)
    result = client.get(PREFIX + "/").json()
    assert result["success"]
    assert {row["task_id"] for row in result["data"]} == {
        chat["task_id"],
        dashboard_tasks["allowed"],
    }


def test_dashboard_task_lifecycle_keeps_scoped_audit_and_filters(
    client, dashboard_tasks
):
    task_id = dashboard_tasks["allowed"]
    path = f"{PREFIX}/{task_id}"
    assert client.get(path).json()["data"]["payload"]["dashboard_id"] == "allowed-board"
    updated = client.put(
        path, json={"task_name": "Renamed", "cron_expression": "0 9 * * mon"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["payload"]["filters"] == {"year": 2026}
    assert updated.json()["data"]["task_name"] == "Renamed"
    for enabled in (False, True):
        response = client.post(path + "/toggle", json={"enabled": enabled})
        assert response.json()["data"]["enabled"] is enabled
    assert client.get(path + "/runs").json()["data"] == []
    assert client.get(path + "/runs/missing").status_code == 404
    assert client.delete(path).json()["success"]
    assert client.get(path).status_code == 404
    events = [
        call.args[2] for call in dashboard_tasks["guard"].record_audit.call_args_list
    ]
    assert events == [
        "schedule.updated",
        "schedule.toggled",
        "schedule.toggled",
        "schedule.deleted",
    ]


@pytest.mark.parametrize("kind,status", [("revoked", 403), ("foreign", 404)])
@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("GET", "", None),
        ("PUT", "", {"task_name": "Should not persist"}),
        ("POST", "/toggle", {"enabled": False}),
        ("DELETE", "", None),
        ("GET", "/runs", None),
        ("GET", "/runs/missing", None),
    ],
)
def test_unified_routes_do_not_bypass_dashboard_access(
    client, dashboard_tasks, kind, status, method, suffix, body
):
    task_id = dashboard_tasks[kind]
    response = client.request(method, f"{PREFIX}/{task_id}{suffix}", json=body)
    assert response.status_code == status, response.text
    remaining = asyncio.run(dashboard_tasks["service"].get_task(task_id))
    assert remaining.enabled
    assert remaining.task_name != "Should not persist"
    dashboard_tasks["guard"].record_audit.assert_not_called()


def test_chat_payload_fields_cannot_be_written_to_dashboard_task(
    client, dashboard_tasks
):
    path = f"{PREFIX}/{dashboard_tasks['allowed']}"
    result = client.put(path, json={"user_input": "Overwrite dashboard"})
    assert result.status_code == 400
    assert client.get(path).json()["data"]["payload"]["filters"] == {"year": 2026}


def test_creation_returns_the_real_next_execution_time(client):
    from ..api.endpoints import get_service

    get_service()._scheduler.get_job.return_value = {
        "next_run_time": "2026-09-23T09:00:00+08:00"
    }
    created = _create_task(client)
    assert created["next_run_time"] == "2026-09-23T09:00:00+08:00"


def test_unified_reads_honor_the_dashboard_identity_provider(
    client, dashboard_tasks, monkeypatch
):
    from fastapi import HTTPException

    from dbgpt_app.openapi.api_v1.dashboard import api as dashboard_api

    def reject_identity(user):
        raise HTTPException(status_code=401, detail="Dashboard identity disabled")

    monkeypatch.setattr(dashboard_api, "_user_id", reject_identity)
    path = f"{PREFIX}/{dashboard_tasks['allowed']}"
    assert client.get(path).status_code == 401
    assert client.get(path + "/runs").status_code == 401
    assert client.get(PREFIX + "/").json()["data"] == []
