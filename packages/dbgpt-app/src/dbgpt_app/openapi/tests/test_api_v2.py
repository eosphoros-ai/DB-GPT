import importlib.util
import sys
import time
import types
from pathlib import Path


def _install_stub(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _load_api_v2_module():
    stub_names = [
        "fastapi",
        "fastapi.security",
        "dbgpt._private.pydantic",
        "dbgpt.component",
        "dbgpt.core.schema.api",
        "dbgpt.model.cluster.apiserver.api",
        "dbgpt.util.executor_utils",
        "dbgpt.util.tracer",
        "dbgpt_app.openapi.api_v1.api_v1",
        "dbgpt_app.scene",
        "dbgpt_client.schema",
        "dbgpt_serve.agent.agents.controller",
        "dbgpt_serve.flow.api.endpoints",
    ]
    original_modules = {name: sys.modules.get(name) for name in stub_names}

    class _Dummy:
        def __init__(self, *args, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _APIRouter:
        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class _HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            self.status_code = status_code
            self.detail = detail

    class _ChatMode:
        CHAT_APP = _Dummy(value="chat_app")
        CHAT_AWEL_FLOW = _Dummy(value="chat_flow")
        CHAT_NORMAL = _Dummy(value="chat_normal")
        CHAT_KNOWLEDGE = _Dummy(value="chat_knowledge")
        CHAT_DATA = _Dummy(value="chat_data")
        CHAT_DB_QA = _Dummy(value="chat_db")
        CHAT_DASHBOARD = _Dummy(value="chat_dashboard")

    class _Tracer:
        def start_span(self, *args, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    _install_stub(
        "fastapi",
        APIRouter=_APIRouter,
        Body=lambda *args, **kwargs: None,
        Depends=lambda *args, **kwargs: None,
        HTTPException=_HTTPException,
    )
    _install_stub(
        "fastapi.security",
        HTTPAuthorizationCredentials=object,
        HTTPBearer=lambda *args, **kwargs: None,
    )
    _install_stub(
        "dbgpt._private.pydantic",
        model_to_dict=lambda value: {},
        model_to_json=lambda value, **kwargs: "{}",
    )
    _install_stub("dbgpt.component", SystemApp=object, logger=_Dummy(info=lambda *a, **k: None))
    _install_stub(
        "dbgpt.core.schema.api",
        ChatCompletionResponse=_Dummy,
        ChatCompletionResponseChoice=_Dummy,
        ChatCompletionResponseStreamChoice=_Dummy,
        ChatCompletionStreamResponse=_Dummy,
        ChatMessage=_Dummy,
        DeltaMessage=_Dummy,
        ErrorResponse=_Dummy,
        UsageInfo=_Dummy,
    )
    _install_stub("dbgpt.model.cluster.apiserver.api", APISettings=_Dummy)
    _install_stub("dbgpt.util.executor_utils", blocking_func_to_async=None)
    _install_stub("dbgpt.util.tracer", SpanType=_Dummy(CHAT="chat"), root_tracer=_Tracer())
    _install_stub(
        "dbgpt_app.openapi.api_v1.api_v1",
        CHAT_FACTORY=_Dummy(),
        __new_conversation=lambda *a, **k: _Dummy(conv_uid="conv"),
        get_chat_flow=lambda: None,
        get_executor=lambda: None,
        stream_generator=lambda *a, **k: None,
    )
    _install_stub(
        "dbgpt_app.scene",
        BaseChat=object,
        ChatParam=_Dummy,
        ChatScene=_Dummy(
            ChatNormal=_Dummy(value=lambda: "chat_normal"),
            is_valid_mode=lambda mode: True,
            of_mode=lambda mode: mode,
        ),
    )
    _install_stub(
        "dbgpt_client.schema",
        ChatCompletionRequestBody=_Dummy,
        ChatMode=_ChatMode,
    )
    _install_stub(
        "dbgpt_serve.agent.agents.controller",
        multi_agents=_Dummy(app_agent_chat=lambda **kwargs: None),
    )
    _install_stub(
        "dbgpt_serve.flow.api.endpoints",
        get_service=lambda: _Dummy(config=_Dummy(api_keys=""), system_app=None),
    )

    module_path = Path(__file__).resolve().parents[1] / "api_v2.py"
    spec = importlib.util.spec_from_file_location("api_v2_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    try:
        spec.loader.exec_module(module)
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return module


api_v2 = _load_api_v2_module()


def test_extract_sse_json_payload_parses_data_object():
    payload = api_v2._extract_sse_json_payload('data: {"vis":"hello"}\n\n')

    assert payload == {"vis": "hello"}


def test_extract_sse_json_payload_ignores_non_json_data():
    payload = api_v2._extract_sse_json_payload("data: [DONE]\n\n")

    assert payload is None


def test_extract_sse_json_payload_handles_malformed_large_input_quickly():
    output = ("data:{{" * 80000) + "X"

    started = time.perf_counter()
    payload = api_v2._extract_sse_json_payload(output)
    elapsed = time.perf_counter() - started

    assert payload is None
    assert elapsed < 1.0
