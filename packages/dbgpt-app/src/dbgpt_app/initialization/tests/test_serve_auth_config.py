"""Effective v1 API-key configuration for registered serves."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi import FastAPI

from dbgpt_serve.core import BaseServe


def _module(monkeypatch):
    datasource = ModuleType("dbgpt_serve.datasource.serve")
    config = ModuleType("dbgpt_app.config")
    config.ApplicationConfig = type("ApplicationConfig", (), {})
    monkeypatch.setitem(sys.modules, datasource.__name__, datasource)
    monkeypatch.setitem(sys.modules, config.__name__, config)
    path = Path(__file__).parents[1] / "serve_initialization.py"
    spec = importlib.util.spec_from_file_location("test_serve_auth_config_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_global_and_service_keys_are_combined_without_duplicates(monkeypatch):
    module = _module(monkeypatch)

    class Config:
        def __init__(self, api_keys=None):
            self.api_keys = api_keys

    existing = Config(api_keys="service,global")
    effective = module.get_config({"flow": existing}, "flow", Config, api_keys="global")
    assert effective.api_keys == "global,service"
    assert module.get_config({}, "flow", Config, api_keys="global").api_keys == "global"


def test_v1_prefixes_receive_only_their_effective_service_keys(monkeypatch):
    module = _module(monkeypatch)

    class RegisteredServe(BaseServe):
        def init_app(self, system_app):
            pass

    class FlowServe(RegisteredServe):
        pass

    FlowServe.__module__ = "dbgpt_serve.flow.serve"
    flow = object.__new__(FlowServe)
    flow._api_prefix = ["/api/v1/serve/awel", "/api/v2/serve/awel"]
    flow._config = SimpleNamespace(api_keys="global,flow")

    class FilesServe(RegisteredServe):
        pass

    FilesServe.__module__ = "dbgpt_serve.session_file.serve"
    files = object.__new__(FilesServe)
    files._api_prefix = "/api/v1/agent/files"
    files._serve_config = SimpleNamespace(api_keys="global,files")

    def flow_route():
        pass

    flow_route.__module__ = "dbgpt_serve.flow.api.endpoints"

    def files_route():
        pass

    files_route.__module__ = "dbgpt_serve.session_file.api.endpoints"

    def legacy_download():
        pass

    legacy_download.__module__ = "dbgpt_app.openapi.api_v1.agentic_data_api"
    app = FastAPI()
    app.state.api_keys = ("global",)
    app.add_api_route("/api/v1/agent/files/download", legacy_download)
    app.add_api_route("/api/v1/serve/awel/flows", flow_route)
    app.add_api_route("/api/v1/agent/files/{file_id}", files_route)
    app.add_api_route("/api/v2/serve/awel/flows", flow_route)

    routes = module._v1_api_key_routes(app, {"flow": flow, "files": files})
    key_map = {
        route.path: keys
        for route, (_, _, keys) in zip(
            (route for route in app.routes if route.path.startswith("/api/v1/")),
            routes,
        )
    }
    assert key_map == {
        "/api/v1/agent/files/download": ("global",),
        "/api/v1/serve/awel/flows": ("global", "flow"),
        "/api/v1/agent/files/{file_id}": ("global", "files"),
    }
