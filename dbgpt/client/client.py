"""This module contains the client for the DB-GPT API."""
import json
import os
from typing import Any, AsyncGenerator, List, Optional, Union
from urllib.parse import urlparse

import httpx

from dbgpt.core.schema.api import ChatCompletionResponse, ChatCompletionStreamResponse

from .schema import ChatCompletionRequestBody

CLIENT_API_PATH = "api"
CLIENT_SERVE_PATH = "serve"


class ClientException(Exception):
    """ClientException is raised when an error occurs in the client."""

    def __init__(self, status=None, reason=None, http_resp=None):
        """Initialize the ClientException.

        Args:
            status: Optional[int], the HTTP status code.
            reason: Optional[str], the reason for the exception.
            http_resp: Optional[httpx.Response], the HTTP response object.
        """
        self.status = status
        self.reason = reason
        self.http_resp = http_resp
        self.headers = http_resp.headers if http_resp else None
        self.body = http_resp.text if http_resp else None

    def __str__(self):
        """Return the error message."""
        error_message = "({0})\n" "Reason: {1}\n".format(self.status, self.reason)
        if self.headers:
            error_message += "HTTP response headers: {0}\n".format(self.headers)

        if self.body:
            error_message += "HTTP response body: {0}\n".format(self.body)

        return error_message


"""Client API."""


class Client:
    """The client for the DB-GPT API."""

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        version: str = "v2",
        timeout: Optional[httpx._types.TimeoutTypes] = 120,
    ):
        """Create the client.

        Args:
            api_base: Optional[str], a full URL for the DB-GPT API.
                Defaults to the `http://localhost:5000/api/v2`.
            api_key: Optional[str], The dbgpt api key to use for authentication.
                Defaults to None.
            timeout: Optional[httpx._types.TimeoutTypes]: The timeout to use.
                Defaults to None.
            In most cases, pass in a float number to specify the timeout in seconds.
        Returns:
            None
        Raise: ClientException

        Examples:
        --------
        .. code-block:: python

            from dbgpt.client import Client

            DBGPT_API_BASE = "http://localhost:5000/api/v2"
            DBGPT_API_KEY = "dbgpt"
            client = Client(api_base=DBGPT_API_BASE, api_key=DBGPT_API_KEY)
            client.chat(model="chatgpt_proxyllm", messages="Hello?")
        """
        if not api_base:
            api_base = os.getenv(
                "DBGPT_API_BASE", f"http://localhost:5000/{CLIENT_API_PATH}/{version}"
            )
        if not api_key:
            api_key = os.getenv("DBGPT_API_KEY")
        if api_base and is_valid_url(api_base):
            self._api_url = api_base
        else:
            raise ValueError(f"api url {api_base} does not exist or is not accessible.")
        self._api_key = api_key
        self._version = version
        self._timeout = timeout
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        self._http_client = httpx.AsyncClient(
            headers=headers, timeout=timeout if timeout else httpx.Timeout(None)
        )

    async def chat(
        self,
        model: str,
        messages: Union[str, List[str]],
        temperature: Optional[float] = None,
        max_new_tokens: Optional[int] = None,
        chat_mode: Optional[str] = None,
        chat_param: Optional[str] = None,
        conv_uid: Optional[str] = None,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        span_id: Optional[str] = None,
        incremental: bool = True,
        enable_vis: bool = True,
    ) -> ChatCompletionResponse:
        """
        Chat Completion.

        Args:
            model: str, The model name.
            messages: Union[str, List[str]], The user input messages.
            temperature: Optional[float], What sampling temperature to use,between 0
                and 2. Higher values like 0.8 will make the output more random,
                while lower values like 0.2 will make it more focused and deterministic.
            max_new_tokens: Optional[int].The maximum number of tokens that can be
                generated in the chat completion.
            chat_mode: Optional[str], The chat mode.
            chat_param: Optional[str], The chat param of chat mode.
            conv_uid: Optional[str], The conversation id of the model inference.
            user_name: Optional[str], The user name of the model inference.
            sys_code: Optional[str], The system code of the model inference.
            span_id: Optional[str], The span id of the model inference.
            incremental: bool, Used to control whether the content is returned
                incrementally or in full each time. If this parameter is not provided,
                the default is full return.
            enable_vis: bool, Response content whether to output vis label.
        Returns:
            ChatCompletionResponse: The chat completion response.
        Examples:
        --------
        .. code-block:: python

            from dbgpt.client import Client

            DBGPT_API_BASE = "http://localhost:5000/api/v2"
            DBGPT_API_KEY = "dbgpt"
            client = Client(api_base=DBGPT_API_BASE, api_key=DBGPT_API_KEY)
            res = await client.chat(model="chatgpt_proxyllm", messages="Hello?")
        """
        request = ChatCompletionRequestBody(
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            chat_mode=chat_mode,
            chat_param=chat_param,
            conv_uid=conv_uid,
            user_name=user_name,
            sys_code=sys_code,
            span_id=span_id,
            incremental=incremental,
            enable_vis=enable_vis,
        )
        response = await self._http_client.post(
            self._api_url + "/chat/completions", json=request.dict()
        )
        if response.status_code == 200:
            json_data = json.loads(response.text)
            chat_completion_response = ChatCompletionResponse(**json_data)
            return chat_completion_response
        else:
            return json.loads(response.content)

    async def chat_stream(
        self,
        model: str,
        messages: Union[str, List[str]],
        temperature: Optional[float] = None,
        max_new_tokens: Optional[int] = None,
        chat_mode: Optional[str] = None,
        chat_param: Optional[str] = None,
        conv_uid: Optional[str] = None,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        span_id: Optional[str] = None,
        incremental: bool = True,
        enable_vis: bool = True,
    ) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """
        Chat Stream Completion.

        Args:
            model: str, The model name.
            messages: Union[str, List[str]], The user input messages.
            temperature: Optional[float], What sampling temperature to use, between 0
            and 2.Higher values like 0.8 will make the output more random, while lower
                values like 0.2 will make it more focused and deterministic.
            max_new_tokens: Optional[int], The maximum number of tokens that can be
            generated in the chat completion.
            chat_mode: Optional[str], The chat mode.
            chat_param: Optional[str], The chat param of chat mode.
            conv_uid: Optional[str], The conversation id of the model inference.
            user_name: Optional[str], The user name of the model inference.
            sys_code: Optional[str], The system code of the model inference.
            span_id: Optional[str], The span id of the model inference.
            incremental: bool, Used to control whether the content is returned
                incrementally or in full each time. If this parameter is not provided,
                the default is full return.
            enable_vis: bool, Response content whether to output vis label.
        Returns:
            ChatCompletionStreamResponse: The chat completion response.

        Examples:
        --------
        .. code-block:: python

            from dbgpt.client import Client

            DBGPT_API_BASE = "http://localhost:5000/api/v2"
            DBGPT_API_KEY = "dbgpt"
            client = Client(api_base=DBGPT_API_BASE, api_key=DBGPT_API_KEY)
            res = await client.chat_stream(model="chatgpt_proxyllm", messages="Hello?")
        """
        request = ChatCompletionRequestBody(
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            chat_mode=chat_mode,
            chat_param=chat_param,
            conv_uid=conv_uid,
            user_name=user_name,
            sys_code=sys_code,
            span_id=span_id,
            incremental=incremental,
            enable_vis=enable_vis,
        )
        async with self._http_client.stream(
            method="POST",
            url=self._api_url + "/chat/completions",
            json=request.dict(),
            headers={},
        ) as response:
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    try:
                        if line.strip() == "data: [DONE]":
                            break
                        if line.startswith("data:"):
                            json_data = json.loads(line[len("data: ") :])
                            chat_completion_response = ChatCompletionStreamResponse(
                                **json_data
                            )
                            yield chat_completion_response
                    except Exception as e:
                        raise e

            else:
                try:
                    error = await response.aread()
                    yield json.loads(error)
                except Exception as e:
                    raise e

    async def get(self, path: str, *args):
        """Get method.

        Args:
            path: str, The path to get.
            args: Any, The arguments to pass to the get method.
        """
        try:
            response = await self._http_client.get(
                f"{self._api_url}/{CLIENT_SERVE_PATH}{path}",
                *args,
            )
            return response
        finally:
            await self._http_client.aclose()

    async def post(self, path: str, args):
        """Post method.

        Args:
            path: str, The path to post.
            args: Any, The arguments to pass to the post
        """
        try:
            return await self._http_client.post(
                f"{self._api_url}/{CLIENT_SERVE_PATH}{path}",
                json=args,
            )
        finally:
            await self._http_client.aclose()

    async def post_param(self, path: str, args):
        """Post method.

        Args:
            path: str, The path to post.
            args: Any, The arguments to pass to the post
        """
        try:
            return await self._http_client.post(
                f"{self._api_url}/{CLIENT_SERVE_PATH}{path}",
                params=args,
            )
        finally:
            await self._http_client.aclose()

    async def patch(self, path: str, *args):
        """Patch method.

        Args:
            path: str, The path to patch.
            args: Any, The arguments to pass to the patch.
        """
        return self._http_client.patch(
            f"{self._api_url}/{CLIENT_SERVE_PATH}{path}", *args
        )

    async def put(self, path: str, args):
        """Put method.

        Args:
            path: str, The path to put.
            args: Any, The arguments to pass to the put.
        """
        try:
            return await self._http_client.put(
                f"{self._api_url}/{CLIENT_SERVE_PATH}{path}", json=args
            )
        finally:
            await self._http_client.aclose()

    async def delete(self, path: str, *args):
        """Delete method.

        Args:
            path: str, The path to delete.
            args: Any, The arguments to pass to the delete.
        """
        try:
            return await self._http_client.delete(
                f"{self._api_url}/{CLIENT_SERVE_PATH}{path}", *args
            )
        finally:
            await self._http_client.aclose()

    async def head(self, path: str, *args):
        """Head method.

        Args:
            path: str, The path to head.
            args: Any, The arguments to pass to the head
        """
        return self._http_client.head(self._api_url + path, *args)


def is_valid_url(api_url: Any) -> bool:
    """Check if the given URL is valid.

    Args:
        api_url: Any, The URL to check.
    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    if not isinstance(api_url, str):
        return False
    parsed = urlparse(api_url)
    return parsed.scheme != "" and parsed.netloc != ""
