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
    StreamingPredictFunc = Callable[[Union[Request, BaseModel]], bool]

logger = logging.getLogger(__name__)


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
        from fastapi import Depends
        from starlette.requests import Request

        methods = [self._methods] if isinstance(self._methods, str) else self._methods

        def create_route_function(name, req_body_cls: Optional[Type[BaseModel]]):
            async def _request_body_dependency(request: Request):
                return await _parse_request_body(request, self._req_body)

            async def route_function(body=Depends(_request_body_dependency)):
                streaming_response = self._streaming_response
                if self._streaming_predict_func:
                    streaming_response = self._streaming_predict_func(body)
                return await _trigger_dag(
                    body,
                    self.dag,
                    streaming_response,
                    self._response_headers,
                    self._response_media_type,
                )

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


async def _parse_request_body(
    request: "Request", request_body_cls: Optional["RequestBody"]
):
    from starlette.requests import Request

    if not request_body_cls:
        return None
    if request_body_cls == Request:
        return request
    if request.method == "POST":
        if request_body_cls == str:
            bytes_body = await request.body()
            str_body = bytes_body.decode("utf-8")
            return str_body
        elif issubclass(request_body_cls, BaseModel):
            json_data = await request.json()
            return request_body_cls(**json_data)
        else:
            raise ValueError(f"Invalid request body cls: {request_body_cls}")
    elif request.method == "GET":
        if issubclass(request_body_cls, BaseModel):
            return request_body_cls(**request.query_params)
        else:
            raise ValueError(f"Invalid request body cls: {request_body_cls}")


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
