"""A server that provides OpenAI-compatible RESTful APIs. It supports:
- Chat Completions. (Reference: https://platform.openai.com/docs/api-reference/chat)

Adapted from https://github.com/lm-sys/FastChat/blob/main/fastchat/serve/openai_api_server.py
"""

import asyncio
import logging
import os
from typing import Any, Dict, Generator, List, Optional

import shortuuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt._private.pydantic import BaseModel, model_to_dict
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core import ModelOutput
from dbgpt.core.interface.message import ModelMessage
from dbgpt.core.schema.api import (
    APIChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    CompletionResponseChoice,
    CompletionResponseStreamChoice,
    CompletionStreamResponse,
    DeltaMessage,
    EmbeddingsRequest,
    EmbeddingsResponse,
    ErrorCode,
    ErrorResponse,
    ModelCard,
    ModelList,
    ModelPermission,
    RelevanceRequest,
    RelevanceResponse,
    UsageInfo,
)
from dbgpt.model.base import ModelInstance
from dbgpt.model.cluster.manager_base import WorkerManager, WorkerManagerFactory
from dbgpt.model.cluster.registry import ModelRegistry
from dbgpt.model.parameter import ModelAPIServerParameters, WorkerType
from dbgpt.util.chat_util import transform_to_sse
from dbgpt.util.fastapi import create_app
from dbgpt.util.tracer import initialize_tracer, root_tracer
from dbgpt.util.tracer.tracer_impl import TracerParameters
from dbgpt.util.utils import LoggingParameters, setup_logging

logger = logging.getLogger(__name__)


class APIServerException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class APISettings(BaseModel):
    api_keys: Optional[List[str]] = None
    api_params: Optional[ModelAPIServerParameters] = None

    @property
    def embedding_bach_size(self):
        if not self.api_params:
            return 4
        return self.api_params.embedding_batch_size

    @property
    def ignore_stop_exceeds_error(self):
        if not self.api_params:
            return False
        return self.api_params.ignore_stop_exceeds_error


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
        model_to_dict(ErrorResponse(message=message, code=code)), status_code=400
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
    if request.stop and isinstance(request.stop, list) and len(request.stop) > 4:
        # https://platform.openai.com/docs/api-reference/chat/create#chat-create-stop
        if not api_settings.ignore_stop_exceeds_error:
            return create_error_response(
                ErrorCode.PARAM_OUT_OF_RANGE,
                f"Invalid 'stop': array too long. Expected an array with "
                f"maximum length 4, but got an array with length {len(request.stop)}"
                " instead.",
            )
        else:
            request.stop = request.stop[:4]

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
                f"Could not get component "
                f"{ComponentType.WORKER_MANAGER_FACTORY} from system_app",
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
                f"Could not get component {ComponentType.MODEL_REGISTRY} from"
                " system_app",
            )
        return controller

    async def get_model_instances_or_raise(
        self, model_name: str, worker_type: str = "llm"
    ) -> List[ModelInstance]:
        """Get healthy model instances with request model name

        Args:
            model_name (str): Model name
            worker_type (str, optional): Worker type. Defaults to "llm".

        Raises:
            APIServerException: If can't get healthy model instances with request model
             name
        """
        registry = self.get_model_registry()
        suffix = f"@{worker_type}"
        registry_model_name = f"{model_name}{suffix}"
        model_instances = await registry.get_all_instances(
            registry_model_name, healthy_only=True
        )
        if not model_instances:
            all_instances = await registry.get_all_model_instances(healthy_only=True)
            models = [
                ins.model_name.split(suffix)[0]
                for ins in all_instances
                if ins.model_name.endswith(suffix)
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
            if (
                worker_type == WorkerType.LLM
                or worker_type == WorkerType.TEXT2VEC
                or worker_type == WorkerType.RERANKER
            ):
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
        curr_usage = UsageInfo()
        last_usage = UsageInfo()
        for i in range(n):
            last_usage.prompt_tokens += curr_usage.prompt_tokens
            last_usage.completion_tokens += curr_usage.completion_tokens
            last_usage.total_tokens += curr_usage.total_tokens

            # First chunk with role
            choice_data = ChatCompletionResponseStreamChoice(
                index=i,
                delta=DeltaMessage(role="assistant"),
                finish_reason=None,
            )
            chunk = ChatCompletionStreamResponse(
                id=id,
                choices=[choice_data],
                model=model_name,
                usage=last_usage,
            )
            yield transform_to_sse(chunk)

            previous_text = ""
            async for model_output in worker_manager.generate_stream(params):
                model_output: ModelOutput = model_output
                if model_output.error_code != 0:
                    yield transform_to_sse(model_output.to_dict())
                    yield transform_to_sse("[DONE]")
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
                has_usage = False
                if model_output.usage:
                    curr_usage = UsageInfo.model_validate(model_output.usage)
                    has_usage = True
                    usage = UsageInfo(
                        prompt_tokens=last_usage.prompt_tokens
                        + curr_usage.prompt_tokens,
                        total_tokens=last_usage.total_tokens + curr_usage.total_tokens,
                        completion_tokens=last_usage.completion_tokens
                        + curr_usage.completion_tokens,
                    )
                else:
                    has_usage = False
                    usage = UsageInfo()
                chunk = ChatCompletionStreamResponse(
                    id=id, choices=[choice_data], model=model_name, usage=usage
                )
                if delta_text is None:
                    if model_output.finish_reason is not None:
                        finish_stream_events.append(chunk)
                    if not has_usage:
                        continue
                yield transform_to_sse(chunk)

        # There is not "content" field in the last delta message, so exclude_none to
        # exclude field "content".
        for finish_chunk in finish_stream_events:
            yield transform_to_sse(finish_chunk)
        yield transform_to_sse("[DONE]")

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
                task_usage = UsageInfo.model_validate(model_output.usage)
                for usage_key, usage_value in model_to_dict(task_usage).items():
                    setattr(usage, usage_key, getattr(usage, usage_key) + usage_value)

        return ChatCompletionResponse(model=model_name, choices=choices, usage=usage)

    async def completion_stream_generator(
        self, request: CompletionRequest, params: Dict
    ):
        worker_manager = self.get_worker_manager()
        id = f"cmpl-{shortuuid.random()}"
        finish_stream_events = []
        params["span_id"] = root_tracer.get_current_span_id()
        curr_usage = UsageInfo()
        last_usage = UsageInfo()
        for text in request.prompt:
            for i in range(request.n):
                params["prompt"] = text
                previous_text = ""
                last_usage.prompt_tokens += curr_usage.prompt_tokens
                last_usage.completion_tokens += curr_usage.completion_tokens
                last_usage.total_tokens += curr_usage.total_tokens

                async for model_output in worker_manager.generate_stream(params):
                    model_output: ModelOutput = model_output
                    if model_output.error_code != 0:
                        yield transform_to_sse(model_output.to_dict())
                        yield transform_to_sse("[DONE]")
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

                    choice_data = CompletionResponseStreamChoice(
                        index=i,
                        text=delta_text or "",
                        # TODO: logprobs
                        logprobs=None,
                        finish_reason=model_output.finish_reason,
                    )
                    if model_output.usage:
                        curr_usage = UsageInfo.model_validate(model_output.usage)
                        usage = UsageInfo(
                            prompt_tokens=last_usage.prompt_tokens
                            + curr_usage.prompt_tokens,
                            total_tokens=last_usage.total_tokens
                            + curr_usage.total_tokens,
                            completion_tokens=last_usage.completion_tokens
                            + curr_usage.completion_tokens,
                        )
                    else:
                        usage = UsageInfo()
                    chunk = CompletionStreamResponse(
                        id=id,
                        object="text_completion",
                        choices=[choice_data],
                        model=request.model,
                        usage=UsageInfo.model_validate(usage),
                    )
                    if delta_text is None:
                        if model_output.finish_reason is not None:
                            finish_stream_events.append(chunk)
                        continue
                    yield transform_to_sse(chunk)
                last_usage = curr_usage
        # There is not "content" field in the last delta message, so exclude_none to
        # exclude field "content".
        for finish_chunk in finish_stream_events:
            yield transform_to_sse(finish_chunk)
        yield transform_to_sse("[DONE]")

    async def completion_generate(
        self, request: CompletionRequest, params: Dict[str, Any]
    ):
        worker_manager: WorkerManager = self.get_worker_manager()
        choices = []
        completions = []
        for text in request.prompt:
            for i in range(request.n):
                params["prompt"] = text
                model_output = asyncio.create_task(worker_manager.generate(params))
                completions.append(model_output)
        try:
            all_tasks = await asyncio.gather(*completions)
        except Exception as e:
            return create_error_response(ErrorCode.INTERNAL_ERROR, str(e))
        usage = UsageInfo()
        for i, model_output in enumerate(all_tasks):
            model_output: ModelOutput = model_output
            if model_output.error_code != 0:
                return create_error_response(model_output.error_code, model_output.text)
            choices.append(
                CompletionResponseChoice(
                    index=i,
                    text=model_output.text,
                    finish_reason=model_output.finish_reason,
                )
            )
            if model_output.usage:
                task_usage = UsageInfo.model_validate(model_output.usage)
                for usage_key, usage_value in model_to_dict(task_usage).items():
                    setattr(usage, usage_key, getattr(usage, usage_key) + usage_value)
        return CompletionResponse(
            model=request.model, choices=choices, usage=UsageInfo.model_validate(usage)
        )

    async def embeddings_generate(
        self,
        model: str,
        texts: List[str],
        span_id: Optional[str] = None,
    ) -> List[List[float]]:
        """Generate embeddings

        Args:
            model (str): Model name
            texts (List[str]): Texts to embed
            span_id (Optional[str], optional): The span id. Defaults to None.

        Returns:
            List[List[float]]: The embeddings of texts
        """
        with root_tracer.start_span(
            "dbgpt.model.apiserver.generate_embeddings",
            parent_span_id=span_id,
            metadata={
                "model": model,
            },
        ):
            worker_manager: WorkerManager = self.get_worker_manager()
            params = {
                "input": texts,
                "model": model,
            }
            return await worker_manager.embeddings(params)

    async def relevance_generate(
        self, model: str, query: str, texts: List[str]
    ) -> List[float]:
        """Generate embeddings

        Args:
            model (str): Model name
            query (str): Query text
            texts (List[str]): Texts to embed

        Returns:
            List[List[float]]: The embeddings of texts
        """
        worker_manager: WorkerManager = self.get_worker_manager()
        params = {
            "input": texts,
            "model": model,
            "query": query,
        }
        scores = await worker_manager.embeddings(params)
        return scores[0]


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
    trace_kwargs = {
        "operation_name": "dbgpt.model.apiserver.create_chat_completion",
        "metadata": {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stop": request.stop,
            "user": request.user,
        },
    }
    if request.stream:
        generator = api_server.chat_completion_stream_generator(
            request.model, params, request.n
        )
        trace_generator = root_tracer.wrapper_async_stream(generator, **trace_kwargs)
        return StreamingResponse(trace_generator, media_type="text/event-stream")
    else:
        with root_tracer.start_span(**trace_kwargs):
            return await api_server.chat_completion_generate(
                request.model, params, request.n
            )


@router.post("/v1/completions", dependencies=[Depends(check_api_key)])
async def create_completion(
    request: CompletionRequest, api_server: APIServer = Depends(get_api_server)
):
    await api_server.get_model_instances_or_raise(request.model)
    error_check_ret = check_requests(request)
    if error_check_ret is not None:
        return error_check_ret
    if isinstance(request.prompt, str):
        request.prompt = [request.prompt]
    elif not isinstance(request.prompt, list):
        return create_error_response(
            ErrorCode.VALIDATION_TYPE_ERROR,
            "prompt must be a string or a list of strings",
        )
    elif isinstance(request.prompt, list) and not isinstance(request.prompt[0], str):
        return create_error_response(
            ErrorCode.VALIDATION_TYPE_ERROR,
            "prompt must be a string or a list of strings",
        )

    params = {
        "model": request.model,
        "prompt": request.prompt,
        "chat_model": False,
        "temperature": request.temperature,
        "max_new_tokens": request.max_tokens,
        "stop": request.stop,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "echo": request.echo,
        "presence_penalty": request.presence_penalty,
        "frequency_penalty": request.frequency_penalty,
        "user": request.user,
        # "use_beam_search": request.use_beam_search,
        # "beam_size": request.beam_size,
    }
    trace_kwargs = {
        "operation_name": "dbgpt.model.apiserver.create_completion",
        "metadata": {k: v for k, v in params.items() if v},
    }
    if request.stream:
        generator = api_server.completion_stream_generator(request, params)
        trace_generator = root_tracer.wrapper_async_stream(generator, **trace_kwargs)
        return StreamingResponse(trace_generator, media_type="text/event-stream")
    else:
        with root_tracer.start_span(**trace_kwargs):
            params["span_id"] = root_tracer.get_current_span_id()
            return await api_server.completion_generate(request, params)


@router.post("/v1/embeddings", dependencies=[Depends(check_api_key)])
async def create_embeddings(
    request: EmbeddingsRequest, api_server: APIServer = Depends(get_api_server)
):
    await api_server.get_model_instances_or_raise(request.model, worker_type="text2vec")
    texts = request.input
    if isinstance(texts, str):
        texts = [texts]
    batch_size = api_settings.embedding_bach_size
    batches = [
        texts[i : min(i + batch_size, len(texts))]
        for i in range(0, len(texts), batch_size)
    ]
    data = []
    async_tasks = []
    for num_batch, batch in enumerate(batches):
        async_tasks.append(
            api_server.embeddings_generate(
                request.model, batch, span_id=root_tracer.get_current_span_id()
            )
        )

    # Request all embeddings in parallel
    batch_embeddings: List[List[List[float]]] = await asyncio.gather(*async_tasks)
    for num_batch, embeddings in enumerate(batch_embeddings):
        data += [
            {
                "object": "embedding",
                "embedding": emb,
                "index": num_batch * batch_size + i,
            }
            for i, emb in enumerate(embeddings)
        ]
    return model_to_dict(
        EmbeddingsResponse(data=data, model=request.model, usage=UsageInfo()),
        exclude_none=True,
    )


@router.post(
    "/v1/beta/relevance",
    dependencies=[Depends(check_api_key)],
    response_model=RelevanceResponse,
)
async def create_relevance(
    request: RelevanceRequest, api_server: APIServer = Depends(get_api_server)
):
    """Generate relevance scores for a query and a list of documents."""
    await api_server.get_model_instances_or_raise(request.model, worker_type="text2vec")

    with root_tracer.start_span(
        "dbgpt.model.apiserver.generate_relevance",
        metadata={
            "model": request.model,
            "query": request.query,
        },
    ):
        scores = await api_server.relevance_generate(
            request.model, request.query, request.documents
        )
    return model_to_dict(
        RelevanceResponse(data=scores, model=request.model, usage=UsageInfo()),
        exclude_none=True,
    )


def _initialize_all(controller_addr: str, system_app: SystemApp):
    from dbgpt.model.cluster.controller.controller import ModelRegistryClient
    from dbgpt.model.cluster.worker.manager import _DefaultWorkerManagerFactory
    from dbgpt.model.cluster.worker.remote_manager import RemoteWorkerManager

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
    apiserver_params: ModelAPIServerParameters,
    sys_trace: Optional[TracerParameters] = None,
    sys_log: Optional[LoggingParameters] = None,
    app=None,
    system_app: SystemApp = None,
):
    import os

    from dbgpt.configs.model_config import LOGDIR

    global global_system_app
    global api_settings
    embedded_mod = True
    if not app:
        embedded_mod = False
        app = create_app()

    if not system_app:
        system_app = SystemApp(app)
    global_system_app = system_app

    log_config = apiserver_params.log or sys_log or LoggingParameters()
    trace_config = apiserver_params.trace or sys_trace or TracerParameters()
    setup_logging(
        "dbgpt",
        log_config=log_config,
        default_logger_filename=os.path.join(LOGDIR, "dbgpt_model_apiserver.log"),
    )

    trace_file = trace_config.file or os.path.join(
        "logs", "dbgpt_model_apiserver_tracer.jsonl"
    )
    initialize_tracer(
        trace_file,
        system_app=system_app,
        root_operation_name=trace_config.root_operation_name or "DB-GPT-APIServer",
        tracer_parameters=trace_config,
    )

    if apiserver_params.api_keys:
        api_settings.api_keys = apiserver_params.api_keys.strip().split(",")

    app.include_router(router, prefix="/api", tags=["APIServer"])

    @app.exception_handler(APIServerException)
    async def validation_apiserver_exception_handler(request, exc: APIServerException):
        return create_error_response(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return create_error_response(ErrorCode.VALIDATION_TYPE_ERROR, str(exc))

    _initialize_all(apiserver_params.controller_addr, system_app)

    if not embedded_mod:
        import uvicorn

        # https://github.com/encode/starlette/issues/617
        cors_app = CORSMiddleware(
            app=app,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        uvicorn.run(
            cors_app,
            host=apiserver_params.host,
            port=apiserver_params.port,
            log_level="info",
        )


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="DB-GPT API Server")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file.",
    )
    return parser.parse_args()


def run_apiserver(config_file: str):
    from dbgpt.configs.model_config import ROOT_PATH
    from dbgpt.util.configure import ConfigurationManager

    if not os.path.isabs(config_file) and not os.path.exists(config_file):
        config_file = os.path.join(ROOT_PATH, config_file)

    cfg = ConfigurationManager.from_file(config_file)
    apiserver_params = cfg.parse_config(
        ModelAPIServerParameters, prefix="service.model.api", hook_section="hooks"
    )

    sys_trace: Optional[TracerParameters] = None
    sys_log: Optional[LoggingParameters] = None

    if cfg.exists("trace"):
        sys_trace = cfg.parse_config(TracerParameters, prefix="trace")
    if cfg.exists("log"):
        sys_log = cfg.parse_config(LoggingParameters, prefix="log")

    log_config = apiserver_params.log or sys_log or LoggingParameters()
    trace_config = apiserver_params.trace or sys_trace or TracerParameters()
    initialize_apiserver(
        apiserver_params,
        sys_trace=trace_config,
        sys_log=log_config,
    )


if __name__ == "__main__":
    _args = parse_args()
    _config_file = _args.config
    run_apiserver(_config_file)
