from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.component import SystemApp
from dbgpt_serve.agent.hub.controller import module_plugin


def _make_client(api_keys: str | None = None) -> TestClient:
    app = FastAPI()
    system_app = SystemApp(app)
    if api_keys is not None:
        system_app.config.set("dbgpt.app.global.api_keys", api_keys)
    module_plugin.init_app(system_app)
    return TestClient(app)


def test_hub_update_requires_api_key_when_configured():
    client = _make_client(api_keys="valid-secret-key")
    with patch(
        "dbgpt_serve.agent.hub.controller.plugin_hub.refresh_hub_from_git"
    ) as mock_refresh:
        resp_no_auth = client.post(
            "/api/v1/agent/hub/update",
            json={"url": "https://github.com/owner/repo"},
        )
        assert resp_no_auth.status_code == 401
        mock_refresh.assert_not_called()

        resp_bad_auth = client.post(
            "/api/v1/agent/hub/update",
            headers={"Authorization": "Bearer wrong-key"},
            json={"url": "https://github.com/owner/repo"},
        )
        assert resp_bad_auth.status_code == 401
        mock_refresh.assert_not_called()

        resp_ok = client.post(
            "/api/v1/agent/hub/update",
            headers={"Authorization": "Bearer valid-secret-key"},
            json={
                "url": "https://github.com/owner/repo",
                "authorization": "token gh_pat",
            },
        )
        assert resp_ok.status_code == 200
        mock_refresh.assert_called_once_with(
            "https://github.com/owner/repo",
            "main",
            "token gh_pat",
        )


def test_hub_update_forwards_authorization_with_null_branch():
    client = _make_client(api_keys=None)
    with patch(
        "dbgpt_serve.agent.hub.controller.plugin_hub.refresh_hub_from_git"
    ) as mock_refresh:
        resp = client.post(
            "/api/v1/agent/hub/update",
            json={
                "url": "https://github.com/owner/repo",
                "branch": None,
                "authorization": "Bearer abc",
            },
        )
        assert resp.status_code == 200
        mock_refresh.assert_called_once_with(
            "https://github.com/owner/repo",
            "main",
            "Bearer abc",
        )
