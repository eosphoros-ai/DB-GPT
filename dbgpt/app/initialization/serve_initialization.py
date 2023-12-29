from dbgpt.component import SystemApp
from dbgpt._private.config import Config


def register_serve_apps(system_app: SystemApp, cfg: Config):
    """Register serve apps"""
    system_app.config.set("dbgpt.app.global.language", cfg.LANGUAGE)

    # ################################ Prompt Serve Register Begin ######################################
    from dbgpt.serve.prompt.serve import (
        Serve as PromptServe,
        SERVE_CONFIG_KEY_PREFIX as PROMPT_SERVE_CONFIG_KEY_PREFIX,
    )

    # Replace old prompt serve
    # Set config
    system_app.config.set(f"{PROMPT_SERVE_CONFIG_KEY_PREFIX}default_user", "dbgpt")
    system_app.config.set(f"{PROMPT_SERVE_CONFIG_KEY_PREFIX}default_sys_code", "dbgpt")
    # Register serve app
    system_app.register(PromptServe, api_prefix="/prompt")
    # ################################ Prompt Serve Register End ########################################

    # ################################ Conversation Serve Register Begin ######################################
    from dbgpt.serve.conversation.serve import Serve as ConversationServe

    # Register serve app
    system_app.register(ConversationServe)
    # ################################ Conversation Serve Register End ########################################
