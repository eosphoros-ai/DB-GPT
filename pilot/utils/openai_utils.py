from typing import Dict, Any, Awaitable, Callable, Optional, Iterator
import httpx
import asyncio
import logging
import json

logger = logging.getLogger(__name__)
MessageCaller = Callable[[str], Awaitable[None]]


async def _do_chat_completion(
    url: str,
    chat_data: Dict[str, Any],
    client: httpx.AsyncClient,
    headers: Dict[str, Any] = {},
    timeout: int = 60,
    caller: Optional[MessageCaller] = None,
) -> Iterator[str]:
    async with client.stream(
        "POST",
        url,
        headers=headers,
        json=chat_data,
        timeout=timeout,
    ) as res:
        if res.status_code != 200:
            error_message = await res.aread()
            if error_message:
                error_message = error_message.decode("utf-8")
            logger.error(
                f"Request failed with status {res.status_code}. Error: {error_message}"
            )
            raise httpx.RequestError(
                f"Request failed with status {res.status_code}",
                request=res.request,
            )
        async for line in res.aiter_lines():
            if line:
                if not line.startswith("data: "):
                    if caller:
                        await caller(line)
                    yield line
                else:
                    decoded_line = line.split("data: ", 1)[1]
                    if decoded_line.lower().strip() != "[DONE]".lower():
                        obj = json.loads(decoded_line)
                        if obj["choices"][0]["delta"].get("content") is not None:
                            text = obj["choices"][0]["delta"].get("content")
                            if caller:
                                await caller(text)
                            yield text
            await asyncio.sleep(0.02)


async def chat_completion_stream(
    url: str,
    chat_data: Dict[str, Any],
    client: Optional[httpx.AsyncClient] = None,
    headers: Dict[str, Any] = {},
    timeout: int = 60,
    caller: Optional[MessageCaller] = None,
) -> Iterator[str]:
    if client:
        async for text in _do_chat_completion(
            url,
            chat_data,
            client=client,
            headers=headers,
            timeout=timeout,
            caller=caller,
        ):
            yield text
    else:
        async with httpx.AsyncClient() as client:
            async for text in _do_chat_completion(
                url,
                chat_data,
                client=client,
                headers=headers,
                timeout=timeout,
                caller=caller,
            ):
                yield text


async def chat_completion(
    url: str,
    chat_data: Dict[str, Any],
    client: Optional[httpx.AsyncClient] = None,
    headers: Dict[str, Any] = {},
    timeout: int = 60,
    caller: Optional[MessageCaller] = None,
) -> str:
    full_text = ""
    async for text in chat_completion_stream(
        url, chat_data, client, headers=headers, timeout=timeout, caller=caller
    ):
        full_text += text
    return full_text
