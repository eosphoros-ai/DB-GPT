"""Mixed public HTTP and ticket-authenticated WebSocket router wiring."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Depends, FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from dbgpt_serve.utils.auth import (
    _resolve_user,
    get_user_from_headers,
    v1_auth_middleware,
)

from ..identity import DashboardIdentityError, DBGPTUserIdentityProvider


def _router_has_http_dependency(name: str) -> bool:
    server = Path(__file__).resolve().parents[4] / "dbgpt_server.py"
    tree = ast.parse(server.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == name
        ):
            return any(keyword.arg == "dependencies" for keyword in node.keywords)
    raise AssertionError(f"Router {name} is not mounted")


@pytest.mark.parametrize("router_name", ["dashboard_router", "agentic_data_api"])
def test_mixed_router_has_no_global_http_dependency(router_name):
    assert not _router_has_http_dependency(router_name)


def test_ticket_websocket_works_with_locked_fastapi():
    router = APIRouter()

    @router.websocket("/v1/dashboards/{dashboard_id}/collaborate")
    async def collaborate(websocket: WebSocket, dashboard_id: str):
        if websocket.query_params.get("ticket") != "valid":
            await websocket.close(code=4401)
            return
        await websocket.accept()
        await websocket.send_text(dashboard_id)

    app = FastAPI()
    app.state.api_keys = ("key",)
    app.middleware("http")(v1_auth_middleware)
    dependencies = (
        [Depends(get_user_from_headers)]
        if _router_has_http_dependency("dashboard_router")
        else []
    )
    app.include_router(router, prefix="/api", dependencies=dependencies)
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/dashboards/example/collaborate?ticket=valid"
    ) as socket:
        assert socket.receive_text() == "example"
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/api/v1/dashboards/example/collaborate?ticket=invalid"
        ):
            pass
    assert exc.value.code == 4401


def test_development_identity_is_rejected_by_production_provider():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(api_keys=())))
    request.url = SimpleNamespace(path="/api/v1/dashboards")
    user = _resolve_user(request, None)
    assert DBGPTUserIdentityProvider().resolve(user) == "001"
    with pytest.raises(DashboardIdentityError):
        DBGPTUserIdentityProvider(allow_development_fallback=False).resolve(user)
