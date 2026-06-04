import pytest

from dbgpt_client.knowledge import create_space
from dbgpt_client.schema import SpaceModel


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _CreateSpaceClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    async def post(self, path, body):
        self.requests.append((path, body))
        return _Response(self.payload)


@pytest.mark.asyncio
async def test_create_space_accepts_primary_key_response():
    client = _CreateSpaceClient(
        {"success": True, "err_code": None, "err_msg": None, "data": 2}
    )
    request = SpaceModel(
        name="test_space",
        vector_type="Chroma",
        desc="for client space",
        owner="dbgpt",
    )

    created = await create_space(client, request)

    assert created.id == 2
    assert created.name == "test_space"
    assert created.vector_type == "Chroma"
    assert created.desc == "for client space"
    assert created.owner == "dbgpt"
    assert client.requests[0][0] == "/knowledge/spaces"


@pytest.mark.asyncio
async def test_create_space_preserves_mapping_response():
    client = _CreateSpaceClient(
        {
            "success": True,
            "err_code": None,
            "err_msg": None,
            "data": {
                "id": 2,
                "name": "server_space",
                "vector_type": "Milvus",
                "desc": "from server",
                "owner": "dbgpt",
            },
        }
    )

    created = await create_space(client, SpaceModel(name="request_space"))

    assert created.id == 2
    assert created.name == "server_space"
    assert created.vector_type == "Milvus"
    assert created.desc == "from server"
