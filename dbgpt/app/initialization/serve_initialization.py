from dbgpt._private.config import Config
from dbgpt.component import SystemApp


def register_serve_apps(system_app: SystemApp, cfg: Config):
    """Register serve apps"""
    system_app.config.set("dbgpt.app.global.language", cfg.LANGUAGE)
    if cfg.API_KEYS:
        system_app.config.set("dbgpt.app.global.api_keys", cfg.API_KEYS)

    # ################################ Prompt Serve Register Begin ######################################
    from dbgpt.serve.prompt.serve import (
        SERVE_CONFIG_KEY_PREFIX as PROMPT_SERVE_CONFIG_KEY_PREFIX,
    )
    from dbgpt.serve.prompt.serve import Serve as PromptServe

    # Replace old prompt serve
    # Set config
    system_app.config.set(f"{PROMPT_SERVE_CONFIG_KEY_PREFIX}default_user", "dbgpt")
    system_app.config.set(f"{PROMPT_SERVE_CONFIG_KEY_PREFIX}default_sys_code", "dbgpt")
    # Register serve app
    system_app.register(PromptServe, api_prefix="/prompt")
    # ################################ Prompt Serve Register End ########################################

    # ################################ Conversation Serve Register Begin ######################################
    from dbgpt.serve.conversation.serve import (
        SERVE_CONFIG_KEY_PREFIX as CONVERSATION_SERVE_CONFIG_KEY_PREFIX,
    )
    from dbgpt.serve.conversation.serve import Serve as ConversationServe

    # Set config
    system_app.config.set(
        f"{CONVERSATION_SERVE_CONFIG_KEY_PREFIX}default_model", cfg.LLM_MODEL
    )
    # Register serve app
    system_app.register(ConversationServe, api_prefix="/api/v1/chat/dialogue")
    # ################################ Conversation Serve Register End ########################################

    # ################################ AWEL Flow Serve Register Begin ######################################
    from dbgpt.serve.flow.serve import (
        SERVE_CONFIG_KEY_PREFIX as FLOW_SERVE_CONFIG_KEY_PREFIX,
    )
    from dbgpt.serve.flow.serve import Serve as FlowServe

    # Register serve app
    system_app.register(FlowServe)

    # ################################ Rag Serve Register Begin ######################################

    from dbgpt.serve.rag.serve import (
        SERVE_CONFIG_KEY_PREFIX as RAG_SERVE_CONFIG_KEY_PREFIX,
    )
    from dbgpt.serve.rag.serve import Serve as RagServe

    # Register serve app
    system_app.register(RagServe)

    # ################################ Datasource Serve Register Begin ######################################

    from dbgpt.serve.datasource.serve import (
        SERVE_CONFIG_KEY_PREFIX as DATASOURCE_SERVE_CONFIG_KEY_PREFIX,
    )
    from dbgpt.serve.datasource.serve import Serve as DatasourceServe

    # Register serve app
    system_app.register(DatasourceServe)
    # ################################ AWEL Flow Serve Register End ########################################
