"""A server that provides OpenAI-compatible RESTful APIs. It supports:
- Chat Completions. (Reference: https://platform.openai.com/docs/api-reference/chat)

Adapted from https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/openai_api_server.py
"""
from typing import Optional, List, Dict, Any, Generator

import logging
import asyncio
import shortuuid
import json
from fastapi import APIRouter, FastAPI
from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from pydantic import BaseSettings

from fastchat.protocol.openai_api_protocol import (
    ChatCompletionResponse,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    ChatCompletionResponseChoice,
    DeltaMessage,
    ModelCard,
    ModelList,
    ModelPermission,
    UsageInfo,
)
from fastchat.protocol.api_protocol import APIChatCompletionRequest, ErrorResponse
from fastchat.constants import ErrorCode

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.parameter_utils import EnvArgumentParser
from dbgpt.core import ModelOutput
from dbgpt.core.interface.message import ModelMessage
from dbgpt.model.base import ModelInstance
from dbgpt.model.parameter import ModelAPIServerParameters, WorkerType
from dbgpt.model.cluster import ModelRegistry
from dbgpt.model.cluster.manager_base import WorkerManager, WorkerManagerFactory
from dbgpt.util.utils import setup_logging

logger = logging.getLogger(__name__)


class APIServerException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class APISettings(BaseSettings):
    api_keys: Optional[List[str]] = None


api_settings = APISettings()
get_bearer_token = HTTPBearer(auto_error=False)


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    if api_settings.api_keys:
        if auth is None or (token := auth.credentials) not in api_settings.api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    else:
        # api_keys not set; allow all
        return None


def create_error_response(code: int, message: str) -> JSONResponse:
    """Copy from fastchat.serve.openai_api_server.check_requests

    We can't use fastchat.serve.openai_api_server because it has too many dependencies.
    """
    return JSONResponse(
        ErrorResponse(message=message, code=code).dict(), status_code=400
    )


def check_requests(request) -> Optional[JSONResponse]:
    """Copy from fastchat.serve.openai_api_server.create_error_response

    We can't use fastchat.serve.openai_api_server because it has too many dependencies.
    """
    # Check all params
    if request.max_tokens is not None and request.max_tokens <= 0:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.max_tokens} is less than the minimum of 1 - 'max_tokens'",
        )
    if request.n is not None and request.n <= 0:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.n} is less than the minimum of 1 - 'n'",
        )
    if request.temperature is not None and request.temperature < 0:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.temperature} is less than the minimum of 0 - 'temperature'",
        )
    if request.temperature is not None and request.temperature > 2:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.temperature} is greater than the maximum of 2 - 'temperature'",
        )
    if request.top_p is not None and request.top_p < 0:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.top_p} is less than the minimum of 0 - 'top_p'",
        )
    if request.top_p is not None and request.top_p > 1:
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.top_p} is greater than the maximum of 1 - 'temperature'",
        )
    if request.top_k is not None and (request.top_k > -1 and request.top_k < 1):
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.top_k} is out of Range. Either set top_k to -1 or >=1.",
        )
    if request.stop is not None and (
        not isinstance(request.stop, str) and not isinstance(request.stop, list)
    ):
        return create_error_response(
            ErrorCode.PARAM_OUT_OF_RANGE,
            f"{request.stop} is not valid under any of the given schemas - 'stop'",
        )

    return None


class APIServer(BaseComponent):
    name = ComponentType.MODEL_API_SERVER

    def init_app(self, system_app: SystemApp):
        self.system_app = system_app

    def get_worker_manager(self) -> WorkerManager:
        """Get the worker manager component instance

        Raises:
            APIServerException: If can't get worker manager component instance
        """
        worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        if not worker_manager:
            raise APIServerException(
                ErrorCode.INTERNAL_ERROR,
                f"Could not get component {ComponentType.WORKER_MANAGER_FACTORY} from system_app",
            )
        return worker_manager

    def get_model_registry(self) -> ModelRegistry:
        """Get the model registry component instance

        Raises:
            APIServerException: If can't get model registry component instance
        """

        controller = self.system_app.get_component(
            ComponentType.MODEL_REGISTRY, ModelRegistry
        )
        if not controller:
            raise APIServerException(
                ErrorCode.INTERNAL_ERROR,
                f"Could not get component {ComponentType.MODEL_REGISTRY} from system_app",
            )
        return controller

    async def get_model_instances_or_raise(
        self, model_name: str
    ) -> List[ModelInstance]:
        """Get healthy model instances with request model name

        Args:
            model_name (str): Model name

        Raises:
            APIServerException: If can't get healthy model instances with request model name
        """
        registry = self.get_model_registry()
        registry_model_name = f"{model_name}@llm"
        model_instances = await registry.get_all_instances(
            registry_model_name, healthy_only=True
        )
        if not model_instances:
            all_instances = await registry.get_all_model_instances(healthy_only=True)
            models = [
                ins.model_name.split("@llm")[0]
                for ins in all_instances
                if ins.model_name.endswith("@llm")
            ]
            if models:
                models = "&&".join(models)
                message = f"Only {models} allowed now, your model {model_name}"
            else:
                message = f"No models allowed now, your model {model_name}"
            raise APIServerException(ErrorCode.INVALID_MODEL, message)
        return model_instances

    async def get_available_models(self) -> ModelList:
        """Return available models

        Just include LLM and embedding models.

        Returns:
            List[ModelList]: The list of models.
        """
        registry = self.get_model_registry()
        model_instances = await registry.get_all_model_instances(healthy_only=True)
        model_name_set = set()
        for inst in model_instances:
            name, worker_type = WorkerType.parse_worker_key(inst.model_name)
            if worker_type == WorkerType.LLM or worker_type == WorkerType.TEXT2VEC:
                model_name_set.add(name)
        models = list(model_name_set)
        models.sort()
        # TODO: return real model permission details
        model_cards = []
        for m in models:
            model_cards.append(
                ModelCard(
                    id=m, root=m, owned_by="DB-GPT", permission=[ModelPermission()]
                )
            )
        return ModelList(data=model_cards)

    async def chat_completion_stream_generator(
        self, model_name: str, params: Dict[str, Any], n: int
    ) -> Generator[str, Any, None]:
        """Chat stream completion generator

        Args:
            model_name (str): Model name
            params (Dict[str, Any]): The parameters pass to model worker
            n (int): How many completions to generate for each prompt.
        """
        worker_manager = self.get_worker_manager()
        id = f"chatcmpl-{shortuuid.random()}"
        finish_stream_events = []
        for i in range(n):
            # First chunk with role
            choice_data = ChatCompletionResponseStreamChoice(
                index=i,
                delta=DeltaMessage(role="assistant"),
                finish_reason=None,
            )
            chunk = ChatCompletionStreamResponse(
                id=id, choices=[choice_data], model=model_name
            )
            yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"

            previous_text = ""
            async for model_output in worker_manager.generate_stream(params):
                model_output: ModelOutput = model_output
                if model_output.error_code != 0:
                    yield f"data: {json.dumps(model_output.to_dict(), ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                decoded_unicode = model_output.text.replace("\ufffd", "")
                delta_text = decoded_unicode[len(previous_text) :]
                previous_text = (
                    decoded_unicode
                    if len(decoded_unicode) > len(previous_text)
                    else previous_text
                )

                if len(delta_text) == 0:
                    delta_text = None
                choice_data = ChatCompletionResponseStreamChoice(
                    index=i,
                    delta=DeltaMessage(content=delta_text),
                    finish_reason=model_output.finish_reason,
                )
                chunk = ChatCompletionStreamResponse(
                    id=id, choices=[choice_data], model=model_name
                )
                if delta_text is None:
                    if model_output.finish_reason is not None:
                        finish_stream_events.append(chunk)
                    continue
                yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"
        # There is not "content" field in the last delta message, so exclude_none to exclude field "content".
        for finish_chunk in finish_stream_events:
            yield f"data: {finish_chunk.json(exclude_none=True, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    async def chat_completion_generate(
        self, model_name: str, params: Dict[str, Any], n: int
    ) -> ChatCompletionResponse:
        """Generate completion
        Args:
            model_name (str): Model name
            params (Dict[str, Any]): The parameters pass to model worker
            n (int): How many completions to generate for each prompt.
        """
        worker_manager: WorkerManager = self.get_worker_manager()
        choices = []
        chat_completions = []
        for i in range(n):
            model_output = asyncio.create_task(worker_manager.generate(params))
            chat_completions.append(model_output)
        try:
            all_tasks = await asyncio.gather(*chat_completions)
        except Exception as e:
            return create_error_response(ErrorCode.INTERNAL_ERROR, str(e))
        usage = UsageInfo()
        for i, model_output in enumerate(all_tasks):
            model_output: ModelOutput = model_output
            if model_output.error_code != 0:
                return create_error_response(model_output.error_code, model_output.text)
            choices.append(
                ChatCompletionResponseChoice(
                    index=i,
                    message=ChatMessage(role="assistant", content=model_output.text),
                    finish_reason=model_output.finish_reason or "stop",
                )
            )
            if model_output.usage:
                task_usage = UsageInfo.parse_obj(model_output.usage)
                for usage_key, usage_value in task_usage.dict().items():
                    setattr(usage, usage_key, getattr(usage, usage_key) + usage_value)

        return ChatCompletionResponse(model=model_name, choices=choices, usage=usage)


def get_api_server() -> APIServer:
    api_server = global_system_app.get_component(
        ComponentType.MODEL_API_SERVER, APIServer, default_component=None
    )
    if not api_server:
        global_system_app.register(APIServer)
    return global_system_app.get_component(ComponentType.MODEL_API_SERVER, APIServer)


router = APIRouter()


@router.get("/v1/models", dependencies=[Depends(check_api_key)])
async def get_available_models(api_server: APIServer = Depends(get_api_server)):
    return await api_server.get_available_models()


@router.post("/v1/chat/completions", dependencies=[Depends(check_api_key)])
async def create_chat_completion(
    request: APIChatCompletionRequest, api_server: APIServer = Depends(get_api_server)
):
    await api_server.get_model_instances_or_raise(request.model)
    error_check_ret = check_requests(request)
    if error_check_ret is not None:
        return error_check_ret
    params = {
        "model": request.model,
        "messages": ModelMessage.to_dict_list(
            ModelMessage.from_openai_messages(request.messages)
        ),
        "echo": False,
    }
    if request.temperature:
        params["temperature"] = request.temperature
    if request.top_p:
        params["top_p"] = request.top_p
    if request.max_tokens:
        params["max_new_tokens"] = request.max_tokens
    if request.stop:
        params["stop"] = request.stop
    if request.user:
        params["user"] = request.user

    # TODO check token length
    if request.stream:
        generator = api_server.chat_completion_stream_generator(
            request.model, params, request.n
        )
        return StreamingResponse(generator, media_type="text/event-stream")
    return await api_server.chat_completion_generate(request.model, params, request.n)


def _initialize_all(controller_addr: str, system_app: SystemApp):
    from dbgpt.model.cluster import RemoteWorkerManager, ModelRegistryClient
    from dbgpt.model.cluster.worker.manager import _DefaultWorkerManagerFactory

    if not system_app.get_component(
        ComponentType.MODEL_REGISTRY, ModelRegistry, default_component=None
    ):
        # Register model registry if not exist
        registry = ModelRegistryClient(controller_addr)
        registry.name = ComponentType.MODEL_REGISTRY.value
        system_app.register_instance(registry)

    registry = system_app.get_component(
        ComponentType.MODEL_REGISTRY, ModelRegistry, default_component=None
    )
    worker_manager = RemoteWorkerManager(registry)

    # Register worker manager component if not exist
    system_app.get_component(
        ComponentType.WORKER_MANAGER_FACTORY,
        WorkerManagerFactory,
        or_register_component=_DefaultWorkerManagerFactory,
        worker_manager=worker_manager,
    )
    # Register api server component if not exist
    system_app.get_component(
        ComponentType.MODEL_API_SERVER, APIServer, or_register_component=APIServer
    )


def initialize_apiserver(
    controller_addr: str,
    app=None,
    system_app: SystemApp = None,
    host: str = None,
    port: int = None,
    api_keys: List[str] = None,
):
    global global_system_app
    global api_settings
    embedded_mod = True
    if not app:
        embedded_mod = False
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    if not system_app:
        system_app = SystemApp(app)
    global_system_app = system_app

    if api_keys:
        api_settings.api_keys = api_keys

    app.include_router(router, prefix="/api", tags=["APIServer"])

    @app.exception_handler(APIServerException)
    async def validation_apiserver_exception_handler(request, exc: APIServerException):
        return create_error_response(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return create_error_response(ErrorCode.VALIDATION_TYPE_ERROR, str(exc))

    _initialize_all(controller_addr, system_app)

    if not embedded_mod:
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level="info")


def run_apiserver():
    parser = EnvArgumentParser()
    env_prefix = "apiserver_"
    apiserver_params: ModelAPIServerParameters = parser.parse_args_into_dataclass(
        ModelAPIServerParameters,
        env_prefixes=[env_prefix],
    )
    setup_logging(
        "dbgpt",
        logging_level=apiserver_params.log_level,
        logger_filename=apiserver_params.log_file,
    )
    api_keys = None
    if apiserver_params.api_keys:
        api_keys = apiserver_params.api_keys.strip().split(",")

    initialize_apiserver(
        apiserver_params.controller_addr,
        host=apiserver_params.host,
        port=apiserver_params.port,
        api_keys=api_keys,
    )


if __name__ == "__main__":
    run_apiserver()
