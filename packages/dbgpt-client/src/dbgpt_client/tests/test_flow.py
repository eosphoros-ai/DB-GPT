import pytest

from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt_client.flow import create_flow


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _CreateFlowClient:
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
async def test_create_flow_posts_instead_of_get():
    client = _CreateFlowClient(
        {
            "success": True,
            "err_code": None,
            "err_msg": None,
            "data": {"label": "test-flow", "name": "test_flow"},
        }
    )
    request = FlowPanel(label="test-flow", name="test_flow")

    created = await create_flow(client, request)

    assert created.name == "test_flow"
    assert client.requests[0][0] == "post"
    assert client.requests[0][1] == "/awel/flows"
    assert client.requests[0][2] == request.to_dict()
