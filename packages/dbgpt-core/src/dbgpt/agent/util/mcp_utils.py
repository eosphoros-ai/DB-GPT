import logging
import ssl
from contextlib import asynccontextmanager
from datetime import timedelta
from ipaddress import ip_address
from typing import Any
from urllib.parse import urljoin, urlparse

import anyio
import httpx
import mcp.types as types
from anyio.abc import TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from httpx_sse import aconnect_sse
from mcp.shared.message import (
    SessionMessage,  # noqa: F401  (referenced via runtime constructor + type annotations)
)

logger = logging.getLogger(__name__)


def remove_request_params(url: str) -> str:
    return urljoin(url, urlparse(url).path)


@asynccontextmanager
async def sse_client(
    url: str,
    headers: dict[str, Any] | None = None,
    timeout: float = 5,
    sse_read_timeout: float = 60 * 5,
    verify: ssl.SSLContext | str | bool = True,
):
    """
    Client transport for SSE.

    `sse_read_timeout` determines how long (in seconds) the client will wait for a new
    event before disconnecting. All other HTTP operations are controlled by `timeout`.

    Yields ``(read_stream, write_stream)`` that carry
    :class:`mcp.shared.message.SessionMessage` (the wrapper introduced in mcp
    1.8 that bundles a :class:`mcp.types.JSONRPCMessage` with transport-level
    metadata). The previous protocol — passing raw ``JSONRPCMessage`` — broke
    when mcp's ``ClientSession`` started emitting ``SessionMessage`` only.
    """
    # Read stream yields SessionMessage objects to the ClientSession, or an
    # Exception when the SSE side fails — ClientSession knows how to surface
    # exceptions encountered mid-stream.
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

    # Write stream receives SessionMessage from ClientSession; we unwrap to
    # ``.message`` (the inner JSONRPCMessage) before POSTing to the server.
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async with anyio.create_task_group() as tg:
        try:
            logger.info(f"Connecting to SSE endpoint: {remove_request_params(url)}")
            async with httpx.AsyncClient(headers=headers, verify=verify) as client:
                async with aconnect_sse(
                    client,
                    "GET",
                    url,
                    timeout=httpx.Timeout(timeout, read=sse_read_timeout),
                ) as event_source:
                    event_source.response.raise_for_status()
                    logger.debug("SSE connection established")

                    # Tracks whether ``task_status.started()`` has been called.
                    # Closed over by ``sse_reader`` so the except-branch can
                    # decide between (a) re-raising — which lets
                    # ``tg.start(sse_reader)`` propagate the error to the
                    # caller — vs (b) forwarding the exception through the
                    # in-memory stream to an already-running ClientSession.
                    #
                    # The deadlock this guards against: read_stream is a
                    # zero-buffer rendezvous, so ``send(exc)`` blocks until a
                    # receiver exists. Before ``started()`` is called the
                    # ClientSession has not been constructed, no receiver
                    # exists, and ``send(exc)`` waits forever — while
                    # ``tg.start(sse_reader)`` is itself waiting for the task
                    # to call ``started()`` or exit. Re-raising breaks the
                    # cycle: ``tg.start`` re-raises, the outer ``async with``
                    # unwinds, streams get closed in ``finally``.
                    started_flag: list[bool] = [False]

                    async def sse_reader(
                        task_status: TaskStatus[str] = anyio.TASK_STATUS_IGNORED,
                    ):
                        try:
                            async for sse in event_source.aiter_sse():
                                logger.debug(f"Received SSE event: {sse.event}")
                                match sse.event:
                                    case "endpoint":
                                        endpoint_url = urljoin(url, sse.data)
                                        logger.info(
                                            f"Received endpoint URL: {endpoint_url}"
                                        )

                                        url_parsed = urlparse(url)
                                        endpoint_parsed = urlparse(endpoint_url)
                                        if (
                                            url_parsed.netloc != endpoint_parsed.netloc
                                            or url_parsed.scheme
                                            != endpoint_parsed.scheme
                                        ):
                                            error_msg = (
                                                "Endpoint origin does not match "
                                                f"connection origin: {endpoint_url}"
                                            )
                                            logger.error(error_msg)
                                            raise ValueError(error_msg)

                                        task_status.started(endpoint_url)
                                        started_flag[0] = True

                                    case "message":
                                        try:
                                            message = types.JSONRPCMessage.model_validate_json(  # noqa: E501
                                                sse.data
                                            )
                                            logger.debug(
                                                f"Received server message: {message}"
                                            )
                                        except Exception as exc:
                                            logger.error(
                                                f"Error parsing server message: {exc}"
                                            )
                                            await read_stream_writer.send(exc)
                                            continue

                                        # Wrap parsed JSONRPCMessage in a
                                        # SessionMessage so the ClientSession
                                        # consumer (mcp >= 1.8) sees the
                                        # protocol shape it expects.
                                        await read_stream_writer.send(
                                            SessionMessage(message=message)
                                        )
                                    case _:
                                        logger.warning(
                                            f"Unknown SSE event: {sse.event}"
                                        )
                        except Exception as exc:
                            logger.error(f"Error in sse_reader: {exc}")
                            if not started_flag[0]:
                                # ``tg.start`` is still awaiting started().
                                # Re-raise so it surfaces the error instead of
                                # deadlocking on send().
                                raise
                            # Steady-state path: ClientSession is reading, so
                            # forwarding via the stream is safe. Guard against
                            # the receiver having gone away to avoid blocking
                            # on a partly torn-down session.
                            try:
                                await read_stream_writer.send(exc)
                            except anyio.BrokenResourceError:
                                pass
                        finally:
                            await read_stream_writer.aclose()

                    async def post_writer(endpoint_url: str):
                        try:
                            async with write_stream_reader:
                                async for session_message in write_stream_reader:
                                    # mcp >= 1.8 hands us a SessionMessage; the
                                    # outbound HTTP body is the inner
                                    # JSONRPCMessage (transport metadata stays
                                    # client-side).
                                    inner = session_message.message
                                    logger.debug(f"Sending client message: {inner}")
                                    response = await client.post(
                                        endpoint_url,
                                        json=inner.model_dump(
                                            by_alias=True,
                                            mode="json",
                                            exclude_none=True,
                                        ),
                                    )
                                    response.raise_for_status()
                                    logger.debug(
                                        "Client message sent successfully: "
                                        f"{response.status_code}"
                                    )
                        except Exception as exc:
                            logger.error(f"Error in post_writer: {exc}")
                        finally:
                            await write_stream.aclose()

                    endpoint_url = await tg.start(sse_reader)
                    logger.info(
                        f"Starting post writer with endpoint URL: {endpoint_url}"
                    )
                    tg.start_soon(post_writer, endpoint_url)

                    try:
                        yield read_stream, write_stream
                    finally:
                        tg.cancel_scope.cancel()
        finally:
            await read_stream_writer.aclose()
            await write_stream.aclose()


# Canonical transport names accepted by ``mcp_transport_client``. Aliases are
# normalised in ``_normalise_transport`` so callers can pass either the
# kebab/snake form (``streamable_http``) or the camelCase MCP spec form
# (``streamableHttp``) without ambiguity.
_SSE_TRANSPORTS = frozenset({"sse"})
_STREAMABLE_HTTP_TRANSPORTS = frozenset({"streamable_http", "streamablehttp"})


def _normalise_transport(transport: str | None) -> str:
    """Lowercase + strip ``-``/``_`` separators so all variants collapse to one key.

    ``"Streamable-HTTP"``, ``"streamable_http"`` and ``"streamableHttp"`` all
    map to ``"streamablehttp"``; ``"SSE"`` and ``"sse"`` both map to ``"sse"``.
    """
    if not transport:
        return "sse"
    key = transport.strip().lower().replace("-", "").replace("_", "")
    return key


def _validate_streamable_http_url(url: str, headers: dict[str, Any] | None) -> None:
    """Reject cleartext credentials except for explicitly local MCP endpoints.

    Header names are arbitrary, so treat any supplied headers as potentially
    sensitive. Check the literal hostname without DNS resolution; private
    network addresses and lookalike localhost domains are not loopback.
    """
    parsed = urlparse(url)
    if parsed.scheme != "http" or (not headers and parsed.username is None):
        return
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        return
    try:
        if ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise ValueError(
        "MCP Streamable HTTP endpoints with headers or URL credentials require "
        "HTTPS, except for localhost and literal loopback addresses."
    )


@asynccontextmanager
async def streamable_http_client(
    url: str,
    headers: dict[str, Any] | None = None,
    timeout: float = 30.0,
    sse_read_timeout: float = 60 * 5,
    verify: ssl.SSLContext | str | bool = True,
):
    """Adapt the MCP SDK's Streamable HTTP clients to a pair of streams.

    Prefer ``streamable_http_client`` (mcp >= 1.24), falling back to the
    legacy ``streamablehttp_client``. SDK 1.x yields a session-id callback
    alongside the streams; SDK 2.x yields just the streams. Both are exposed
    as ``(read, write)`` so callers do not depend on the SDK version.

    Endpoints with headers or URL credentials require HTTPS unless they use
    localhost or a literal loopback address. Since custom header names can
    carry secrets, this applies to all supplied headers. The adapter-owned
    modern HTTP client does not follow redirects; configure the final MCP
    URL explicitly. Legacy clients retain their SDK's redirect behavior.

    Note on ``verify``: the SDK's HTTP client factory has no verify knob,
    so the argument is accepted for symmetry with :func:`sse_client` but is
    currently a no-op. Certificate trust uses the installed SDK's defaults.
    """
    _validate_streamable_http_url(url, headers)
    # Local import keeps the dependency lazy: if the installed mcp lib does
    # not ship the streamable_http module yet (mcp < 1.8.0), users only hit
    # this when they actually pick the streamable_http transport — not at
    # module load — and they get an actionable upgrade hint instead of a
    # raw ModuleNotFoundError.
    try:
        import mcp.client.streamable_http as streamable_http
    except ModuleNotFoundError as exc:
        if exc.name != "mcp.client.streamable_http":
            raise
        raise RuntimeError(
            "MCP Streamable HTTP transport requires mcp>=1.8.0, but the "
            "installed mcp package does not provide "
            "'mcp.client.streamable_http'. Upgrade with `uv sync` (the "
            "project's pyproject pins mcp>=1.8.0) or fall back to the "
            "'sse' transport for this connector."
        ) from exc

    if verify is not True:
        logger.debug(
            "streamable_http_client: 'verify' is ignored by upstream "
            "HTTP client factory."
        )

    client_factory = getattr(streamable_http, "streamable_http_client", None)
    if client_factory is not None:
        from mcp.shared._httpx_utils import create_mcp_http_client

        # Use the SDK factory: 1.x uses httpx, while 2.x uses httpx2. The
        # renamed transport accepts an HTTP client, not headers/timeouts.
        async with create_mcp_http_client(headers=headers) as http_client:
            # Do not forward requests or custom credential headers to a
            # redirect target, including internal services on another origin.
            http_client.follow_redirects = False
            http_client.timeout = (timeout, sse_read_timeout, timeout, timeout)
            async with client_factory(url, http_client=http_client) as streams:
                yield streams[0], streams[1]
        return

    client_factory = getattr(streamable_http, "streamablehttp_client", None)
    if client_factory is None:
        raise RuntimeError(
            "The installed mcp package provides neither 'streamable_http_client' "
            "nor 'streamablehttp_client'. Install a supported mcp SDK (>=1.8.0)."
        )
    async with client_factory(
        url,
        headers=headers,
        # Early 1.x releases require timedelta; later legacy clients accept it too.
        timeout=timedelta(seconds=timeout),
        sse_read_timeout=timedelta(seconds=sse_read_timeout),
    ) as streams:
        yield streams[0], streams[1]


@asynccontextmanager
async def mcp_transport_client(
    url: str,
    transport: str = "sse",
    headers: dict[str, Any] | None = None,
    verify: ssl.SSLContext | str | bool = True,
):
    """Dispatch to the right MCP client based on *transport*.

    Args:
        url: MCP server endpoint URL.
        transport: ``"sse"`` (legacy HTTP+SSE) or ``"streamable_http"``
            (MCP 2026-03-26 Streamable HTTP, also accepts ``"streamableHttp"``).
        headers: Optional HTTP headers (auth tokens, etc.).
        verify: TLS verify flag/context. Forwarded to :func:`sse_client`;
            ignored for streamable_http (see note in :func:`streamable_http_client`).

    Yields:
        Tuple ``(read_stream, write_stream)`` — the same shape both clients
        produce, so downstream :class:`mcp.ClientSession` usage is identical.

    Raises:
        ValueError: when *transport* is not a recognised key.
    """
    key = _normalise_transport(transport)
    if key in _STREAMABLE_HTTP_TRANSPORTS:
        async with streamable_http_client(
            url, headers=headers, verify=verify
        ) as streams:
            yield streams
        return
    if key in _SSE_TRANSPORTS:
        async with sse_client(url=url, headers=headers, verify=verify) as streams:
            yield streams
        return
    raise ValueError(
        f"Unknown MCP transport '{transport}'. "
        f"Supported: 'sse', 'streamable_http' (alias 'streamableHttp')."
    )
