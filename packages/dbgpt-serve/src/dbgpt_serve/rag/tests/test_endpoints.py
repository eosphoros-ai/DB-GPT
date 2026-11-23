from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ..api.endpoints import get_service, router


@pytest.fixture
def service():
    service = MagicMock()
    service.config.api_keys = None
    service.sync_document = AsyncMock(return_value=[7])
    return service


@pytest_asyncio.fixture
async def client(service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, body",
    [
        ("/documents/sync", [{"doc_id": 7, "space_id": "1"}]),
        ("/documents/batch_sync", [{"doc_id": 7, "space_id": "1"}]),
        ("/documents/7/sync", {"space_id": "1"}),
    ],
)
async def test_sync_document_routes_await_service(client, service, path, body):
    response = await client.post(path, json=body)

    assert response.status_code == 200
    assert response.json()["data"] == [7]
    service.sync_document.assert_awaited_once()
    requests = service.sync_document.await_args.args[0]
    assert [request.doc_id for request in requests] == [7]
