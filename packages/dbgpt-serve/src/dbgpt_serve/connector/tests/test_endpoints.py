import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from dbgpt.agent.resource.connector.confirmation import _PENDING_CONFIRMATIONS
from dbgpt.component import SystemApp
from dbgpt.storage.metadata import db
from dbgpt_serve.core import BaseServeConfig
from dbgpt_serve.core.tests.conftest import asystem_app, client  # noqa: F401

from ..api.endpoints import init_endpoints, router
from ..config import ServeConfig

_APP_CONFIG = {"app_config": {"dbgpt.app.global.encrypt_key": "test_encrypt_key"}}

_PENDING_ENTRY = {
    "confirm_id": "confirm-1",
    "connector_id": "conn-1",
    "tool_name": "delete_repo",
    "args_summary": "repo='dbgpt'",
}

_INVALID_API_KEY = {
    "detail": {
        "error": {
            "message": "",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_api_key",
        }
    }
}


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    _PENDING_CONFIRMATIONS.clear()
    _PENDING_CONFIRMATIONS["confirm-1"] = dict(_PENDING_ENTRY)

    yield

    _PENDING_CONFIRMATIONS.clear()


@pytest.fixture
def config(request):
    param = getattr(request, "param", {})
    return ServeConfig(api_keys=param.get("api_keys"))


def client_init_caller(app: FastAPI, system_app: SystemApp, config: BaseServeConfig):
    app.include_router(router)
    init_endpoints(system_app, config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, asystem_app, config, has_auth",
    [
        (
            {"app_caller": client_init_caller},
            _APP_CONFIG,
            {"api_keys": "secret1"},
            False,
        ),
        (
            {"app_caller": client_init_caller, "client_api_key": "wrong_token"},
            _APP_CONFIG,
            {"api_keys": "secret1"},
            False,
        ),
        (
            {"app_caller": client_init_caller, "client_api_key": "secret1"},
            _APP_CONFIG,
            {"api_keys": "secret1"},
            True,
        ),
    ],
    indirect=["client", "asystem_app", "config"],
)
async def test_pending_confirms_requires_api_key(
    client: AsyncClient, asystem_app, config, has_auth: bool
):
    response = await client.get("/pending-confirms")
    if has_auth:
        assert response.status_code == 200
        assert response.json() == [_PENDING_ENTRY]
    else:
        assert response.status_code == 401
        assert response.json() == _INVALID_API_KEY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, asystem_app, config",
    [({"app_caller": client_init_caller}, _APP_CONFIG, {"api_keys": "secret1"})],
    indirect=["client", "asystem_app", "config"],
)
async def test_confirm_requires_api_key(client: AsyncClient, asystem_app, config):
    response = await client.post(
        "/confirm", json={"confirm_id": "confirm-1", "approved": True}
    )
    assert response.status_code == 401
    assert response.json() == _INVALID_API_KEY
    # The request must be rejected before the handler touches the queue.
    assert "confirm-1" in _PENDING_CONFIRMATIONS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, asystem_app, config",
    [({"app_caller": client_init_caller}, _APP_CONFIG, {})],
    indirect=["client", "asystem_app", "config"],
)
async def test_pending_confirms_allows_all_without_api_keys(
    client: AsyncClient, asystem_app, config
):
    response = await client.get("/pending-confirms")
    assert response.status_code == 200
    assert response.json() == [_PENDING_ENTRY]
