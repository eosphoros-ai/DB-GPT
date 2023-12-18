from dbgpt.component import SystemApp


def register_serve_apps(system_app: SystemApp):
    """Register serve apps"""
    from dbgpt.serve.prompt.serve import Serve as PromptServe

    # Replace old prompt serve
    system_app.register(PromptServe, api_prefix="/prompt")
