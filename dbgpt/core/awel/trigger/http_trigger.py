from __future__ import annotations

from typing import Union, Type, List, TYPE_CHECKING, Optional, Any, Dict
from starlette.requests import Request
from starlette.responses import Response
from dbgpt._private.pydantic import BaseModel
import logging

from .base import Trigger
from ..dag.base import DAG
from ..operator.base import BaseOperator

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI

RequestBody = Union[Request, Type[BaseModel], str]

logger = logging.getLogger(__name__)


class HttpTrigger(Trigger):
    def __init__(
        self,
        endpoint: str,
        methods: Optional[Union[str, List[str]]] = "GET",
        request_body: Optional[RequestBody] = None,
        streaming_response: Optional[bool] = False,
        response_model: Optional[Type] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_media_type: Optional[str] = None,
        status_code: Optional[int] = 200,
        router_tags: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        self._endpoint = endpoint
        self._methods = methods
        self._req_body = request_body
        self._streaming_response = streaming_response
        self._response_model = response_model
        self._status_code = status_code
        self._router_tags = router_tags
        self._response_headers = response_headers
        self._response_media_type = response_media_type
        self._end_node: BaseOperator = None

    async def trigger(self) -> None:
        pass

    def mount_to_router(self, router: "APIRouter") -> None:
        from fastapi import Depends

        methods = self._methods if isinstance(self._methods, list) else [self._methods]

        def create_route_function(name, req_body_cls: Optional[Type[BaseModel]]):
            async def _request_body_dependency(request: Request):
                return await _parse_request_body(request, self._req_body)

            async def route_function(body=Depends(_request_body_dependency)):
                return await _trigger_dag(
                    body,
                    self.dag,
                    self._streaming_response,
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
            f"mount router function {dynamic_route_function}({function_name}), endpoint: {self._endpoint}, methods: {methods}"
        )

        router.api_route(
            self._endpoint,
            methods=methods,
            response_model=self._response_model,
            status_code=self._status_code,
            tags=self._router_tags,
        )(dynamic_route_function)


async def _parse_request_body(
    request: Request, request_body_cls: Optional[Type[BaseModel]]
):
    if not request_body_cls:
        return None
    if request.method == "POST":
        json_data = await request.json()
        return request_body_cls(**json_data)
    elif request.method == "GET":
        return request_body_cls(**request.query_params)
    else:
        return request


async def _trigger_dag(
    body: Any,
    dag: DAG,
    streaming_response: Optional[bool] = False,
    response_headers: Optional[Dict[str, str]] = None,
    response_media_type: Optional[str] = None,
) -> Any:
    from fastapi.responses import StreamingResponse

    end_node = dag.leaf_nodes
    if len(end_node) != 1:
        raise ValueError("HttpTrigger just support one leaf node in dag")
    end_node = end_node[0]
    if not streaming_response:
        return await end_node.call(call_data={"data": body})
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
        return StreamingResponse(
            end_node.call_stream(call_data={"data": body}),
            headers=headers,
            media_type=media_type,
        )
