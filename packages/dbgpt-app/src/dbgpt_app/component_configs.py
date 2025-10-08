import logging
from typing import Optional

from dbgpt.component import SystemApp
from dbgpt.configs.model_config import MODEL_DISK_CACHE_DIR, resolve_root_path
from dbgpt.util.executor_utils import DefaultExecutorFactory
from dbgpt_app.config import ApplicationConfig, ServiceWebParameters
from dbgpt_serve.rag.storage_manager import StorageManager

logger = logging.getLogger(__name__)


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
    system_app.register(DefaultScheduler)
    system_app.register_instance(controller)
    system_app.register(ConnectorManager)
    system_app.register(StorageManager)

    from dbgpt_serve.agent.hub.controller import module_plugin

    system_app.register_instance(module_plugin)

    from dbgpt_serve.agent.agents.controller import multi_agents

    system_app.register_instance(multi_agents)

    _initialize_embedding_model(system_app, default_embedding_name)
    _initialize_rerank_model(system_app, default_rerank_name)
    _initialize_model_cache(system_app, web_config)
    _initialize_awel(system_app, web_config.awel_dirs)
    # Initialize resource manager of agent
    _initialize_resource_manager(system_app)
    _initialize_agent(system_app)
    _initialize_openapi(system_app)
    # Register serve apps
    register_serve_apps(system_app, param, web_config.host, web_config.port)
    _initialize_operators()
    _initialize_code_server(system_app)
    # Initialize prompt templates - MUST be after serve apps registration
    _initialize_prompt_templates()
    _initialize_benchmark_data(system_app)


def _initialize_model_cache(system_app: SystemApp, web_config: ServiceWebParameters):
    from dbgpt.storage.cache import initialize_cache

    if not web_config.model_cache or not web_config.model_cache.enable_model_cache:
        logger.info("Model cache is not enable")
        return

    storage_type = web_config.model_cache.storage_type or "memory"
    max_memory_mb = web_config.model_cache.max_memory_mb or 256
    if web_config.model_cache.persist_dir:
        persist_dir = web_config.model_cache.persist_dir
    else:
        persist_dir = f"{MODEL_DISK_CACHE_DIR}_{web_config.port}"
    persist_dir = resolve_root_path(persist_dir)
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
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.resources.dbgpt_tool import list_dbgpt_support_models
    from dbgpt.agent.expand.resources.host_tool import (
        get_current_host_cpu_status,
        get_current_host_memory_status,
        get_current_host_system_load,
    )
    from dbgpt.agent.expand.resources.search_tool import baidu_search
    from dbgpt.agent.resource.base import ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager, initialize_resource
    from dbgpt_serve.agent.resource.app import GptAppResource
    from dbgpt_serve.agent.resource.datasource import DatasourceResource
    from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource
    from dbgpt_serve.agent.resource.mcp import MCPSSEToolPack
    from dbgpt_serve.agent.resource.plugin import PluginToolPack

    initialize_resource(system_app)
    rm = get_resource_manager(system_app)
    rm.register_resource(DatasourceResource)
    rm.register_resource(KnowledgeSpaceRetrieverResource)
    rm.register_resource(PluginToolPack, resource_type=ResourceType.Tool)
    rm.register_resource(GptAppResource)
    rm.register_resource(resource_instance=Terminate())
    # Register a search tool
    rm.register_resource(resource_instance=baidu_search)
    rm.register_resource(resource_instance=list_dbgpt_support_models)
    # Register host tools
    rm.register_resource(resource_instance=get_current_host_cpu_status)
    rm.register_resource(resource_instance=get_current_host_memory_status)
    rm.register_resource(resource_instance=get_current_host_system_load)
    # Register mcp tool
    rm.register_resource(MCPSSEToolPack, resource_type=ResourceType.Tool)


def _initialize_openapi(system_app: SystemApp):
    from dbgpt_app.openapi.api_v1.editor.service import EditorService

    system_app.register(EditorService)


def _initialize_operators():
    from dbgpt.core.awel import BaseOperator
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig

    modules = ["dbgpt_app.operators", "dbgpt_serve.agent.resource"]

    scanner = ModelScanner[BaseOperator]()
    registered_items = {}
    for module in modules:
        config = ScannerConfig(
            module_path=module,
            base_class=BaseOperator,
        )
        items = scanner.scan_and_register(config)
        registered_items[module] = items
    return scanner.get_registered_items()


def _initialize_code_server(system_app: SystemApp):
    from dbgpt.util.code.server import initialize_code_server

    initialize_code_server(system_app)


def _initialize_prompt_templates():
    """Initialize all prompt templates by importing scene modules.

    This ensures that all prompt templates are registered in the prompt registry
    before the application starts serving requests.
    """
    logger.info("Initializing prompt templates...")

    try:
        # Import all scene prompt modules to trigger registration
        # This is the same list as in ChatFactory.get_implementation()
        # Verify that templates are registered
        from dbgpt._private.config import Config
        from dbgpt_app.scene.chat_dashboard.prompt import prompt  # noqa: F401
        from dbgpt_app.scene.chat_data.chat_excel.excel_analyze.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_data.chat_excel.excel_learning.prompt import (  # noqa: F401, F811
            prompt,
        )
        from dbgpt_app.scene.chat_db.auto_execute.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_db.professional_qa.prompt import (  # noqa: F401, F811
            prompt,
        )
        from dbgpt_app.scene.chat_knowledge.refine_summary.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_knowledge.v1.prompt import prompt  # noqa: F401,F811
        from dbgpt_app.scene.chat_normal.prompt import prompt  # noqa: F401,F811

        cfg = Config()
        registry = cfg.prompt_template_registry.registry

        registered_scenes = list(registry.keys())
        logger.info(
            f"Successfully initialized prompt templates for scenes: {registered_scenes}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize prompt templates: {e}")
        # Don't raise exception to avoid breaking the application startup
        # The templates will be loaded lazily when needed


def _initialize_benchmark_data(system_app: SystemApp):
    from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
        initialize_benchmark_data,
    )

    initialize_benchmark_data(system_app)
