import pytest

from dbgpt._private.pydantic import model_to_dict
from dbgpt_client.datasource import create_datasource
from dbgpt_client.schema import DatasourceModel


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _CreateDatasourceClient:
    """Mirrors the real `Client`'s method signatures closely enough to
    reproduce the real bug: httpx's `AsyncClient.get()` only accepts a
    request body via the keyword-only `params`, so calling `.get(path,
    body)` with the body as a positional argument raises TypeError before
    any request is sent.
    """

    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    async def get(self, path, *args, **kwargs):
        self.requests.append(("get", path, args, kwargs))
        if args:
            raise TypeError(
                "AsyncClient.get() takes 2 positional arguments but 3 "
                "positional arguments (and 1 keyword-only argument) were "
                "given"
            )
        return _Response(self.payload)

    async def post(self, path, body):
        self.requests.append(("post", path, body))
        return _Response(self.payload)


@pytest.mark.asyncio
async def test_create_datasource_posts_instead_of_get():
    client = _CreateDatasourceClient(
        {
            "success": True,
            "err_code": None,
            "err_msg": None,
            "data": {
                "id": 1,
                "db_type": "mysql",
                "db_name": "test_db",
                "db_path": "",
                "db_host": "",
                "db_port": 0,
                "db_user": "",
                "db_pwd": "",
                "comment": "",
            },
        }
    )
    request = DatasourceModel(db_type="mysql", db_name="test_db")

    created = await create_datasource(client, request)

    assert created.id == 1
    assert created.db_name == "test_db"
    assert client.requests[0][0] == "post"
    assert client.requests[0][1] == "/datasources"
    assert client.requests[0][2] == model_to_dict(request)
