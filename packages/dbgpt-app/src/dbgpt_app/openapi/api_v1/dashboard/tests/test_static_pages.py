"""Direct navigation to exported Dashboard pages must work with Python hosting."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.util.fastapi import replace_router
from dbgpt_app import dbgpt_server


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    web = tmp_path / "static" / "web"
    (web / "_next" / "static").mkdir(parents=True)
    for relative, content in {
        "dashboards/index.html": "dashboard list",
        "dashboards/new/index.html": "create dashboard",
        "dashboards/[id]/index.html": "dashboard editor",
        "dashboard-share/[token]/index.html": "published dashboard",
        "share/[token]/index.html": "conversation share",
    }.items():
        page = web / relative
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(content, encoding="utf-8")

    monkeypatch.setattr(dbgpt_server, "__file__", str(tmp_path / "dbgpt_server.py"))
    monkeypatch.setattr(
        dbgpt_server, "STATIC_MESSAGE_IMG_PATH", str(tmp_path / "images")
    )
    app = FastAPI()
    replace_router(app)

    @app.get("/api/v1/dashboards/{dashboard_id}")
    async def dashboard_api(dashboard_id: str):
        return {"id": dashboard_id}

    config = SimpleNamespace(
        service=SimpleNamespace(web=SimpleNamespace(new_web_ui=True))
    )
    dbgpt_server.mount_static_files(app, config)
    with TestClient(app) as client:
        yield client, web


@pytest.mark.parametrize("suffix", ["", "/"])
@pytest.mark.parametrize(
    "route,expected",
    [
        ("/dashboards/new", "create dashboard"),
        ("/dashboards/saved-dashboard", "dashboard editor"),
        ("/dashboard-share/fixed-token", "published dashboard"),
        ("/share/conversation-token", "conversation share"),
    ],
)
def test_direct_exported_page_navigation(static_client, route, expected, suffix):
    client, _ = static_client
    response = client.get(route + suffix)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == expected


def test_dashboard_static_routes_preserve_list_and_api(static_client):
    client, _ = static_client
    assert client.get("/dashboards/").text == "dashboard list"
    response = client.get("/api/v1/dashboards/saved-dashboard")
    assert response.status_code == 200
    assert response.json() == {"id": "saved-dashboard"}


@pytest.mark.parametrize(
    "route,relative",
    [
        ("/dashboards/new/", "dashboards/new/index.html"),
        ("/dashboards/saved-dashboard/", "dashboards/[id]/index.html"),
        ("/dashboard-share/fixed-token/", "dashboard-share/[token]/index.html"),
    ],
)
def test_missing_exported_dashboard_page_is_404(static_client, route, relative):
    client, web = static_client
    (web / relative).unlink()
    assert client.get(route).status_code == 404
