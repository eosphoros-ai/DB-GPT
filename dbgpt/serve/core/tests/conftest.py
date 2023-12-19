import pytest
import pytest_asyncio
from typing import Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient

from dbgpt.component import SystemApp
from dbgpt.util import AppConfig

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def create_system_app(param: Dict) -> SystemApp:
    app_config = param.get("app_config", {})
    if isinstance(app_config, dict):
        app_config = AppConfig(configs=app_config)
    elif not isinstance(app_config, AppConfig):
        raise RuntimeError("app_config must be AppConfig or dict")
    return SystemApp(app, app_config)


@pytest_asyncio.fixture
async def asystem_app(request):
    param = getattr(request, "param", {})
    return create_system_app(param)


@pytest.fixture
def system_app(request):
    param = getattr(request, "param", {})
    return create_system_app(param)


@pytest_asyncio.fixture
async def client(request, asystem_app: SystemApp):
    param = getattr(request, "param", {})
    headers = param.get("headers", {})
    base_url = param.get("base_url", "http://test")
    client_api_key = param.get("client_api_key")
    routers = param.get("routers", [])
    app_caller = param.get("app_caller")
    if "api_keys" in param:
        del param["api_keys"]
    if client_api_key:
        headers["Authorization"] = "Bearer " + client_api_key
    async with AsyncClient(app=app, base_url=base_url, headers=headers) as client:
        for router in routers:
            app.include_router(router)
        if app_caller:
            app_caller(app, asystem_app)
        yield client
