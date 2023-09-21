import json
import time
from fastapi import (
    APIRouter,
    Body,
    UploadFile,
    File,
)

from typing import List
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

from pilot.openapi.api_view_model import (
    Result,
)

from .model import PluginHubParam, PagenationFilter, PagenationResult, PluginHubFilter, MyPluginFilter
from .hub.agent_hub import AgentHub
from .db.plugin_hub_db import PluginHubEntity
from .db.my_plugin_db import MyPluginEntity
from pilot.configs.model_config import PLUGINS_DIR

router = APIRouter()
logger = build_logger("agent_mange", LOGDIR + "agent_mange.log")


@router.post("/api/v1/agent/hub/update", response_model=Result[str])
async def agent_hub_update(update_param: PluginHubParam = Body()):
    logger.info(f"agent_hub_update:{update_param.__dict__}")
    try:
        agent_hub = AgentHub(PLUGINS_DIR)
        agent_hub.refresh_hub_from_git(update_param.url, update_param.branch, update_param.authorization)
        return Result.succ(None)
    except Exception as e:
        logger.error("Agent Hub Update Error!", e)
        return Result.faild(code="E0020", msg=f"Agent Hub Update Error! {e}")



@router.post("/api/v1/agent/query", response_model=Result[str])
async def get_agent_list(filter: PagenationFilter[PluginHubFilter] = Body()):
    logger.info(f"get_agent_list:{json.dumps(filter)}")
    agent_hub = AgentHub(PLUGINS_DIR)
    filter_enetity:PluginHubEntity = PluginHubEntity()
    attrs = vars(filter.filter)  # 获取原始对象的属性字典
    for attr, value in attrs.items():
        setattr(filter_enetity, attr, value)  # 设置拷贝对象的属性值

    datas, total_pages, total_count = agent_hub.hub_dao.list(filter_enetity, filter.page_index, filter.page_size)
    result: PagenationResult[PluginHubEntity] = PagenationResult[PluginHubEntity]()
    result.page_index = filter.page_index
    result.page_size = filter.page_size
    result.total_page = total_pages
    result.total_row_count = total_count
    result.datas = datas
    return Result.succ(result)

@router.post("/api/v1/agent/my", response_model=Result[str])
async def my_agents(user:str= None):
    logger.info(f"my_agents:{json.dumps(my_agents)}")
    agent_hub = AgentHub(PLUGINS_DIR)
    return Result.succ(agent_hub.get_my_plugin(user))


@router.post("/api/v1/agent/install", response_model=Result[str])
async def agent_install(plugin_name:str, user: str = None):
    logger.info(f"agent_install:{plugin_name},{user}")
    try:
        agent_hub = AgentHub(PLUGINS_DIR)
        agent_hub.install_plugin(plugin_name, user)
        return Result.succ(None)
    except Exception  as e:
        logger.error("Plugin Install Error!", e)
        return Result.faild(code="E0021", msg=f"Plugin Install Error {e}")



@router.post("/api/v1/agent/uninstall", response_model=Result[str])
async def agent_uninstall(plugin_name:str, user: str = None):
    logger.info(f"agent_uninstall:{plugin_name},{user}")
    try:
        agent_hub = AgentHub(PLUGINS_DIR)
        agent_hub.uninstall_plugin(plugin_name, user)
        return Result.succ(None)
    except Exception  as e:
        logger.error("Plugin Uninstall Error!", e)
        return Result.faild(code="E0022", msg=f"Plugin Uninstall Error {e}")


@router.post("/api/v1/personal/agent/upload", response_model=Result[str])
async def personal_agent_upload( doc_file: UploadFile = File(...), user: str =None):
    logger.info(f"personal_agent_upload:{doc_file.filename},{user}")
    try:
        agent_hub = AgentHub(PLUGINS_DIR)
        agent_hub.upload_my_plugin(doc_file, user)
        return Result.succ(None)
    except Exception  as e:
        logger.error("Upload Personal Plugin Error!", e)
        return Result.faild(code="E0023", msg=f"Upload Personal Plugin Error {e}")

