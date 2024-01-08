import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from dbgpt.component import SystemApp
from dbgpt.serve.core.tests.conftest import asystem_app, client
from dbgpt.storage.metadata import db
from dbgpt.util import PaginationResult

from ..api.endpoints import init_endpoints, router
from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()

    yield


def client_init_caller(app: FastAPI, system_app: SystemApp):
    app.include_router(router)
    init_endpoints(system_app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, asystem_app, has_auth",
    [
        (
            {
                "app_caller": client_init_caller,
                "client_api_key": "test_token1",
            },
            {
                "app_config": {
                    f"{SERVE_CONFIG_KEY_PREFIX}api_keys": "test_token1,test_token2"
                }
            },
            True,
        ),
        (
            {
                "app_caller": client_init_caller,
                "client_api_key": "error_token",
            },
            {
                "app_config": {
                    f"{SERVE_CONFIG_KEY_PREFIX}api_keys": "test_token1,test_token2"
                }
            },
            False,
        ),
    ],
    indirect=["client", "asystem_app"],
)
async def test_api_health(client: AsyncClient, asystem_app, has_auth: bool):
    response = await client.get("/test_auth")
    if has_auth:
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    else:
        assert response.status_code == 401
        assert response.json() == {
            "detail": {
                "error": {
                    "message": "",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            }
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client", [{"app_caller": client_init_caller}], indirect=["client"]
)
async def test_api_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client", [{"app_caller": client_init_caller}], indirect=["client"]
)
async def test_api_create(client: AsyncClient):
    # TODO: add your test case
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client", [{"app_caller": client_init_caller}], indirect=["client"]
)
async def test_api_update(client: AsyncClient):
    # TODO: implement your test case
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client", [{"app_caller": client_init_caller}], indirect=["client"]
)
async def test_api_query(client: AsyncClient):
    # TODO: implement your test case
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client", [{"app_caller": client_init_caller}], indirect=["client"]
)
async def test_api_query_by_page(client: AsyncClient):
    # TODO: implement your test case
    pass


# Add more test cases according to your own logic
