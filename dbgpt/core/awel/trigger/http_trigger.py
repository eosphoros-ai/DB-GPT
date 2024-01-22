"""Http trigger for AWEL."""
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, Union, cast

from dbgpt._private.pydantic import BaseModel

from ..dag.base import DAG
from ..operators.base import BaseOperator
from .base import Trigger

if TYPE_CHECKING:
    from fastapi import APIRouter
    from starlette.requests import Request

    RequestBody = Union[Type[Request], Type[BaseModel], Type[str]]
    StreamingPredictFunc = Callable[[Union[Request, BaseModel, str, None]], bool]

logger = logging.getLogger(__name__)


class AWELHttpError(RuntimeError):
    """AWEL Http Error."""

    def __init__(self, msg: str, code: Optional[str] = None):
        """Init the AWELHttpError."""
        super().__init__(msg)
        self.msg = msg
        self.code = code


class HttpTrigger(Trigger):
    """Http trigger for AWEL.

    Http trigger is used to trigger a DAG by http request.
    """

    def __init__(
        self,
        endpoint: str,
        methods: Optional[Union[str, List[str]]] = "GET",
        request_body: Optional["RequestBody"] = None,
        streaming_response: bool = False,
        streaming_predict_func: Optional["StreamingPredictFunc"] = None,
        response_model: Optional[Type] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str | Enum]] = None,
        **kwargs,
    ) -> None:
        """Initialize a HttpTrigger."""
        super().__init__(**kwargs)
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        self._endpoint = endpoint
        self._methods = methods
        self._req_body = request_body
        self._streaming_response = streaming_response
        self._streaming_predict_func = streaming_predict_func
        self._response_model = response_model
        self._status_code = status_code
        self._router_tags = router_tags
        self._response_headers = response_headers
        self._response_media_type = response_media_type
        self._end_node: Optional[BaseOperator] = None

    async def trigger(self) -> None:
        """Trigger the DAG. Not used in HttpTrigger."""
        pass

    def mount_to_router(self, router: "APIRouter") -> None:
        """Mount the trigger to a router.

        Args:
            router (APIRouter): The router to mount the trigger.
        """
        from inspect import Parameter, Signature
        from typing import get_type_hints

        from starlette.requests import Request

        methods = [self._methods] if isinstance(self._methods, str) else self._methods
        is_query_method = (
            all(method in ["GET", "DELETE"] for method in methods) if methods else True
        )

        async def _trigger_dag_func(body: Union[Request, BaseModel, str, None]):
            streaming_response = self._streaming_response
            if self._streaming_predict_func:
                streaming_response = self._streaming_predict_func(body)
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

        def create_route_function(name, req_body_cls: Optional[Type[BaseModel]]):
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
                if req_body_cls == str:
                    raise AWELHttpError(f"Query methods {methods} not support str type")

                async def route_function_get(**kwargs):
                    body = req_body_cls(**kwargs)
                    return await _trigger_dag_func(body)

                parameters = [
                    Parameter(
                        name=field_name,
                        kind=Parameter.KEYWORD_ONLY,
                        default=Parameter.empty,
                        annotation=field.outer_type_,
                    )
                    for field_name, field in req_body_cls.__fields__.items()
                ]
                route_function_get.__signature__ = Signature(parameters)  # type: ignore
                route_function_get.__annotations__ = get_type_hints(req_body_cls)
                route_function_get.__name__ = name
                return route_function_get
            else:

                async def route_function(body: req_body_cls):  # type: ignore
                    return await _trigger_dag_func(body)

                route_function.__name__ = name
                return route_function

        function_name = f"AWEL_trigger_route_{self._endpoint.replace('/', '_')}"
        request_model = (
            self._req_body
            if isinstance(self._req_body, type)
            and issubclass(self._req_body, BaseModel)
            else None
        )
        dynamic_route_function = create_route_function(function_name, request_model)
        logger.info(
            f"mount router function {dynamic_route_function}({function_name}), "
            f"endpoint: {self._endpoint}, methods: {methods}"
        )

        router.api_route(
            self._endpoint,
            methods=methods,
            response_model=self._response_model,
            status_code=self._status_code,
            tags=self._router_tags,
        )(dynamic_route_function)


async def _trigger_dag(
    body: Any,
    dag: DAG,
    streaming_response: Optional[bool] = False,
    response_headers: Optional[Dict[str, str]] = None,
    response_media_type: Optional[str] = None,
) -> Any:
    from fastapi import BackgroundTasks
    from fastapi.responses import StreamingResponse

    leaf_nodes = dag.leaf_nodes
    if len(leaf_nodes) != 1:
        raise ValueError("HttpTrigger just support one leaf node in dag")
    end_node = cast(BaseOperator, leaf_nodes[0])
    if not streaming_response:
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
        generator = await end_node.call_stream(call_data=body)
        background_tasks = BackgroundTasks()
        background_tasks.add_task(dag._after_dag_end)
        return StreamingResponse(
            generator,
            headers=headers,
            media_type=media_type,
            background=background_tasks,
        )
