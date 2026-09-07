"""Streamable HTTP compatibility tests, runnable with only MCP and pytest."""

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

import pytest
from mcp import ClientSession


@pytest.fixture
def mcp_utils():
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
    import mcp.client.streamable_http as sdk
    import mcp.shared._httpx_utils as http_utils

    streams = (object(), object(), lambda: "session")[:stream_count]
    clients = []
    events = []
    original_factory = http_utils.create_mcp_http_client

    def http_factory(**kwargs):
        client = original_factory(**kwargs)
        clients.append(client)
        return client

    @asynccontextmanager
    async def modern(url, *, http_client):
        assert url == "https://example.com/mcp"
        assert http_client.headers["Authorization"] == "Bearer test-token"
        assert http_client.timeout.connect == 7
        assert http_client.timeout.read == 42
        assert http_client.timeout.write == 7
        assert http_client.timeout.pool == 7
        assert not http_client.is_closed
        events.append("enter")
        try:
            if fail == "connect":
                raise ValueError("connection failed")
            yield streams
        finally:
            assert not http_client.is_closed
            events.append("exit")

    def legacy(*args, **kwargs):
        pytest.fail("The modern entry point must take precedence")

    monkeypatch.setattr(sdk, "streamable_http_client", modern, raising=False)
    monkeypatch.setattr(sdk, "streamablehttp_client", legacy, raising=False)
    monkeypatch.setattr(http_utils, "create_mcp_http_client", http_factory)

    async def connect():
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
    import mcp.client.streamable_http as sdk

    streams = (object(), object(), lambda: "session")
    events = []

    @asynccontextmanager
    async def legacy(url, *, headers, timeout, sse_read_timeout):
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
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
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
        def log_message(self, *args):
            pass

        def respond(self, status, body=None):
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
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
@pytest.mark.parametrize("transport", ["streamable_http", "streamableHttp"])
async def test_installed_sdk_round_trip(mcp_utils, mcp_http_server, transport):
    import anyio

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
