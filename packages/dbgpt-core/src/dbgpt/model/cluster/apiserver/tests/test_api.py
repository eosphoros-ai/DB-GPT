import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from dbgpt.component import SystemApp
from dbgpt.model.cluster.apiserver.api import (
    ModelList,
    api_settings,
    initialize_apiserver,
)
from dbgpt.model.cluster.tests.conftest import _new_cluster
from dbgpt.model.cluster.worker.manager import _DefaultWorkerManagerFactory
from dbgpt.model.parameter import ModelAPIServerParameters
from dbgpt.util.fastapi import create_app
from dbgpt.util.openai_utils import chat_completion, chat_completion_stream
from dbgpt.util.utils import LoggingParameters

app = create_app()
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
#     allow_headers=["*"],
# )


@pytest_asyncio.fixture
async def system_app():
    return SystemApp(app)


@pytest_asyncio.fixture
async def client(request, system_app: SystemApp):
    param = getattr(request, "param", {})
    api_keys = param.get("api_keys", [])
    client_api_key = param.get("client_api_key")
    if "num_workers" not in param:
        param["num_workers"] = 2
    if "api_keys" in param:
        del param["api_keys"]
    headers = {}
    if client_api_key:
        headers["Authorization"] = "Bearer " + client_api_key
    print(f"param: {param}")
    api_params = ModelAPIServerParameters(
        log=LoggingParameters(level="INFO"), api_keys=api_keys
    )
    app = create_app()
    if api_settings:
        # Clear global api keys
        api_settings.api_keys = []
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test", headers=headers
    ) as client:
        async with _new_cluster(**param) as cluster:
            worker_manager, model_registry = cluster
            system_app.register(_DefaultWorkerManagerFactory, worker_manager)
            system_app.register_instance(model_registry)
            initialize_apiserver(api_params, None, None, app, system_app)
            yield client


@pytest.mark.asyncio
async def test_get_all_models(client: AsyncClient):
    res = await client.get("/api/v1/models")
    res.status_code == 200
    model_lists = ModelList.model_validate(res.json())
    print(f"model list json: {res.json()}")
    assert model_lists.object == "list"
    assert len(model_lists.data) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, expected_messages",
    [
        ({"stream_messags": ["Hello", " world."]}, ""),
    ],
    indirect=["client"],
)
async def test_chat_completions(client: AsyncClient, expected_messages):
    chat_data = {
        "model": "test-model-name-0",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }
    full_text = ""
    async for text in chat_completion_stream(
        "/api/v1/chat/completions", chat_data, client
    ):
        full_text += text
    assert full_text == expected_messages

    assert (
        await chat_completion("/api/v1/chat/completions", chat_data, client)
        == expected_messages
    )
