"""Extends HTTP Triggers.

Supports more trigger types, such as RequestHttpTrigger.
"""
from enum import Enum
from typing import List, Optional, Type, Union

from starlette.requests import Request

from ..flow import IOField, OperatorCategory, OperatorType, ViewMetadata
from .http_trigger import (
    _PARAMETER_ENDPOINT,
    _PARAMETER_MEDIA_TYPE,
    _PARAMETER_METHODS_ALL,
    _PARAMETER_RESPONSE_BODY,
    _PARAMETER_STATUS_CODE,
    _PARAMETER_STREAMING_RESPONSE,
    BaseHttpBody,
    HttpTrigger,
)


class RequestHttpTrigger(HttpTrigger):
    """Request http trigger for AWEL."""

    metadata = ViewMetadata(
        label="Request Http Trigger",
        name="request_http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description="Trigger your workflow by http request, and parse the request body"
        " as a starlette Request",
        inputs=[],
        outputs=[
            IOField.build_from(
                "Request Body",
                "request_body",
                Request,
                description="The request body of the API endpoint, parse as a starlette"
                " Request",
            ),
        ],
        parameters=[
            _PARAMETER_ENDPOINT.new(),
            _PARAMETER_METHODS_ALL.new(),
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
        """Initialize a RequestHttpTrigger."""
        if not router_tags:
            router_tags = ["AWEL RequestHttpTrigger"]
        super().__init__(
            endpoint,
            methods,
            streaming_response=streaming_response,
            request_body=Request,
            http_response_body=http_response_body,
            response_media_type=response_media_type,
            status_code=status_code,
            router_tags=router_tags,
            register_to_app=True,
            **kwargs,
        )
