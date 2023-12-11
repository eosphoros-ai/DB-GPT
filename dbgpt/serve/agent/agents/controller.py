import logging
from fastapi import (
    APIRouter,
    Body,
    UploadFile,
    File,
)
from abc import ABC
from typing import List

from dbgpt.app.openapi.api_view_model import (
    Result,
)

from dbgpt.serve.agent.model import (
    PluginHubParam,
    PagenationFilter,
    PagenationResult,
    PluginHubFilter,
)

from dbgpt.configs.model_config import PLUGINS_DIR
from dbgpt.component import BaseComponent, ComponentType, SystemApp

router = APIRouter()
logger = logging.getLogger(__name__)


class MultiAgents(BaseComponent, ABC):
    name = ComponentType.MULTI_AGENTS

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Multi-Agents"])


multi_agents = MultiAgents()


@router.post("/v1/dbbgpts/agents/list", response_model=Result[str])
async def agents_list():
    pass

@router.post("/v1/dbbgpts/create", response_model=Result[str])
async def create_dbgpts(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass

@router.post("/v1/dbbgpts/chat/start", response_model=Result[str])
async def chat_start(user: str = None):
    pass


@router.post("/v1/dbbgpts/chat/completions", response_model=Result[str])
async def dgpts_completions(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass

@router.post("/v1/dbbgpts/chat/feedback", response_model=Result[str])
async def dgpts_chat_feedback(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass

