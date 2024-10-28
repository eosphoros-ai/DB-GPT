import logging
from abc import ABC
from typing import List

from fastapi import APIRouter, Body, File, UploadFile

from dbgpt.agent.resource.tool.autogpt.plugins_util import scan_plugins
from dbgpt.agent.resource.tool.pack import AutoGPTPluginToolPack
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.configs.model_config import PLUGINS_DIR
from dbgpt.serve.agent.hub.plugin_hub import plugin_hub
from dbgpt.serve.agent.model import (
    PagenationFilter,
    PagenationResult,
    PluginHubFilter,
    PluginHubParam,
)

from .db.my_plugin_db import MyPluginEntity
from .db.plugin_hub_db import PluginHubEntity
from .model.model import MyPluginVO, PluginHubVO

router = APIRouter()
logger = logging.getLogger(__name__)


class ModulePlugin(BaseComponent, ABC):
    name = ComponentType.PLUGIN_HUB

    def __init__(self):
        # load plugins
        self.refresh_plugins()

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Agent"])

    def refresh_plugins(self):
        self.plugins = scan_plugins(PLUGINS_DIR)
        self.tools = AutoGPTPluginToolPack(PLUGINS_DIR)
        self.tools.preload_resource()


module_plugin = ModulePlugin()


@router.post("/v1/agent/hub/update", response_model=Result[str])
async def plugin_hub_update(update_param: PluginHubParam = Body()):
    logger.info(f"plugin_hub_update:{update_param.__dict__}")
    try:
        branch = (
            update_param.branch
            if update_param.branch is not None and len(update_param.branch) > 0
            else "main"
        )
        authorization = (
            update_param.authorization
            if update_param.branch is not None and len(update_param.branch) > 0
            else None
        )
        # TODO change it to async
        plugin_hub.refresh_hub_from_git(update_param.url, branch, authorization)
        return Result.succ(None)
    except Exception as e:
        logger.error("Agent Hub Update Error!", e)
        return Result.failed(code="E0020", msg=f"Agent Hub Update Error! {e}")


@router.post("/v1/agent/query", response_model=Result[dict])
async def get_agent_list(filter: PagenationFilter[PluginHubFilter] = Body()):
    logger.info(f"get_agent_list:{filter.__dict__}")
    filter_enetity: PluginHubEntity = PluginHubEntity()
    if filter.filter:
        attrs = vars(filter.filter)  # 获取原始对象的属性字典
        for attr, value in attrs.items():
            setattr(filter_enetity, attr, value)  # 设置拷贝对象的属性值

    datas, total_pages, total_count = plugin_hub.hub_dao.list(
        filter_enetity, filter.page_index, filter.page_size
    )
    result: PagenationResult[PluginHubVO] = PagenationResult[PluginHubVO]()
    result.page_index = filter.page_index
    result.page_size = filter.page_size
    result.total_page = total_pages
    result.total_row_count = total_count
    result.datas = PluginHubEntity.to_vo(datas)
    # print(json.dumps(result.to_dic()))
    return Result.succ(result.to_dic())


@router.post("/v1/agent/my", response_model=Result[List[MyPluginVO]])
async def my_agents(user: str = None):
    logger.info(f"my_agents:{user}")
    agents = plugin_hub.get_my_plugin(user)
    agent_dicts = MyPluginEntity.to_vo(agents)
    return Result.succ(agent_dicts)


@router.post("/v1/agent/install", response_model=Result[str])
async def agent_install(plugin_name: str, user: str = None):
    logger.info(f"agent_install:{plugin_name},{user}")
    try:
        plugin_hub.install_plugin(plugin_name, user)

        module_plugin.refresh_plugins()

        return Result.succ(None)
    except Exception as e:
        logger.error("Plugin Install Error!", e)
        return Result.failed(code="E0021", msg=f"Plugin Install Error {e}")


@router.post("/v1/agent/uninstall", response_model=Result[str])
async def agent_uninstall(plugin_name: str, user: str = None):
    logger.info(f"agent_uninstall:{plugin_name},{user}")
    try:
        plugin_hub.uninstall_plugin(plugin_name, user)

        module_plugin.refresh_plugins()
        return Result.succ(None)
    except Exception as e:
        logger.error("Plugin Uninstall Error!", e)
        return Result.failed(code="E0022", msg=f"Plugin Uninstall Error {e}")


@router.post("/v1/personal/agent/upload", response_model=Result[str])
async def personal_agent_upload(doc_file: UploadFile = File(...), user: str = None):
    logger.info(f"personal_agent_upload:{doc_file.filename},{user}")
    try:
        await plugin_hub.upload_my_plugin(doc_file, user)
        module_plugin.refresh_plugins()
        return Result.succ(None)
    except Exception as e:
        logger.error("Upload Personal Plugin Error!", e)
        return Result.failed(code="E0023", msg=f"Upload Personal Plugin Error {e}")
