"""Streamable HTTP compatibility and security regressions.

Requires MCP, httpx, httpx-sse, pytest and pytest-asyncio. Tests marked
``integration`` bind ephemeral loopback ports and need local socket access;
they do not contact external servers. Run only unit tests with
``uv run pytest tests/unit_tests/agent/test_mcp_utils.py -m 'not integration'``.
"""

import builtins
import importlib.util
import json
import sys
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import anyio
import pytest
from mcp import ClientSession


@pytest.fixture
def mcp_utils():
    """Load only the transport module, without the agent/LLM dependencies."""
    # Load the transport without importing the unrelated agent/LLM stack.
    path = (
        Path(__file__).parents[3]
        / "packages/dbgpt-core/src/dbgpt/agent/util/mcp_utils.py"
    )
    spec = importlib.util.spec_from_file_location("mcp_utils_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_count", [2, 3])
@pytest.mark.parametrize("fail", [None, "connect", "body"])
async def test_modern_client_configuration_and_cleanup(
    monkeypatch, mcp_utils, stream_count, fail
):
    """Preserve settings and close the client even if connection or usage fails."""
    import mcp.client.streamable_http as sdk
    import mcp.shared._httpx_utils as http_utils

    streams = (object(), object(), lambda: "session")[:stream_count]
    clients = []
    events = []
    original_factory = http_utils.create_mcp_http_client

    def http_factory(**kwargs):
        """Track the real HTTP client so its lifecycle can be asserted."""
        client = original_factory(**kwargs)
        clients.append(client)
        return client

    @asynccontextmanager
    async def modern(url, *, http_client):
        """Validate the supplied client while mimicking each SDK return shape."""
        assert url == "https://example.com/mcp"
        assert http_client.headers["Authorization"] == "Bearer test-token"
        assert http_client.timeout.connect == 7
        assert http_client.timeout.read == 42
        assert http_client.timeout.write == 7
        assert http_client.timeout.pool == 7
        assert not http_client.is_closed
        assert not http_client.follow_redirects
        events.append("enter")
        try:
            if fail == "connect":
                raise ValueError("connection failed")
            yield streams
        finally:
            assert not http_client.is_closed
            events.append("exit")

    def legacy(*args, **kwargs):
        """Fail if the deprecated entry point is selected over the modern one."""
        pytest.fail("The modern entry point must take precedence")

    monkeypatch.setattr(sdk, "streamable_http_client", modern, raising=False)
    monkeypatch.setattr(sdk, "streamablehttp_client", legacy, raising=False)
    monkeypatch.setattr(http_utils, "create_mcp_http_client", http_factory)

    async def connect():
        """Exercise the public wrapper, including errors inside its context."""
        async with mcp_utils.streamable_http_client(
            "https://example.com/mcp",
            headers={"Authorization": "Bearer test-token"},
            timeout=7,
            sse_read_timeout=42,
        ) as result:
            assert result == streams[:2]
            if fail == "body":
                raise ValueError("connection failed")

    if fail:
        with pytest.raises(ValueError, match="connection failed"):
            await connect()
    else:
        await connect()
    assert events == ["enter", "exit"]
    assert len(clients) == 1
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_legacy_client_fallback(monkeypatch, mcp_utils):
    """Keep older SDKs working with timedelta timeouts and legacy headers."""
    import mcp.client.streamable_http as sdk

    streams = (object(), object(), lambda: "session")
    events = []

    @asynccontextmanager
    async def legacy(url, *, headers, timeout, sse_read_timeout):
        """Emulate the legacy transport's signature and context lifetime."""
        assert url == "https://example.com/mcp"
        assert headers == {"X-Test": "legacy"}
        assert timeout == timedelta(seconds=9)
        assert sse_read_timeout == timedelta(seconds=45)
        events.append("enter")
        try:
            yield streams
        finally:
            events.append("exit")

    monkeypatch.delattr(sdk, "streamable_http_client", raising=False)
    monkeypatch.setattr(sdk, "streamablehttp_client", legacy, raising=False)
    async with mcp_utils.streamable_http_client(
        "https://example.com/mcp",
        headers={"X-Test": "legacy"},
        timeout=9,
        sse_read_timeout=45,
    ) as result:
        assert result == streams[:2]
    assert events == ["enter", "exit"]


@pytest.mark.asyncio
async def test_missing_client_has_actionable_error(monkeypatch, mcp_utils):
    """Explain unsupported SDK entry points before attempting a connection."""
    module = ModuleType("mcp.client.streamable_http")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    import mcp.client

    monkeypatch.setattr(mcp.client, "streamable_http", module)
    with pytest.raises(RuntimeError, match="neither.*streamable_http_client"):
        async with mcp_utils.streamable_http_client("https://example.com/mcp"):
            pytest.fail("The unsupported SDK must not connect")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["mcp.client.streamable_http", "httpx"])
async def test_missing_module_error(monkeypatch, mcp_utils, missing):
    """Distinguish a missing transport from a missing transitive dependency."""
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        """Inject only the relevant import error while preserving other imports."""
        if name == "mcp.client.streamable_http":
            raise ModuleNotFoundError(f"No module named '{missing}'", name=missing)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_module)
    error = (
        RuntimeError if missing == "mcp.client.streamable_http" else ModuleNotFoundError
    )
    match = "requires mcp>=1.8.0" if error is RuntimeError else "httpx"
    with pytest.raises(error, match=match):
        async with mcp_utils.streamable_http_client("https://example.com/mcp"):
            pytest.fail("The unavailable SDK must not connect")


@pytest.fixture
def mcp_http_server():
    """Small JSON-RPC server exercising the installed SDK's real transport."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        """Serve the minimal MCP JSON-RPC methods needed by the SDK client."""

        def log_message(self, *args):
            """Keep routine access logs out of the test output."""
            pass

        def respond(self, status, body=None):
            """Write a complete response, including an explicit content length."""
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            """Handle initialization, notifications, tool listing and calls."""
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((payload["method"], self.headers.get("Authorization")))
            if "id" not in payload:
                self.respond(202)
                return
            method = payload["method"]
            if method == "initialize":
                result = {
                    "protocolVersion": payload["params"]["protocolVersion"],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "compat-test", "version": "1.0"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [{"name": "echo", "inputSchema": {"type": "object"}}]
                }
            elif method == "tools/call":
                result = {"content": [{"type": "text", "text": "hello"}]}
            else:
                self.respond(400)
                return
            self.respond(200, {"jsonrpc": "2.0", "id": payload["id"], "result": result})

        def do_GET(self):
            """Decline the optional server-to-client event stream."""
            self.respond(405)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/mcp", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("transport", ["streamable_http", "streamableHttp"])
async def test_installed_sdk_round_trip(mcp_utils, mcp_http_server, transport):
    """Exercise the installed SDK using an ephemeral loopback HTTP server."""

    url, requests = mcp_http_server
    with anyio.fail_after(10):
        async with mcp_utils.mcp_transport_client(
            url, transport=transport, headers={"Authorization": "Bearer test-token"}
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                assert result.tools[0].name == "echo"
                result = await session.call_tool("echo", arguments={})
                assert result.content[0].text == "hello"
    assert [method for method, _ in requests] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "tools/call",
    ]
    assert all(auth == "Bearer test-token" for _, auth in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,headers",
    [
        ("http://example.com/mcp", {"Authorization": "Bearer secret"}),
        ("http://192.0.2.1/mcp", {"X-Api-Key": "secret"}),
        ("http://10.0.0.1/mcp", {"Cookie": "session=secret"}),
        ("http://[2001:db8::1]/mcp", {"Custom-Credential": "secret"}),
        ("http://localhost.example.com/mcp", {"X-Api-Key": "secret"}),
        ("http://localhost@192.0.2.1/mcp", {"X-Api-Key": "secret"}),
        ("http://user:secret@example.com/mcp", None),
    ],
)
async def test_reject_cleartext_credentials_before_connect(
    monkeypatch, mcp_utils, url, headers
):
    """Reject remote credentials before invoking either SDK transport factory."""
    import mcp.client.streamable_http as sdk
    import mcp.shared._httpx_utils as http_utils

    def unexpected_call(*args, **kwargs):
        """Prove that no transport or HTTP client is created for unsafe URLs."""
        pytest.fail("Unsafe credentials must be rejected before creating a client")

    monkeypatch.setattr(sdk, "streamable_http_client", unexpected_call, raising=False)
    monkeypatch.setattr(sdk, "streamablehttp_client", unexpected_call, raising=False)
    monkeypatch.setattr(http_utils, "create_mcp_http_client", unexpected_call)
    with pytest.raises(ValueError, match="HTTPS") as exc:
        async with mcp_utils.streamable_http_client(url, headers=headers):
            pytest.fail("The unsafe connection must not be entered")
    assert "secret" not in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,headers",
    [
        ("https://example.com/mcp", {"X-Api-Key": "secret"}),
        ("http://localhost/mcp", {"X-Api-Key": "secret"}),
        ("http://127.0.0.1/mcp", {"Authorization": "Bearer secret"}),
        ("http://[::1]/mcp", {"X-Api-Key": "secret"}),
        ("http://example.com/mcp", None),
        ("http://example.com/mcp", {}),
    ],
)
async def test_allow_https_loopback_and_anonymous_http(
    monkeypatch, mcp_utils, url, headers
):
    """Keep secure endpoints, local development and anonymous HTTP supported."""
    import mcp.client.streamable_http as sdk

    @asynccontextmanager
    async def modern(endpoint, *, http_client):
        """Accept the safe endpoint without performing network I/O."""
        assert endpoint == url
        yield "read", "write"

    monkeypatch.setattr(sdk, "streamable_http_client", modern, raising=False)
    async with mcp_utils.streamable_http_client(url, headers=headers) as streams:
        assert streams == ("read", "write")


@pytest.fixture
def redirect_servers():
    """Run two loopback origins and record whether a redirect reaches its target."""
    requests = {"source": [], "target": []}

    class TargetHandler(BaseHTTPRequestHandler):
        """Record requests at the destination that must never be contacted."""

        def log_message(self, *args):
            """Suppress access logs for this local test server."""

        def do_POST(self):
            """Record any redirected JSON-RPC request and return an error."""
            requests["target"].append(dict(self.headers))
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

    class RedirectHandler(TargetHandler):
        """Redirect each request to the separately bound destination server."""

        def do_POST(self):
            """Emit the selected redirect status without returning MCP data."""
            self.rfile.read(int(self.headers["Content-Length"]))
            requests["source"].append(dict(self.headers))
            self.send_response(int(self.path.strip("/")))
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/mcp")
            self.send_header("Content-Length", "0")
            self.end_headers()

    source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    servers = [source, target]
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for thread in threads:
        thread.start()
    try:
        yield f"http://127.0.0.1:{source.server_port}", requests
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("status", [307, 308])
@pytest.mark.parametrize("headers", [None, {"X-Api-Key": "test-secret"}])
async def test_modern_sdk_does_not_follow_redirects(
    mcp_utils, redirect_servers, status, headers
):
    """Block cross-origin requests and custom-key leakage using real SDK I/O."""
    import mcp.client.streamable_http as sdk

    if not hasattr(sdk, "streamable_http_client"):
        pytest.skip("The adapter-owned HTTP client requires the modern SDK entry point")
    url, requests = redirect_servers
    # The installed SDK wraps HTTP status errors in its task-group exception.
    with anyio.fail_after(10):
        with pytest.raises(Exception) as error:
            async with mcp_utils.streamable_http_client(
                f"{url}/{status}", headers=headers
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
    assert not isinstance(error.value, TimeoutError)
    assert len(requests["source"]) == 1
    assert requests["target"] == []
