import logging

from fastapi import APIRouter

from dbgpt._private.config import Config
from dbgpt.agent.core.agent_manage import get_agent_manager
from dbgpt.agent.resource.manage import get_resource_manager
from dbgpt.agent.util.llm.llm import LLMStrategyType
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.serve.agent.app.gpts_server import available_llms
from dbgpt.serve.agent.db.gpts_app import (
    GptsApp,
    GptsAppCollectionDao,
    GptsAppDao,
    GptsAppQuery,
    GptsAppResponse,
)
from dbgpt.serve.agent.team.base import TeamMode

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)

gpts_dao = GptsAppDao()
collection_dao = GptsAppCollectionDao()


@router.post("/v1/app/create")
async def create(gpts_app: GptsApp):
    try:
        return Result.succ(gpts_dao.create(gpts_app))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"create app error: {ex}")


@router.post("/v1/app/list", response_model=Result[GptsAppResponse])
async def app_list(query: GptsAppQuery):
    try:
        return Result.succ(gpts_dao.app_list(query, True))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query app error: {ex}")


@router.post("/v1/app/detail")
async def app_list(gpts_app: GptsApp):
    try:
        return Result.succ(gpts_dao.app_detail(gpts_app.app_code))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query app error: {ex}")


@router.post("/v1/app/edit")
async def edit(gpts_app: GptsApp):
    try:
        return Result.succ(gpts_dao.edit(gpts_app))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"edit app error: {ex}")


@router.get("/v1/agents/list")
async def all_agents():
    try:
        return Result.succ(get_agent_manager().list_agents())
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query agents error: {ex}")


@router.post("/v1/app/remove")
async def delete(gpts_app: GptsApp):
    try:
        gpts_dao.delete(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ(None)
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"delete app error: {ex}")


@router.post("/v1/app/collect", response_model=Result[str])
async def collect(gpts_app: GptsApp):
    try:
        collection_dao.collect(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ([])
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"collect app error: {ex}")


@router.post("/v1/app/uncollect", response_model=Result[str])
async def uncollect(gpts_app: GptsApp):
    try:
        collection_dao.uncollect(
            gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code
        )
        return Result.succ([])
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"uncollect app error: {ex}")


@router.get("/v1/team-mode/list")
async def team_mode_list():
    try:
        return Result.succ([mode.value for mode in TeamMode])
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query team mode list error: {ex}")


@router.get("/v1/resource-type/list")
async def team_mode_list():
    try:
        resources = get_resource_manager().get_supported_resources(version="v1")
        return Result.succ(list(resources.keys()))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query resource type list error: {ex}")


@router.get("/v1/llm-strategy/list")
async def llm_strategies():
    try:
        return Result.succ([type.value for type in LLMStrategyType])
    except Exception as ex:
        return Result.failed(
            code="E000X", msg=f"query llm strategy type list error: {ex}"
        )


@router.get("/v1/llm-strategy/value/list")
async def llm_strategy_values(type: str):
    try:
        results = []
        match type:
            case LLMStrategyType.Priority.value:
                results = await available_llms()
        return Result.succ(results)
    except Exception as ex:
        return Result.failed(
            code="E000X", msg=f"query llm strategy type list error: {ex}"
        )


@router.get("/v1/app/resources/list", response_model=Result[list[str]])
async def app_resources(
    type: str, name: str = None, user_code: str = None, sys_code: str = None
):
    """
    Get agent resources, such as db, knowledge, internet, plugin.
    """
    try:
        resources = get_resource_manager().get_supported_resources("v1")
        results = resources.get(type, [])
        return Result.succ(results)
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query app resources error: {ex}")
