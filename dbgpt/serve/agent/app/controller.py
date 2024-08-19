import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends

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
    native_app_params,
)
from dbgpt.serve.agent.team.base import TeamMode
from dbgpt.serve.utils.auth import UserRequest, get_user_from_headers

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)

gpts_dao = GptsAppDao()
collection_dao = GptsAppCollectionDao()


@router.post("/v1/app/create")
async def create(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        return Result.succ(gpts_dao.create(gpts_app))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"create app error: {ex}")


@router.post("/v1/app/list")
async def app_list(
    query: GptsAppQuery, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        # query.user_code = (
        #     user_info.user_id if user_info.user_id is not None else query.user_code
        # )
        query.ignore_user = "true"
        return Result.succ(gpts_dao.app_list(query, True))
    except Exception as ex:
        logger.exception("app_list exception!")
        return Result.failed(code="E000X", msg=f"query app list error: {ex}")


@router.get("/v1/app/info")
async def app_detail(
    chat_scene: str,
    app_code: str = None,
):
    logger.info(f"app_detail:{chat_scene},{app_code}")
    try:
        if app_code:
            return Result.succ(gpts_dao.app_detail(app_code))
        else:
            from dbgpt.app.scene.base import ChatScene

            scene: ChatScene = ChatScene.of_mode(chat_scene)
            return Result.succ(gpts_dao.native_app_detail(scene.scene_name()))
    except Exception as ex:
        logger.exception("query app detail error!")
        return Result.failed(code="E000X", msg=f"query app detail error: {ex}")


@router.get("/v1/app/export")
async def app_export(
    chat_scene: str,
    app_code: str = None,
):
    logger.info(f"app_export:{app_code}")
    try:
        if app_code:
            app_info = gpts_dao.app_detail(app_code)
        else:
            from dbgpt.app.scene.base import ChatScene

            scene: ChatScene = ChatScene.of_mode(chat_scene)
            app_info = gpts_dao.native_app_detail(scene.scene_name())

        return Result.succ(app_info)
    except Exception as ex:
        logger.exception("export app info error!")
        return Result.failed(code="E000X", msg=f"export app info error: {ex}")


@router.get("/v1/app/{app_code}")
async def get_app_by_code(
    app_code: str,
):
    try:
        return Result.succ(gpts_dao.app_detail(app_code))
    except Exception as ex:
        logger.exception("query app detail error!")
        return Result.failed(code="E000X", msg=f"query app detail error: {ex}")


@router.post("/v1/app/hot/list")
async def hot_app_list(
    query: GptsAppQuery, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        query.user_code = (
            user_info.user_id if user_info.user_id is not None else query.user_code
        )
        list_hot_apps = gpts_dao.list_hot_apps(query)
        return Result.succ(list_hot_apps)
    except Exception as ex:
        logger.exception("hot_app_list exception！")
        return Result.failed(code="E000X", msg=f"query hot app error: {ex}")


@router.post("/v1/app/detail")
async def app_list(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        return Result.succ(gpts_dao.app_detail(gpts_app.app_code))
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query app error: {ex}")


@router.post("/v1/app/edit")
async def edit(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        return Result.succ(gpts_dao.edit(gpts_app))
    except Exception as ex:
        logger.exception(" app edit exception!")
        return Result.failed(code="E000X", msg=f"edit app error: {ex}")


@router.get("/v1/agents/list")
async def all_agents(user_info: UserRequest = Depends(get_user_from_headers)):
    try:
        agents = get_agent_manager().list_agents()
        for agent in agents:
            label = agent["name"]
            agent["label"] = label
        return Result.succ(agents)
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"query agents error: {ex}")


@router.post("/v1/app/remove", response_model=Result)
async def delete(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        gpts_dao.delete(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ()
    except Exception as ex:
        logger.exception("app remove exception!")
        return Result.failed(code="E000X", msg=f"delete app error: {ex}")


@router.post("/v1/app/collect", response_model=Result)
async def collect(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        collection_dao.collect(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ()
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"collect app error: {ex}")


@router.post("/v1/app/uncollect", response_model=Result)
async def uncollect(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        collection_dao.uncollect(
            gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code
        )
        return Result.succ()
    except Exception as ex:
        return Result.failed(code="E000X", msg=f"uncollect app error: {ex}")


@router.get("/v1/team-mode/list")
async def team_mode_list(user_info: UserRequest = Depends(get_user_from_headers)):
    try:
        return Result.succ([mode.to_dict() for mode in TeamMode])
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(code="E000X", msg=f"query team mode list error: {ex}")


@router.get("/v1/resource-type/list")
async def team_mode_list(user_info: UserRequest = Depends(get_user_from_headers)):
    try:
        resources = get_resource_manager().get_supported_resources_type()
        return Result.succ(resources)
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(code="E000X", msg=f"query resource type list error: {ex}")


@router.get("/v1/llm-strategy/list")
async def llm_strategies(user_info: UserRequest = Depends(get_user_from_headers)):
    try:
        return Result.succ([type.to_dict() for type in LLMStrategyType])
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(
            code="E000X", msg=f"query llm strategy type list error: {ex}"
        )


@router.get("/v1/llm-strategy/value/list")
async def llm_strategy_values(
    type: str, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        results = []
        match type:
            case LLMStrategyType.Priority.value:
                results = await available_llms()
        return Result.succ(results)
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(
            code="E000X", msg=f"query llm strategy type list error: {ex}"
        )


@router.get("/v1/app/resources/list", response_model=Result)
async def app_resources(
    type: str,
    name: Optional[str] = None,
    user_code: Optional[str] = None,
    sys_code: Optional[str] = None,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    """
    Get agent resources, such as db, knowledge, internet, plugin.
    """
    try:
        resources = get_resource_manager().get_supported_resources(
            version="v1", type=type, user_id=None
        )
        results = resources.get(type, [])
        return Result.succ(results)
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(code="E000X", msg=f"query app resources error: {ex}")


@router.post("/v1/app/publish", response_model=Result)
async def publish(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        gpts_dao.publish(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ([])
    except Exception as ex:
        logger.exception(str(ex))
        return Result.failed(code="E000X", msg=f"publish app error: {ex}")


@router.post("/v1/app/unpublish", response_model=Result)
async def unpublish(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        gpts_app.user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        gpts_dao.unpublish(gpts_app.app_code, gpts_app.user_code, gpts_app.sys_code)
        return Result.succ([])
    except Exception as ex:
        logger.exception("unpublish:" + str(ex))
        return Result.failed(code="E000X", msg=f"unpublish app error: {ex}")


@router.post("/v1/app/native/init", response_model=Result)
async def init_native_apps(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    try:
        user_code = (
            user_info.user_id if user_info.user_id is not None else gpts_app.user_code
        )
        gpts_dao.init_native_apps(user_code)
        return Result.succ([])
    except Exception as ex:
        logger.exception("init natove error!")
        return Result.failed(code="E000X", msg=f"init natove error: {ex}")


@router.get("/v1/native_scenes")
async def native_scenes(user_info: UserRequest = Depends(get_user_from_headers)):
    return Result.succ(native_app_params())


@router.post("/v1/app/admins/update")
def update_admins(
    gpts_app: GptsApp, user_info: UserRequest = Depends(get_user_from_headers)
):
    return Result.succ(gpts_dao.update_admins(gpts_app.app_code, gpts_app.admins))


@router.get("/v1/app/{app_code}/admins")
async def query_admins(
    app_code: str,
    user_info: UserRequest = Depends(get_user_from_headers),
):
    try:
        return Result.succ(gpts_dao.get_admins(app_code))
    except Exception as ex:
        logger.exception("query_admins:" + str(ex))
        return Result.failed(code="E000X", msg=f"query admins error: {ex}")


@router.get("/v1/dbgpts/list", response_model=Result[List[GptsApp]])
async def get_dbgpts(user_code: str = None, sys_code: str = None):
    logger.info(f"get_dbgpts:{user_code},{sys_code}")
    try:
        query: GptsAppQuery = GptsAppQuery()
        query.ignore_user = "true"
        response = gpts_dao.app_list(query, True)
        return Result.succ(response.app_list)
    except Exception as e:
        logger.error(f"get_dbgpts failed:{str(e)}")
        return Result.failed(msg=str(e), code="E300003")
