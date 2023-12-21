from dbgpt.component import SystemApp


def register_serve_apps(system_app: SystemApp):
    """Register serve apps"""
    from dbgpt.serve.prompt.serve import Serve as PromptServe, SERVE_CONFIG_KEY_PREFIX

    # Replace old prompt serve
    # Set config
    system_app.config.set(f"{SERVE_CONFIG_KEY_PREFIX}default_user", "dbgpt")
    system_app.config.set(f"{SERVE_CONFIG_KEY_PREFIX}default_sys_code", "dbgpt")
    # Register serve app
    system_app.register(PromptServe, api_prefix="/prompt")
