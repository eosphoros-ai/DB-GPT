from __future__ import annotations

import logging
from typing import Optional

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import MODEL_DISK_CACHE_DIR
from dbgpt.util.executor_utils import DefaultExecutorFactory
from dbgpt_app.config import ApplicationConfig

logger = logging.getLogger(__name__)

CFG = Config()


def initialize_components(
    param: ApplicationConfig,
    system_app: SystemApp,
):
    # Lazy import to avoid high time cost
    from dbgpt.model.cluster.controller.controller import controller
    from dbgpt_app.initialization.embedding_component import (
        _initialize_embedding_model,
        _initialize_rerank_model,
    )
    from dbgpt_app.initialization.scheduler import DefaultScheduler
    from dbgpt_app.initialization.serve_initialization import register_serve_apps
    from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

    web_config = param.service.web
    default_embedding_name = param.models.default_embedding
    default_rerank_name = param.models.default_reranker

    # Register global default executor factory first
    system_app.register(
        DefaultExecutorFactory, max_workers=web_config.default_thread_pool_size
    )
    system_app.register(DefaultScheduler, scheduler_enable=CFG.SCHEDULER_ENABLED)
    system_app.register_instance(controller)
    system_app.register(ConnectorManager)

    from dbgpt_serve.agent.hub.controller import module_plugin

    system_app.register_instance(module_plugin)

    from dbgpt_serve.agent.agents.controller import multi_agents

    system_app.register_instance(multi_agents)

    _initialize_embedding_model(system_app, default_embedding_name)
    _initialize_rerank_model(system_app, default_rerank_name)
    _initialize_model_cache(system_app, web_config.port)
    _initialize_awel(system_app, web_config.awel_dirs)
    # Initialize resource manager of agent
    _initialize_resource_manager(system_app)
    _initialize_agent(system_app)
    _initialize_openapi(system_app)
    # Register serve apps
    register_serve_apps(system_app, CFG, web_config.port)
    _initialize_operators()
    _initialize_code_server(system_app)


def _initialize_model_cache(system_app: SystemApp, port: int):
    from dbgpt.storage.cache import initialize_cache

    if not CFG.MODEL_CACHE_ENABLE:
        logger.info("Model cache is not enable")
        return

    storage_type = CFG.MODEL_CACHE_STORAGE_TYPE or "disk"
    max_memory_mb = CFG.MODEL_CACHE_MAX_MEMORY_MB or 256
    persist_dir = CFG.MODEL_CACHE_STORAGE_DISK_DIR or MODEL_DISK_CACHE_DIR
    if CFG.WEBSERVER_MULTI_INSTANCE:
        persist_dir = f"{persist_dir}_{port}"
    initialize_cache(system_app, storage_type, max_memory_mb, persist_dir)


def _initialize_awel(system_app: SystemApp, awel_dirs: Optional[str] = None):
    from dbgpt.configs.model_config import _DAG_DEFINITION_DIR
    from dbgpt.core.awel import initialize_awel

    # Add default dag definition dir
    dag_dirs = [_DAG_DEFINITION_DIR]
    if awel_dirs:
        dag_dirs += awel_dirs.strip().split(",")
    dag_dirs = [x.strip() for x in dag_dirs]

    initialize_awel(system_app, dag_dirs)


def _initialize_agent(system_app: SystemApp):
    from dbgpt.agent import initialize_agent

    initialize_agent(system_app)


def _initialize_resource_manager(system_app: SystemApp):
    from dbgpt.agent.expand.resources.dbgpt_tool import list_dbgpt_support_models
    from dbgpt.agent.expand.resources.host_tool import (
        get_current_host_cpu_status,
        get_current_host_memory_status,
        get_current_host_system_load,
    )
    from dbgpt.agent.expand.resources.search_tool import baidu_search
    from dbgpt.agent.resource.app import AppResource
    from dbgpt.agent.resource.base import ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager, initialize_resource
    from dbgpt_serve.agent.resource.datasource import DatasourceResource
    from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource
    from dbgpt_serve.agent.resource.plugin import PluginToolPack

    initialize_resource(system_app)
    rm = get_resource_manager(system_app)
    rm.register_resource(DatasourceResource)
    rm.register_resource(KnowledgeSpaceRetrieverResource)
    rm.register_resource(PluginToolPack, resource_type=ResourceType.Tool)
    rm.register_resource(AppResource)
    # Register a search tool
    rm.register_resource(resource_instance=baidu_search)
    rm.register_resource(resource_instance=list_dbgpt_support_models)
    # Register host tools
    rm.register_resource(resource_instance=get_current_host_cpu_status)
    rm.register_resource(resource_instance=get_current_host_memory_status)
    rm.register_resource(resource_instance=get_current_host_system_load)


def _initialize_openapi(system_app: SystemApp):
    from dbgpt_app.openapi.api_v1.editor.service import EditorService

    system_app.register(EditorService)


def _initialize_operators():
    from dbgpt_app.operators.code import CodeMapOperator  # noqa: F401
    from dbgpt_app.operators.converter import StringToInteger  # noqa: F401
    from dbgpt_app.operators.datasource import (  # noqa: F401
        HODatasourceExecutorOperator,
        HODatasourceRetrieverOperator,
    )
    from dbgpt_app.operators.llm import (  # noqa: F401
        HOLLMOperator,
        HOStreamingLLMOperator,
    )
    from dbgpt_app.operators.rag import HOKnowledgeOperator  # noqa: F401
    from dbgpt_serve.agent.resource.datasource import DatasourceResource  # noqa: F401


def _initialize_code_server(system_app: SystemApp):
    from dbgpt.util.code.server import initialize_code_server

    initialize_code_server(system_app)
