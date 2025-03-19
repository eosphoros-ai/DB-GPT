from typing import TYPE_CHECKING, Dict, Optional, Type, TypeVar

import dbgpt_serve.datasource.serve
from dbgpt.component import SystemApp
from dbgpt_app.config import ApplicationConfig

if TYPE_CHECKING:
    from dbgpt_serve.core import BaseServeConfig

T = TypeVar("T", bound="BaseServeConfig")


def scan_serve_configs():
    """Scan serve configs."""
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig
    from dbgpt_serve.core import BaseServeConfig

    modules = [
        "dbgpt_serve.agent.chat",
        "dbgpt_serve.conversation",
        "dbgpt_serve.datasource",
        "dbgpt_serve.dbgpts.hub",
        "dbgpt_serve.dbgpts.my",
        "dbgpt_serve.evaluate",
        "dbgpt_serve.feedback",
        "dbgpt_serve.file",
        "dbgpt_serve.flow",
        "dbgpt_serve.libro",
        "dbgpt_serve.model",
        "dbgpt_serve.prompt",
        "dbgpt_serve.rag",
    ]

    scanner = ModelScanner[BaseServeConfig]()
    registered_items = {}
    for module in modules:
        config = ScannerConfig(
            module_path=module,
            base_class=BaseServeConfig,
            specific_files=["config"],
        )
        items = scanner.scan_and_register(config)
        registered_items[module] = items
    return registered_items


def get_config(
    serve_configs: Dict[str, T], serve_name: str, config_type: Type[T], **default_config
) -> T:
    """
    Get serve config with specific type

    Args:
        serve_configs: Dictionary of serve configs
        serve_name: Name of the serve config to get
        config_type: The specific config type to return
        **default_config: Default values for config attributes

    Returns:
        Config instance of type T
    """
    if hasattr(config_type, "__type__"):
        # Use the type name as the serve name
        serve_name = config_type.__type__

    config = serve_configs.get(serve_name)
    if not config:
        config = config_type(**default_config)
    else:
        if default_config:
            for k, v in default_config.items():
                if hasattr(config, k) and getattr(config, k) is None:
                    setattr(config, k, v)
    return config


def register_serve_apps(
    system_app: SystemApp,
    app_config: ApplicationConfig,
    webserver_host: str,
    webserver_port: int,
):
    """Register serve apps"""
    serve_configs = {s.get_type_value(): s for s in app_config.serves}

    system_app.config.set("dbgpt.app.global.language", app_config.system.language)
    global_api_keys: Optional[str] = None
    if app_config.system.api_keys:
        global_api_keys = ",".join(app_config.system.api_keys)
        system_app.config.set("dbgpt.app.global.api_keys", global_api_keys)
    if app_config.system.encrypt_key:
        system_app.config.set(
            "dbgpt.app.global.encrypt_key", app_config.system.encrypt_key
        )

    # ################################ Prompt Serve Register Begin ####################
    from dbgpt_serve.prompt.serve import (
        Serve as PromptServe,
    )

    # Register serve app
    system_app.register(
        PromptServe,
        api_prefix="/prompt",
        config=get_config(
            serve_configs,
            PromptServe.name,
            dbgpt_serve.prompt.serve.ServeConfig,
            default_user="dbgpt",
            default_sys_code="dbgpt",
            api_keys=global_api_keys,
        ),
    )
    # ################################ Prompt Serve Register End ######################

    # ################################ Conversation Serve Register Begin ##############
    from dbgpt_serve.conversation.serve import Serve as ConversationServe

    # Register serve app
    system_app.register(
        ConversationServe,
        api_prefix="/api/v1/chat/dialogue",
        config=get_config(
            serve_configs,
            ConversationServe.name,
            dbgpt_serve.conversation.serve.ServeConfig,
            default_model=app_config.models.default_llm,
            api_keys=global_api_keys,
        ),
    )
    # ################################ Conversation Serve Register End ################

    # ################################ AWEL Flow Serve Register Begin #################
    from dbgpt_serve.flow.serve import Serve as FlowServe

    # Register serve app
    system_app.register(
        FlowServe,
        config=get_config(
            serve_configs,
            FlowServe.name,
            dbgpt_serve.flow.serve.ServeConfig,
            encrypt_key=app_config.system.encrypt_key,
            api_keys=global_api_keys,
        ),
    )

    # ################################ AWEL Flow Serve Register End ###################

    # ################################ Rag Serve Register Begin #######################

    from dbgpt_serve.rag.serve import Serve as RagServe

    rag_config = app_config.rag
    llm_configs = app_config.models

    # Register serve app
    system_app.register(
        RagServe,
        config=get_config(
            serve_configs,
            RagServe.name,
            dbgpt_serve.rag.serve.ServeConfig,
            embedding_model=llm_configs.default_embedding,
            rerank_model=llm_configs.default_reranker,
            chunk_size=rag_config.chunk_size,
            chunk_overlap=rag_config.chunk_overlap,
            similarity_top_k=rag_config.similarity_top_k,
            query_rewrite=rag_config.query_rewrite,
            max_chunks_once_load=rag_config.max_chunks_once_load,
            max_threads=rag_config.max_threads,
            rerank_top_k=rag_config.rerank_top_k,
            api_keys=global_api_keys,
        ),
    )

    # ################################ Rag Serve Register End #########################

    # ################################ Datasource Serve Register Begin ################

    from dbgpt_serve.datasource.serve import Serve as DatasourceServe

    # Register serve app
    system_app.register(
        DatasourceServe,
        config=get_config(
            serve_configs,
            DatasourceServe.name,
            dbgpt_serve.datasource.serve.ServeConfig,
            api_keys=global_api_keys,
        ),
    )

    # ################################ Datasource Serve Register End ##################

    # ################################ Chat Feedback Serve Register End ###############
    from dbgpt_serve.feedback.serve import Serve as FeedbackServe

    # Register serve feedback
    system_app.register(
        FeedbackServe,
        config=get_config(
            serve_configs,
            FeedbackServe.name,
            dbgpt_serve.feedback.serve.ServeConfig,
            api_keys=global_api_keys,
        ),
    )
    # ################################ Chat Feedback Register End #####################

    # ################################ DbGpts Register Begin ##########################
    # Register serve dbgptshub
    from dbgpt_serve.dbgpts.hub.serve import Serve as DbgptsHubServe

    system_app.register(
        DbgptsHubServe,
        config=get_config(
            serve_configs,
            DbgptsHubServe.name,
            dbgpt_serve.dbgpts.hub.serve.ServeConfig,
            api_keys=global_api_keys,
        ),
    )
    # Register serve dbgptsmy
    from dbgpt_serve.dbgpts.my.serve import Serve as DbgptsMyServe

    system_app.register(
        DbgptsMyServe,
        config=get_config(
            serve_configs,
            DbgptsMyServe.name,
            dbgpt_serve.dbgpts.my.serve.ServeConfig,
            api_keys=global_api_keys,
        ),
    )
    # ################################ DbGpts Register End ############################

    # ################################ File Serve Register Begin ######################

    from dbgpt.configs.model_config import FILE_SERVER_LOCAL_STORAGE_PATH
    from dbgpt_serve.file.serve import Serve as FileServe

    local_storage_path = f"{FILE_SERVER_LOCAL_STORAGE_PATH}_{webserver_port}"
    # Register serve app
    system_app.register(
        FileServe,
        config=get_config(
            serve_configs,
            FileServe.name,
            dbgpt_serve.file.serve.ServeConfig,
            host=webserver_host,
            port=webserver_port,
            local_storage_path=local_storage_path,
            api_keys=global_api_keys,
        ),
    )

    # ################################ File Serve Register End ########################

    # ################################ Evaluate Serve Register Begin ##################
    from dbgpt_serve.evaluate.serve import Serve as EvaluateServe

    rag_config = app_config.rag
    llm_configs = app_config.models
    # Register serve Evaluate
    system_app.register(
        EvaluateServe,
        config=get_config(
            serve_configs,
            EvaluateServe.name,
            dbgpt_serve.evaluate.serve.ServeConfig,
            embedding_model=llm_configs.default_embedding,
            similarity_top_k=rag_config.similarity_top_k,
            api_keys=global_api_keys,
        ),
    )
    # ################################ Evaluate Serve Register End ####################

    # ################################ Libro Serve Register Begin #####################
    from dbgpt_serve.libro.serve import Serve as LibroServe

    # Register serve libro
    system_app.register(
        LibroServe,
        config=get_config(
            serve_configs,
            LibroServe.name,
            dbgpt_serve.libro.serve.ServeConfig,
            api_keys=global_api_keys,
        ),
    )

    # ################################ Libro Serve Register End #######################

    # ################################ Model Serve Register Begin #####################
    from dbgpt_serve.model.serve import Serve as ModelServe

    # Register serve model
    system_app.register(
        ModelServe,
        config=get_config(
            serve_configs,
            ModelServe.name,
            dbgpt_serve.model.serve.ServeConfig,
            model_storage=app_config.service.web.model_storage,
            api_keys=global_api_keys,
        ),
    )
