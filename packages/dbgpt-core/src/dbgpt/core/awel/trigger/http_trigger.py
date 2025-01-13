"""Http trigger for AWEL."""

import json
import logging
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    cast,
    get_origin,
)

from dbgpt._private.pydantic import (
    BaseModel,
    Field,
    field_is_required,
    field_outer_type,
    model_fields,
    model_to_dict,
)
from dbgpt.util.i18n_utils import _
from dbgpt.util.tracer import root_tracer

from ..dag.base import DAG
from ..flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OperatorType,
    OptionValue,
    Parameter,
    ResourceCategory,
    ResourceType,
    ViewMetadata,
    register_resource,
)
from ..operators.base import BaseOperator
from ..operators.common_operator import MapOperator
from ..util._typing_util import _parse_bool
from ..util.http_util import join_paths
from .base import Trigger, TriggerMetadata

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI
    from starlette.requests import Request

    from dbgpt.core.interface.llm import ModelRequestContext

    RequestBody = Union[Type[Request], Type[BaseModel], Type[Dict[str, Any]], Type[str]]
    CommonRequestType = Union[Request, BaseModel, Dict[str, Any], str, None]
    StreamingPredictFunc = Callable[[CommonRequestType], bool]

logger = logging.getLogger(__name__)

ENDPOINT_PLACEHOLDER_DAG_ID = "{dag_id}"


class AWELHttpError(RuntimeError):
    """AWEL Http Error."""

    def __init__(self, msg: str, code: Optional[str] = None):
        """Init the AWELHttpError."""
        super().__init__(msg)
        self.msg = msg
        self.code = code


def _default_streaming_predict_func(body: "CommonRequestType") -> bool:
    if isinstance(body, BaseModel):
        body = model_to_dict(body)
    elif isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            return False
    elif not isinstance(body, dict):
        return False
    streaming = body.get("streaming") or body.get("stream")
    return _parse_bool(streaming)


class HttpTriggerMetadata(TriggerMetadata):
    """Trigger metadata."""

    path: str = Field(..., description="The path of the trigger")
    methods: List[str] = Field(..., description="The methods of the trigger")
    trigger_mode: str = Field(
        default="command", description="The mode of the trigger, command or chat"
    )
    trigger_type: Optional[str] = Field(
        default="http", description="The type of the trigger"
    )


class BaseHttpBody(BaseModel):
    """Http body.

    For http request body or response body.
    """

    @classmethod
    def get_body_class(cls) -> Type:
        """Get body class.

        Returns:
            Type: The body class.
        """
        return cls

    def get_body(self) -> Any:
        """Get the body."""
        return self

    @classmethod
    def streaming_predict_func(cls) -> Optional["StreamingPredictFunc"]:
        """Get the streaming predict function."""
        return _default_streaming_predict_func

    def streaming_response(self) -> bool:
        """Whether the response is streaming.

        Returns:
            bool: Whether the response is streaming.
        """
        return False


@register_resource(
    label=_("Dict Http Body"),
    name="dict_http_body",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Parse the request body as a dict or response body as a dict"),
)
class DictHttpBody(BaseHttpBody):
    """Dict http body."""

    _default_body: Optional[Dict[str, Any]] = None

    @classmethod
    def get_body_class(cls) -> Type[Dict[str, Any]]:
        """Get body class.

        Just return Dict[str, Any] here.

        Returns:
            Type[Dict[str, Any]]: The body class.
        """
        return Dict[str, Any]

    def get_body(self) -> Dict[str, Any]:
        """Get the body."""
        if self._default_body is None:
            raise AWELHttpError("DictHttpBody is not set")
        return self._default_body


@register_resource(
    label=_("String Http Body"),
    name="string_http_body",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Parse the request body as a string or response body as string"),
)
class StringHttpBody(BaseHttpBody):
    """String http body."""

    _default_body: Optional[str] = None

    @classmethod
    def get_body_class(cls) -> Type[str]:
        """Get body class.

        Just return str here.

        Returns:
            Type[str]: The body class.
        """
        return str

    def get_body(self) -> str:
        """Get the body."""
        if self._default_body is None:
            raise AWELHttpError("StringHttpBody is not set")
        return self._default_body


@register_resource(
    label=_("Request Http Body"),
    name="request_http_body",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Parse the request body as a starlette Request"),
)
class RequestHttpBody(BaseHttpBody):
    """Http trigger body."""

    _default_body: Optional["Request"] = None

    @classmethod
    def get_body_class(cls) -> Type["Request"]:
        """Get the request body type.

        Just return Request here.

        Returns:
            Type[Request]: The request body type.
        """
        from starlette.requests import Request

        return Request

    def get_body(self) -> "Request":
        """Get the body."""
        if self._default_body is None:
            raise AWELHttpError("RequestHttpBody is not set")
        return self._default_body


@register_resource(
    label=_("Common LLM Http Request Body"),
    name="common_llm_http_request_body",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Parse the request body as a common LLM http body"),
)
class CommonLLMHttpRequestBody(BaseHttpBody):
    """Common LLM http request body."""

    model: str = Field(
        ..., description="The model name", examples=["gpt-3.5-turbo", "proxyllm"]
    )
    messages: Union[str, List[str]] = Field(
        ..., description="User input messages", examples=["Hello", "How are you?"]
    )
    stream: bool = Field(default=False, description="Whether return stream")

    temperature: Optional[float] = Field(
        default=None,
        description="What sampling temperature to use, between 0 and 2. Higher values "
        "like 0.8 will make the output more random, while lower values like 0.2 will "
        "make it more focused and deterministic.",
    )
    max_new_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be generated in the chat "
        "completion.",
    )
    conv_uid: Optional[str] = Field(
        default=None, description="The conversation id of the model inference"
    )
    span_id: Optional[str] = Field(
        default=None, description="The span id of the model inference"
    )
    chat_mode: Optional[str] = Field(
        default="chat_normal",
        description="The chat mode",
        examples=["chat_awel_flow", "chat_normal"],
    )
    chat_param: Optional[str] = Field(
        default=None,
        description="The chat param of chat mode",
    )
    user_name: Optional[str] = Field(
        default=None, description="The user name of the model inference"
    )
    sys_code: Optional[str] = Field(
        default=None, description="The system code of the model inference"
    )
    incremental: bool = Field(
        default=True,
        description="Used to control whether the content is returned incrementally "
        "or in full each time. "
        "If this parameter is not provided, the default is full return.",
    )
    enable_vis: bool = Field(
        default=True, description="response content whether to output vis label"
    )
    extra: Optional[Dict[str, Any]] = Field(
        default=None, description="The extra info of the model inference"
    )

    @property
    def context(self) -> "ModelRequestContext":
        """Get the model request context."""
        from dbgpt.core.interface.llm import ModelRequestContext

        return ModelRequestContext(
            stream=self.stream,
            user_name=self.user_name,
            sys_code=self.sys_code,
            conv_uid=self.conv_uid,
            span_id=self.span_id,
            chat_mode=self.chat_mode,
            chat_param=self.chat_param,
            extra=self.extra,
        )


@register_resource(
    label=_("Common LLM Http Response Body"),
    name="common_llm_http_response_body",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Parse the response body as a common LLM http body"),
)
class CommonLLMHttpResponseBody(BaseHttpBody):
    """Common LLM http response body."""

    text: str = Field(
        ..., description="The generated text", examples=["Hello", "How are you?"]
    )
    error_code: int = Field(
        default=0, description="The error code, 0 means no error", examples=[0, 1]
    )
    metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The metrics of the model, like the number of tokens generated",
    )


class HttpTrigger(Trigger):
    """Http trigger for AWEL.

    Http trigger is used to trigger a DAG by http request.
    """

    metadata = ViewMetadata(
        label="Http Trigger",
        name="http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description="Trigger your workflow by http request",
        inputs=[],
        outputs=[],
        parameters=[
            Parameter.build_from(
                "API Endpoint", "endpoint", str, description="The API endpoint"
            ),
            Parameter.build_from(
                "Http Methods",
                "methods",
                str,
                optional=True,
                default="GET",
                description="The methods of the API endpoint",
                options=[
                    OptionValue(label="HTTP Method GET", name="http_get", value="GET"),
                    OptionValue(label="HTTP Method PUT", name="http_put", value="PUT"),
                    OptionValue(
                        label="HTTP Method POST", name="http_post", value="POST"
                    ),
                    OptionValue(
                        label="HTTP Method DELETE", name="http_delete", value="DELETE"
                    ),
                ],
            ),
            Parameter.build_from(
                "Http Request Trigger Body",
                "http_trigger_body",
                BaseHttpBody,
                optional=True,
                default=None,
                description="The request body of the API endpoint",
                resource_type=ResourceType.CLASS,
            ),
            Parameter.build_from(
                "Streaming Response",
                "streaming_response",
                bool,
                optional=True,
                default=False,
                description="Whether the response is streaming",
            ),
            Parameter.build_from(
                "Http Response Body",
                "http_response_body",
                BaseHttpBody,
                optional=True,
                default=None,
                description="The response body of the API endpoint",
                resource_type=ResourceType.CLASS,
            ),
            Parameter.build_from(
                "Response Media Type",
                "response_media_type",
                str,
                optional=True,
                default=None,
                description="The response media type",
            ),
            Parameter.build_from(
                "Http Status Code",
                "status_code",
                int,
                optional=True,
                default=200,
                description="The http status code",
            ),
        ],
    )

    def __init__(
        self,
        endpoint: str,
        methods: Optional[Union[str, List[str]]] = "GET",
        request_body: Optional["RequestBody"] = None,
        http_trigger_body: Optional[Type[BaseHttpBody]] = None,
        streaming_response: bool = False,
        streaming_predict_func: Optional["StreamingPredictFunc"] = None,
        http_response_body: Optional[Type[BaseHttpBody]] = None,
        response_model: Optional[Type] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str | Enum]] = None,
        register_to_app: bool = False,
        **kwargs,
    ) -> None:
        """Initialize a HttpTrigger."""
        super().__init__(**kwargs)
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        if not request_body and http_trigger_body:
            request_body = http_trigger_body.get_body_class()
            streaming_predict_func = http_trigger_body.streaming_predict_func()
        if not response_model and http_response_body:
            response_model = http_response_body.get_body_class()
        self._endpoint = endpoint
        self._methods = [methods] if isinstance(methods, str) else methods
        self._req_body = request_body
        self._streaming_response = _parse_bool(streaming_response)
        self._streaming_predict_func = streaming_predict_func
        self._response_model = response_model
        self._status_code = status_code
        self._router_tags = router_tags
        self._response_headers = response_headers
        self._response_media_type = response_media_type
        self._end_node: Optional[BaseOperator] = None
        self._register_to_app = register_to_app

    async def trigger(self, **kwargs) -> Any:
        """Trigger the DAG. Not used in HttpTrigger."""
        raise NotImplementedError("HttpTrigger does not support trigger directly")

    def register_to_app(self) -> bool:
        """Register the trigger to a FastAPI app.

        Returns:
            bool: Whether register to app, if not register to app, will register to
                router.
        """
        return self._register_to_app

    def mount_to_router(
        self, router: "APIRouter", global_prefix: Optional[str] = None
    ) -> HttpTriggerMetadata:
        """Mount the trigger to a router.

        Args:
            router (APIRouter): The router to mount the trigger.
            global_prefix (Optional[str], optional): The global prefix of the router.
        """
        endpoint = self._resolved_endpoint()
        path = join_paths(global_prefix, endpoint) if global_prefix else endpoint
        dynamic_route_function = self._create_route_func()
        router.api_route(
            endpoint,
            methods=self._methods,
            response_model=self._response_model,
            status_code=self._status_code,
            tags=self._router_tags,
        )(dynamic_route_function)

        logger.info(f"Mount http trigger success, path: {path}")
        return HttpTriggerMetadata(
            path=path, methods=self._methods, trigger_mode=self._trigger_mode()
        )

    def mount_to_app(
        self, app: "FastAPI", global_prefix: Optional[str] = None
    ) -> HttpTriggerMetadata:
        """Mount the trigger to a FastAPI app.

        TODO: The performance of this method is not good, need to be optimized.

        Args:
            app (FastAPI): The FastAPI app.
            global_prefix (Optional[str], optional): The global prefix of the app.
                Defaults to None.
        """
        from dbgpt.util.fastapi import PriorityAPIRouter

        endpoint = self._resolved_endpoint()

        path = join_paths(global_prefix, endpoint) if global_prefix else endpoint
        dynamic_route_function = self._create_route_func()
        router = cast(PriorityAPIRouter, app.router)
        router.add_api_route(
            path,
            dynamic_route_function,
            methods=self._methods,
            response_model=self._response_model,
            status_code=self._status_code,
            tags=self._router_tags,
            priority=10,
        )
        app.openapi_schema = None
        app.middleware_stack = None
        logger.info(f"Mount http trigger success, path: {path}")
        return HttpTriggerMetadata(
            path=path, methods=self._methods, trigger_mode=self._trigger_mode()
        )

    def remove_from_app(
        self, app: "FastAPI", global_prefix: Optional[str] = None
    ) -> None:
        """Remove the trigger from a FastAPI app.

        Args:
            app (FastAPI): The FastAPI app.
            global_prefix (Optional[str], optional): The global prefix of the app.
                Defaults to None.
        """
        from fastapi import APIRouter

        endpoint = self._resolved_endpoint()

        path = join_paths(global_prefix, endpoint) if global_prefix else endpoint
        app_router = cast(APIRouter, app.router)
        for i, r in enumerate(app_router.routes):
            if r.path_format == path:  # type: ignore
                # TODO, remove with path and methods
                del app_router.routes[i]

    def _resolved_endpoint(self) -> str:
        """Get the resolved endpoint.

        Replace the placeholder {dag_id} with the real dag_id.
        """
        endpoint = self._endpoint
        if ENDPOINT_PLACEHOLDER_DAG_ID not in endpoint:
            return endpoint
        if not self.dag:
            raise AWELHttpError("DAG is not set")
        dag_id = self.dag.dag_id
        return endpoint.replace(ENDPOINT_PLACEHOLDER_DAG_ID, dag_id)

    def _trigger_mode(self) -> str:
        if (
            self._req_body
            and isinstance(self._req_body, type)
            and issubclass(self._req_body, CommonLLMHttpRequestBody)
        ):
            return "chat"
        return "command"

    async def map(self, input_data: Any) -> Any:
        """Map the input data.

        Do some transformation for the input data.

        Args:
            input_data (Any): The input data from caller.

        Returns:
            Any: The mapped data.
        """
        if not self._req_body or not input_data:
            return await super().map(input_data)
        if (
            isinstance(self._req_body, type)
            and issubclass(self._req_body, BaseModel)
            and isinstance(input_data, dict)
        ):
            return self._req_body(**input_data)
        return await super().map(input_data)

    def _create_route_func(self):
        from inspect import Parameter, Signature
        from typing import get_type_hints

        from starlette.requests import Request

        is_query_method = (
            all(method in ["GET", "DELETE"] for method in self._methods)
            if self._methods
            else True
        )

        async def _trigger_dag_func(body: Union[Request, BaseModel, str, None]):
            streaming_response = self._streaming_response
            if self._streaming_predict_func:
                streaming_response = self._streaming_predict_func(body)
            elif isinstance(body, BaseHttpBody):
                # BaseHttpBody, read streaming flag from body
                streaming_response = _default_streaming_predict_func(body)
            dag = self.dag
            if not dag:
                raise AWELHttpError("DAG is not set")
            return await _trigger_dag(
                body,
                dag,
                streaming_response,
                self._response_headers,
                self._response_media_type,
            )

        def create_route_function(name, req_body_cls: Optional["RequestBody"]):
            async def route_function_request(request: Request):
                return await _trigger_dag_func(request)

            async def route_function_none():
                return await _trigger_dag_func(None)

            route_function_request.__name__ = name
            route_function_none.__name__ = name

            if not req_body_cls:
                return route_function_none
            if req_body_cls == Request:
                return route_function_request

            if is_query_method:
                if req_body_cls is str:
                    raise AWELHttpError(
                        f"Query methods {self._methods} not support str type"
                    )

                async def route_function_get(**kwargs):
                    if req_body_cls is dict or get_origin(req_body_cls) is dict:
                        body = kwargs
                    else:
                        body = req_body_cls(**kwargs)
                    return await _trigger_dag_func(body)

                if isinstance(req_body_cls, type) and issubclass(
                    req_body_cls, BaseModel
                ):
                    fields = model_fields(req_body_cls)  # type: ignore
                    parameters = []
                    for field_name, field in fields.items():
                        default_value = (
                            Parameter.empty
                            if field_is_required(field)
                            else field.default
                        )
                        parameters.append(
                            Parameter(
                                name=field_name,
                                kind=Parameter.KEYWORD_ONLY,
                                default=default_value,
                                annotation=field_outer_type(field),
                            )
                        )
                elif req_body_cls == Dict[str, Any] or req_body_cls is dict:
                    raise AWELHttpError(
                        f"Query methods {self._methods} not support dict type"
                    )
                else:
                    parameters = []
                route_function_get.__signature__ = Signature(parameters)  # type: ignore
                if isinstance(req_body_cls, type):
                    route_function_get.__annotations__ = get_type_hints(req_body_cls)
                route_function_get.__name__ = name
                return route_function_get
            else:

                async def route_function(body: req_body_cls):  # type: ignore
                    return await _trigger_dag_func(body)

                route_function.__name__ = name
                return route_function

        function_name = f"AWEL_trigger_route_{self._endpoint.replace('/', '_')}"
        if isinstance(self._req_body, type) and (  # noqa: SIM114
            issubclass(self._req_body, Request)
            or issubclass(self._req_body, BaseModel)
            or issubclass(self._req_body, dict)
            or issubclass(self._req_body, str)
        ):  # noqa: SIM114
            request_model = self._req_body
        elif get_origin(self._req_body) is dict and not is_query_method:
            request_model = self._req_body
        elif is_query_method:
            request_model = None
        else:
            err_msg = f"Unsupported request body type {self._req_body}"
            raise AWELHttpError(err_msg)

        dynamic_route_function = create_route_function(function_name, request_model)
        logger.info(
            f"mount router function {dynamic_route_function}({function_name}), "
            f"endpoint: {self._endpoint}, methods: {self._methods}"
        )
        return dynamic_route_function


async def _trigger_dag(
    body: Any,
    dag: DAG,
    streaming_response: Optional[bool] = False,
    response_headers: Optional[Dict[str, str]] = None,
    response_media_type: Optional[str] = None,
) -> Any:
    from fastapi import BackgroundTasks
    from fastapi.responses import StreamingResponse

    span_id = root_tracer._parse_span_id(body)

    leaf_nodes = dag.leaf_nodes
    if len(leaf_nodes) != 1:
        raise ValueError("HttpTrigger just support one leaf node in dag")
    end_node = cast(BaseOperator, leaf_nodes[0])
    metadata = {
        "awel_node_id": end_node.node_id,
        "awel_node_name": end_node.node_name,
    }
    if not streaming_response:
        with root_tracer.start_span(
            "dbgpt.core.trigger.http.run_dag", span_id, metadata=metadata
        ):
            return await end_node.call(call_data=body)
    else:
        headers = response_headers
        media_type = response_media_type if response_media_type else "text/event-stream"
        if not headers:
            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
            }
        _generator = await end_node.call_stream(call_data=body)
        trace_generator = root_tracer.wrapper_async_stream(
            _generator, "dbgpt.core.trigger.http.run_dag", span_id, metadata=metadata
        )

        async def _after_dag_end():
            await dag._after_dag_end(end_node.current_event_loop_task_id)

        background_tasks = BackgroundTasks()
        background_tasks.add_task(_after_dag_end)
        return StreamingResponse(
            trace_generator,
            headers=headers,
            media_type=media_type,
            background=background_tasks,
        )


_PARAMETER_ENDPOINT = Parameter.build_from(
    _("API Endpoint"), "endpoint", str, description=_("The API endpoint")
)
_PARAMETER_METHODS_POST_PUT = Parameter.build_from(
    _("Http Methods"),
    "methods",
    str,
    optional=True,
    default="POST",
    description=_("The methods of the API endpoint"),
    options=[
        OptionValue(label=_("HTTP Method PUT"), name="http_put", value="PUT"),
        OptionValue(label=_("HTTP Method POST"), name="http_post", value="POST"),
    ],
)
_PARAMETER_METHODS_ALL = Parameter.build_from(
    _("Http Methods"),
    "methods",
    str,
    optional=True,
    default="GET",
    description=_("The methods of the API endpoint"),
    options=[
        OptionValue(label=_("HTTP Method GET"), name="http_get", value="GET"),
        OptionValue(label=_("HTTP Method DELETE"), name="http_delete", value="DELETE"),
        OptionValue(label=_("HTTP Method PUT"), name="http_put", value="PUT"),
        OptionValue(label=_("HTTP Method POST"), name="http_post", value="POST"),
    ],
)
_PARAMETER_STREAMING_RESPONSE = Parameter.build_from(
    _("Streaming Response"),
    "streaming_response",
    bool,
    optional=True,
    default=False,
    description=_("Whether the response is streaming"),
)
_PARAMETER_RESPONSE_BODY = Parameter.build_from(
    _("Http Response Body"),
    "http_response_body",
    BaseHttpBody,
    optional=True,
    default=None,
    description=_("The response body of the API endpoint"),
    resource_type=ResourceType.CLASS,
)
_PARAMETER_MEDIA_TYPE = Parameter.build_from(
    _("Response Media Type"),
    "response_media_type",
    str,
    optional=True,
    default=None,
    description=_("The response media type"),
)
_PARAMETER_STATUS_CODE = Parameter.build_from(
    _("Http Status Code"),
    "status_code",
    int,
    optional=True,
    default=200,
    description=_("The http status code"),
)


class DictHttpTrigger(HttpTrigger):
    """Dict http trigger for AWEL.

    Parse the request body as a dict.
    """

    metadata = ViewMetadata(
        label=_("Dict Http Trigger"),
        name="dict_http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description=_(
            "Trigger your workflow by http request, and parse the request body"
            " as a dict"
        ),
        inputs=[],
        outputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                dict,
                description=_("The request body of the API endpoint"),
            ),
        ],
        parameters=[
            _PARAMETER_ENDPOINT.new(),
            _PARAMETER_METHODS_POST_PUT.new(),
            _PARAMETER_STREAMING_RESPONSE.new(),
            _PARAMETER_RESPONSE_BODY.new(),
            _PARAMETER_MEDIA_TYPE.new(),
            _PARAMETER_STATUS_CODE.new(),
        ],
    )

    def __init__(
        self,
        endpoint: str,
        methods: Optional[Union[str, List[str]]] = "POST",
        streaming_response: bool = False,
        http_response_body: Optional[Type[BaseHttpBody]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str | Enum]] = None,
        **kwargs,
    ):
        """Initialize a DictHttpTrigger."""
        if not router_tags:
            router_tags = ["AWEL DictHttpTrigger"]
        super().__init__(
            endpoint,
            methods,
            streaming_response=streaming_response,
            request_body=dict,
            http_response_body=http_response_body,
            response_media_type=response_media_type,
            status_code=status_code,
            router_tags=router_tags,
            register_to_app=True,
            **kwargs,
        )


class StringHttpTrigger(HttpTrigger):
    """String http trigger for AWEL."""

    metadata = ViewMetadata(
        label=_("String Http Trigger"),
        name="string_http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description=_(
            "Trigger your workflow by http request, and parse the request body"
            " as a string"
        ),
        inputs=[],
        outputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                str,
                description=_(
                    "The request body of the API endpoint, parse as a json string"
                ),
            ),
        ],
        parameters=[
            _PARAMETER_ENDPOINT.new(),
            _PARAMETER_METHODS_POST_PUT.new(),
            _PARAMETER_STREAMING_RESPONSE.new(),
            _PARAMETER_RESPONSE_BODY.new(),
            _PARAMETER_MEDIA_TYPE.new(),
            _PARAMETER_STATUS_CODE.new(),
        ],
    )

    def __init__(
        self,
        endpoint: str,
        methods: Optional[Union[str, List[str]]] = "POST",
        streaming_response: bool = False,
        http_response_body: Optional[Type[BaseHttpBody]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str | Enum]] = None,
        **kwargs,
    ):
        """Initialize a StringHttpTrigger."""
        if not router_tags:
            router_tags = ["AWEL StringHttpTrigger"]
        super().__init__(
            endpoint,
            methods,
            streaming_response=streaming_response,
            request_body=str,
            http_response_body=http_response_body,
            response_media_type=response_media_type,
            status_code=status_code,
            router_tags=router_tags,
            register_to_app=True,
            **kwargs,
        )


class CommonLLMHttpTrigger(HttpTrigger):
    """Common LLM http trigger for AWEL."""

    class MessagesOutputMapper(MapOperator[CommonLLMHttpRequestBody, str]):
        """Messages output mapper."""

        async def map(self, request_body: CommonLLMHttpRequestBody) -> str:
            """Map the request body to messages."""
            if isinstance(request_body.messages, str):
                return request_body.messages
            else:
                raise ValueError("Messages to be transformed is not a string")

    metadata = ViewMetadata(
        label=_("Common LLM Http Trigger"),
        name="common_llm_http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description=_(
            "Trigger your workflow by http request, and parse the request body "
            "as a common LLM http body"
        ),
        inputs=[],
        outputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                CommonLLMHttpRequestBody,
                description=_(
                    "The request body of the API endpoint, parse as a common "
                    "LLM http body"
                ),
            ),
            IOField.build_from(
                _("Request String Messages"),
                "request_string_messages",
                str,
                description=_(
                    "The request string messages of the API endpoint, parsed from "
                    "'messages' field of the request body"
                ),
                mappers=[MessagesOutputMapper],
            ),
        ],
        parameters=[
            Parameter.build_from(
                _("API Endpoint"),
                "endpoint",
                str,
                optional=True,
                default="/example/" + ENDPOINT_PLACEHOLDER_DAG_ID,
                description=_("The API endpoint"),
            ),
            _PARAMETER_METHODS_POST_PUT.new(),
            _PARAMETER_STREAMING_RESPONSE.new(),
            _PARAMETER_RESPONSE_BODY.new(),
            _PARAMETER_MEDIA_TYPE.new(),
            _PARAMETER_STATUS_CODE.new(),
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        endpoint: str = "/example/" + ENDPOINT_PLACEHOLDER_DAG_ID,
        methods: Optional[Union[str, List[str]]] = "POST",
        streaming_response: bool = False,
        http_response_body: Optional[Type[BaseHttpBody]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str | Enum]] = None,
        **kwargs,
    ):
        """Initialize a CommonLLMHttpTrigger."""
        if not router_tags:
            router_tags = ["AWEL CommonLLMHttpTrigger"]
        super().__init__(
            endpoint,
            methods,
            streaming_response=streaming_response,
            request_body=CommonLLMHttpRequestBody,
            http_response_body=http_response_body,
            response_media_type=response_media_type,
            status_code=status_code,
            router_tags=router_tags,
            register_to_app=True,
            **kwargs,
        )


@register_resource(
    label=_("Example Http Response"),
    name="example_http_response",
    category=ResourceCategory.HTTP_BODY,
    resource_type=ResourceType.CLASS,
    description=_("Example Http Request"),
)
class ExampleHttpResponse(BaseHttpBody):
    """Example Http Response.

    Just for test.
    Register as a resource.
    """

    server_res: str = Field(..., description="The server response from Operator")
    request_body: Dict[str, Any] = Field(
        ..., description="The request body from Http request"
    )


class ExampleHttpHelloOperator(MapOperator[dict, ExampleHttpResponse]):
    """Example Http Hello Operator.

    Just for test.
    """

    metadata = ViewMetadata(
        label=_("Example Http Hello Operator"),
        name="example_http_hello_operator",
        category=OperatorCategory.COMMON,
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Http Request Body"),
                "request_body",
                dict,
                description=_("The request body of the API endpoint(Dict[str, Any])"),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Response Body"),
                "response_body",
                ExampleHttpResponse,
                description=_("The response body of the API endpoint"),
            )
        ],
        description=_("Example Http Hello Operator"),
    )

    def __int__(self, **kwargs):
        """Initialize a ExampleHttpHelloOperator."""
        super().__init__(**kwargs)

    async def map(self, request_body: dict) -> ExampleHttpResponse:
        """Map the request body to response body."""
        print(f"Receive input value: {request_body}")
        name = request_body.get("name")
        age = request_body.get("age")
        server_res = f"Hello, {name}, your age is {age}"
        return ExampleHttpResponse(server_res=server_res, request_body=request_body)


class RequestBodyToDictOperator(MapOperator[CommonLLMHttpRequestBody, Dict[str, Any]]):
    """Request body to dict operator."""

    metadata = ViewMetadata(
        label=_("Request Body To Dict Operator"),
        name="request_body_to_dict_operator",
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Prefix Key"),
                "prefix_key",
                str,
                optional=True,
                default=None,
                description=_(
                    "The prefix key of the dict, link 'message' or 'extra.info'"
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                CommonLLMHttpRequestBody,
                description=_("The request body of the API endpoint"),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Response Body"),
                "response_body",
                dict,
                description=_("The response body of the API endpoint"),
            )
        ],
        description="Request body to dict operator",
    )

    def __init__(self, prefix_key: Optional[str] = None, **kwargs):
        """Initialize a RequestBodyToDictOperator."""
        super().__init__(**kwargs)
        self._key = prefix_key

    async def map(self, request_body: CommonLLMHttpRequestBody) -> Dict[str, Any]:
        """Map the request body to response body."""
        dict_value = model_to_dict(request_body)
        if not self._key:
            return dict_value
        else:
            keys = self._key.split(".")
            for k in keys:
                dict_value = dict_value[k]
            if not isinstance(dict_value, dict):
                raise ValueError(
                    f"Prefix key {self._key} is not a valid key of the request body"
                )
            return dict_value


class UserInputParsedOperator(MapOperator[CommonLLMHttpRequestBody, Dict[str, Any]]):
    """User input parsed operator."""

    metadata = ViewMetadata(
        label=_("User Input Parsed Operator"),
        name="user_input_parsed_operator",
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Key"),
                "key",
                str,
                optional=True,
                default="user_input",
                description=_("The key of the dict, link 'user_input'"),
            )
        ],
        inputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                CommonLLMHttpRequestBody,
                description=_("The request body of the API endpoint"),
            )
        ],
        outputs=[
            IOField.build_from(
                _("User Input Dict"),
                "user_input_dict",
                dict,
                description=_("The user input dict of the API endpoint"),
            )
        ],
        description=_(
            "User input parsed operator, parse the user input from request body"
            " and return as a dict"
        ),
    )

    def __init__(self, key: str = "user_input", **kwargs):
        """Initialize a UserInputParsedOperator."""
        self._key = key
        super().__init__(**kwargs)

    async def map(self, request_body: CommonLLMHttpRequestBody) -> Dict[str, Any]:
        """Map the request body to response body."""
        return {self._key: request_body.messages}


class RequestedParsedOperator(MapOperator[CommonLLMHttpRequestBody, str]):
    """User input parsed operator."""

    metadata = ViewMetadata(
        label=_("Request Body Parsed To String Operator"),
        name="request_body_to_str__parsed_operator",
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Key"),
                "key",
                str,
                optional=True,
                default="messages",
                description=_("The key of the dict, link 'user_input'"),
            )
        ],
        inputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                CommonLLMHttpRequestBody,
                description=_("The request body of the API endpoint"),
            )
        ],
        outputs=[
            IOField.build_from(
                _("User Input String"),
                "user_input_str",
                str,
                description=_("The user input dict of the API endpoint"),
            )
        ],
        description=_(
            "User input parsed operator, parse the user input from request body and "
            "return as a string"
        ),
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, key: str = "user_input", **kwargs):
        """Initialize a UserInputParsedOperator."""
        self._key = key
        super().__init__(**kwargs)

    async def map(self, request_body: CommonLLMHttpRequestBody) -> str:
        """Map the request body to response body."""
        dict_value = model_to_dict(request_body)
        if not self._key or self._key not in dict_value:
            raise ValueError(
                f"Prefix key {self._key} is not a valid key of the request body"
            )
        return dict_value[self._key]
