import pytest
import pytest_asyncio
from aioresponses import aioresponses
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, HTTPError
import importlib.metadata as metadata

from dbgpt.component import SystemApp
from dbgpt.util.openai_utils import chat_completion_stream, chat_completion

from dbgpt.model.cluster.apiserver.api import (
    api_settings,
    initialize_apiserver,
    ModelList,
    UsageInfo,
    ChatCompletionResponse,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    ChatCompletionResponseChoice,
    DeltaMessage,
)
from dbgpt.model.cluster.tests.conftest import _new_cluster

from dbgpt.model.cluster.worker.manager import _DefaultWorkerManagerFactory

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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
    if api_settings:
        # Clear global api keys
        api_settings.api_keys = []
    async with AsyncClient(app=app, base_url="http://test", headers=headers) as client:
        async with _new_cluster(**param) as cluster:
            worker_manager, model_registry = cluster
            system_app.register(_DefaultWorkerManagerFactory, worker_manager)
            system_app.register_instance(model_registry)
            # print(f"Instances {model_registry.registry}")
            initialize_apiserver(None, app, system_app, api_keys=api_keys)
            yield client


@pytest.mark.asyncio
async def test_get_all_models(client: AsyncClient):
    res = await client.get("/api/v1/models")
    res.status_code == 200
    model_lists = ModelList.parse_obj(res.json())
    print(f"model list json: {res.json()}")
    assert model_lists.object == "list"
    assert len(model_lists.data) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, expected_messages",
    [
        ({"stream_messags": ["Hello", " world."]}, "Hello world."),
        ({"stream_messags": ["你好，我是", "张三。"]}, "你好，我是张三。"),
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, expected_messages, client_api_key",
    [
        (
            {"stream_messags": ["Hello", " world."], "api_keys": ["abc"]},
            "Hello world.",
            "abc",
        ),
        ({"stream_messags": ["你好，我是", "张三。"], "api_keys": ["abc"]}, "你好，我是张三。", "abc"),
    ],
    indirect=["client"],
)
async def test_chat_completions_with_openai_lib_async_no_stream(
    client: AsyncClient, expected_messages: str, client_api_key: str
):
    import openai

    openai.api_key = client_api_key
    openai.api_base = "http://test/api/v1"

    model_name = "test-model-name-0"

    with aioresponses() as mocked:
        mock_message = {"text": expected_messages}
        one_res = ChatCompletionResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=expected_messages),
            finish_reason="stop",
        )
        data = ChatCompletionResponse(
            model=model_name, choices=[one_res], usage=UsageInfo()
        )
        mock_message = f"{data.json(exclude_unset=True, ensure_ascii=False)}\n\n"
        # Mock http request
        mocked.post(
            "http://test/api/v1/chat/completions", status=200, body=mock_message
        )
        completion = await openai.ChatCompletion.acreate(
            model=model_name,
            messages=[{"role": "user", "content": "Hello! What is your name?"}],
        )
        assert completion.choices[0].message.content == expected_messages


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, expected_messages, client_api_key",
    [
        (
            {"stream_messags": ["Hello", " world."], "api_keys": ["abc"]},
            "Hello world.",
            "abc",
        ),
        ({"stream_messags": ["你好，我是", "张三。"], "api_keys": ["abc"]}, "你好，我是张三。", "abc"),
    ],
    indirect=["client"],
)
async def test_chat_completions_with_openai_lib_async_stream(
    client: AsyncClient, expected_messages: str, client_api_key: str
):
    import openai

    openai.api_key = client_api_key
    openai.api_base = "http://test/api/v1"

    model_name = "test-model-name-0"

    with aioresponses() as mocked:
        mock_message = {"text": expected_messages}
        choice_data = ChatCompletionResponseStreamChoice(
            index=0,
            delta=DeltaMessage(content=expected_messages),
            finish_reason="stop",
        )
        chunk = ChatCompletionStreamResponse(
            id=0, choices=[choice_data], model=model_name
        )
        mock_message = f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"
        mocked.post(
            "http://test/api/v1/chat/completions",
            status=200,
            body=mock_message,
            content_type="text/event-stream",
        )

        stream_stream_resp = ""
        if metadata.version("openai") >= "1.0.0":
            from openai import OpenAI

            client = OpenAI(
                **{"base_url": "http://test/api/v1", "api_key": client_api_key}
            )
            res = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hello! What is your name?"}],
                stream=True,
            )
        else:
            res = openai.ChatCompletion.acreate(
                model=model_name,
                messages=[{"role": "user", "content": "Hello! What is your name?"}],
                stream=True,
            )
        async for stream_resp in res:
            stream_stream_resp = stream_resp.choices[0]["delta"].get("content", "")

        assert stream_stream_resp == expected_messages


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client, expected_messages, api_key_is_error",
    [
        (
            {
                "stream_messags": ["Hello", " world."],
                "api_keys": ["abc", "xx"],
                "client_api_key": "abc",
            },
            "Hello world.",
            False,
        ),
        ({"stream_messags": ["你好，我是", "张三。"]}, "你好，我是张三。", False),
        (
            {"stream_messags": ["你好，我是", "张三。"], "api_keys": ["abc", "xx"]},
            "你好，我是张三。",
            True,
        ),
        (
            {
                "stream_messags": ["你好，我是", "张三。"],
                "api_keys": ["abc", "xx"],
                "client_api_key": "error_api_key",
            },
            "你好，我是张三。",
            True,
        ),
    ],
    indirect=["client"],
)
async def test_chat_completions_with_api_keys(
    client: AsyncClient, expected_messages: str, api_key_is_error: bool
):
    chat_data = {
        "model": "test-model-name-0",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }
    if api_key_is_error:
        with pytest.raises(HTTPError):
            await chat_completion("/api/v1/chat/completions", chat_data, client)
    else:
        assert (
            await chat_completion("/api/v1/chat/completions", chat_data, client)
            == expected_messages
        )
