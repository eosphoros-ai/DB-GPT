"""Extends HTTP Triggers.

Supports more trigger types, such as RequestHttpTrigger.
"""

from enum import Enum
from typing import Dict, List, Optional, Type, Union

from starlette.requests import Request

from dbgpt.util.i18n_utils import _

from ..flow import IOField, OperatorCategory, OperatorType, Parameter, ViewMetadata
from ..operators.common_operator import MapOperator
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
        label=_("Request Http Trigger"),
        name="request_http_trigger",
        category=OperatorCategory.TRIGGER,
        operator_type=OperatorType.INPUT,
        description=_(
            "Trigger your workflow by http request, and parse the request body"
            " as a starlette Request"
        ),
        inputs=[],
        outputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                Request,
                description=_(
                    "The request body of the API endpoint, parse as a starlette Request"
                ),
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


class DictHTTPSender(MapOperator[Dict, Dict]):
    """HTTP Sender operator for AWEL."""

    metadata = ViewMetadata(
        label=_("HTTP Sender"),
        name="awel_dict_http_sender",
        category=OperatorCategory.SENDER,
        description=_("Send a HTTP request to a specified endpoint"),
        inputs=[
            IOField.build_from(
                _("Request Body"),
                "request_body",
                dict,
                description=_("The request body to send"),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Response Body"),
                "response_body",
                dict,
                description=_("The response body of the HTTP request"),
            )
        ],
        parameters=[
            Parameter.build_from(
                _("HTTP Address"),
                _("address"),
                type=str,
                description=_("The address to send the HTTP request to"),
            ),
            _PARAMETER_METHODS_ALL.new(),
            _PARAMETER_STATUS_CODE.new(),
            Parameter.build_from(
                _("Timeout"),
                "timeout",
                type=int,
                optional=True,
                default=60,
                description=_("The timeout of the HTTP request in seconds"),
            ),
            Parameter.build_from(
                _("Token"),
                "token",
                type=str,
                optional=True,
                default=None,
                description=_("The token to use for the HTTP request"),
            ),
            Parameter.build_from(
                _("Cookies"),
                "cookies",
                type=str,
                optional=True,
                default=None,
                description=_("The cookies to use for the HTTP request"),
            ),
        ],
    )

    def __init__(
        self,
        address: str,
        methods: Optional[str] = "GET",
        status_code: Optional[int] = 200,
        timeout: Optional[int] = 60,
        token: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """Initialize a HTTPSender."""
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            raise ImportError(
                "aiohttp is required for HTTPSender, please install it with "
                "`pip install aiohttp`"
            )
        self._address = address
        self._methods = methods
        self._status_code = status_code
        self._timeout = timeout
        self._token = token
        self._cookies = cookies
        super().__init__(**kwargs)

    async def map(self, request_body: Dict) -> Dict:
        """Send the request body to the specified address."""
        import aiohttp

        if self._methods in ["POST", "PUT"]:
            req_kwargs = {"json": request_body}
        else:
            req_kwargs = {"params": request_body}
        method = self._methods or "GET"

        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        async with aiohttp.ClientSession(
            headers=headers,
            cookies=self._cookies,
            timeout=aiohttp.ClientTimeout(total=self._timeout),
        ) as session:
            async with session.request(
                method,
                self._address,
                raise_for_status=False,
                **req_kwargs,
            ) as response:
                status_code = response.status
                if status_code != self._status_code:
                    raise ValueError(
                        f"HTTP request failed with status code {status_code}"
                    )
                response_body = await response.json()
                return response_body
