from __future__ import annotations

import logging
from typing import Optional

from dbgpt._private.config import Config
from dbgpt.app.base import WebServerParameters
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import MODEL_DISK_CACHE_DIR
from dbgpt.util.executor_utils import DefaultExecutorFactory

logger = logging.getLogger(__name__)

CFG = Config()


def initialize_components(
    param: WebServerParameters,
    system_app: SystemApp,
    embedding_model_name: str,
    embedding_model_path: str,
    rerank_model_name: Optional[str] = None,
    rerank_model_path: Optional[str] = None,
):
    # Lazy import to avoid high time cost
    from dbgpt.app.initialization.embedding_component import (
        _initialize_embedding_model,
        _initialize_rerank_model,
    )
    from dbgpt.app.initialization.scheduler import DefaultScheduler
    from dbgpt.app.initialization.serve_initialization import register_serve_apps
    from dbgpt.datasource.manages.connector_manager import ConnectorManager
    from dbgpt.model.cluster.controller.controller import controller

    # Register global default executor factory first
    system_app.register(
        DefaultExecutorFactory, max_workers=param.default_thread_pool_size
    )
    system_app.register(DefaultScheduler, scheduler_enable=CFG.SCHEDULER_ENABLED)
    system_app.register_instance(controller)
    system_app.register(ConnectorManager)

    from dbgpt.serve.agent.hub.controller import module_plugin

    system_app.register_instance(module_plugin)

    from dbgpt.serve.agent.agents.controller import multi_agents

    system_app.register_instance(multi_agents)

    _initialize_embedding_model(
        param, system_app, embedding_model_name, embedding_model_path
    )
    _initialize_rerank_model(param, system_app, rerank_model_name, rerank_model_path)
    _initialize_model_cache(system_app, param.port)
    _initialize_awel(system_app, param)
    # Initialize resource manager of agent
    _initialize_resource_manager(system_app)
    _initialize_agent(system_app)
    _initialize_openapi(system_app)
    # Register serve apps
    register_serve_apps(system_app, CFG, param.port)
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


def _initialize_awel(system_app: SystemApp, param: WebServerParameters):
    from dbgpt.configs.model_config import _DAG_DEFINITION_DIR
    from dbgpt.core.awel import initialize_awel

    # Add default dag definition dir
    dag_dirs = [_DAG_DEFINITION_DIR]
    if param.awel_dirs:
        dag_dirs += param.awel_dirs.strip().split(",")
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
    from dbgpt.agent.resource.base import ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager, initialize_resource
    from dbgpt.serve.agent.resource.datasource import DatasourceResource
    from dbgpt.serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource
    from dbgpt.serve.agent.resource.plugin import PluginToolPack

    initialize_resource(system_app)
    rm = get_resource_manager(system_app)
    rm.register_resource(DatasourceResource)
    rm.register_resource(KnowledgeSpaceRetrieverResource)
    rm.register_resource(PluginToolPack, resource_type=ResourceType.Tool)
    # Register a search tool
    rm.register_resource(resource_instance=baidu_search)
    rm.register_resource(resource_instance=list_dbgpt_support_models)
    # Register host tools
    rm.register_resource(resource_instance=get_current_host_cpu_status)
    rm.register_resource(resource_instance=get_current_host_memory_status)
    rm.register_resource(resource_instance=get_current_host_system_load)


def _initialize_openapi(system_app: SystemApp):
    from dbgpt.app.openapi.api_v1.editor.service import EditorService

    system_app.register(EditorService)


def _initialize_operators():
    from dbgpt.app.operators.code import CodeMapOperator
    from dbgpt.app.operators.converter import StringToInteger
    from dbgpt.app.operators.datasource import (
        HODatasourceExecutorOperator,
        HODatasourceRetrieverOperator,
    )
    from dbgpt.app.operators.llm import HOLLMOperator, HOStreamingLLMOperator
    from dbgpt.app.operators.rag import HOKnowledgeOperator
    from dbgpt.serve.agent.resource.datasource import DatasourceResource


def _initialize_code_server(system_app: SystemApp):
    from dbgpt.util.code.server import initialize_code_server

    initialize_code_server(system_app)
