import os
import argparse
import sys
from typing import List

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)
import signal
from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG, EMBEDDING_MODEL_CONFIG
from pilot.component import SystemApp

from pilot.server.base import (
    server_init,
    WebWerverParameters,
    _create_model_start_listener,
)
from pilot.server.component_configs import initialize_components

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, applications
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pilot.server.knowledge.api import router as knowledge_router
from pilot.server.prompt.api import router as prompt_router


from pilot.openapi.api_v1.api_v1 import router as api_v1
from pilot.openapi.base import validation_exception_handler
from pilot.openapi.api_v1.editor.api_editor_v1 import router as api_editor_route_v1
from pilot.commands.disply_type.show_chart_gen import static_message_img_path
from pilot.model.cluster import initialize_worker_manager_in_client
from pilot.utils.utils import setup_logging, logging_str_to_uvicorn_level

static_file_path = os.path.join(os.getcwd(), "server/static")

CFG = Config()


def signal_handler():
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui.css"
    )


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI()
system_app = SystemApp(app)

origins = ["*"]

# 添加跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


app.include_router(api_v1, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(api_editor_route_v1, prefix="/api")

# app.include_router(api_v1)
app.include_router(knowledge_router)
app.include_router(prompt_router)
# app.include_router(api_editor_route_v1)


def mount_static_files(app):
    os.makedirs(static_message_img_path, exist_ok=True)
    app.mount(
        "/images",
        StaticFiles(directory=static_message_img_path, html=True),
        name="static2",
    )
    app.mount(
        "/_next/static", StaticFiles(directory=static_file_path + "/_next/static")
    )
    app.mount("/", StaticFiles(directory=static_file_path, html=True), name="static")


app.add_exception_handler(RequestValidationError, validation_exception_handler)


def initialize_app(param: WebWerverParameters = None, args: List[str] = None):
    """Initialize app
    If you use gunicorn as a process manager, initialize_app can be invoke in `on_starting` hook.
    """
    if not param:
        from pilot.utils.parameter_utils import EnvArgumentParser

        parser: argparse.ArgumentParser = EnvArgumentParser.create_argparse_option(
            WebWerverParameters
        )
        param = WebWerverParameters(**vars(parser.parse_args(args=args)))

    setup_logging(logging_level=param.log_level)
    # Before start
    system_app.before_start()

    print(param)

    embedding_model_name = CFG.EMBEDDING_MODEL
    embedding_model_path = EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]

    server_init(param, system_app)
    model_start_listener = _create_model_start_listener(system_app)
    initialize_components(param, system_app, embedding_model_name, embedding_model_path)

    model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]
    if not param.light:
        print("Model Unified Deployment Mode!")
        if not param.remote_embedding:
            embedding_model_name, embedding_model_path = None, None
        initialize_worker_manager_in_client(
            app=app,
            model_name=CFG.LLM_MODEL,
            model_path=model_path,
            local_port=param.port,
            embedding_model_name=embedding_model_name,
            embedding_model_path=embedding_model_path,
            start_listener=model_start_listener,
            system_app=system_app,
        )

        CFG.NEW_SERVER_MODE = True
    else:
        # MODEL_SERVER is controller address now
        initialize_worker_manager_in_client(
            app=app,
            model_name=CFG.LLM_MODEL,
            model_path=model_path,
            run_locally=False,
            controller_addr=CFG.MODEL_SERVER,
            local_port=param.port,
            start_listener=model_start_listener,
            system_app=system_app,
        )
        CFG.SERVER_LIGHT_MODE = True

    mount_static_files(app)
    return param


def run_uvicorn(param: WebWerverParameters):
    import uvicorn

    uvicorn.run(
        app,
        host=param.host,
        port=param.port,
        log_level=logging_str_to_uvicorn_level(param.log_level),
    )
    signal.signal(signal.SIGINT, signal_handler())


def run_webserver(param: WebWerverParameters = None):
    param = initialize_app(param)
    run_uvicorn(param)


if __name__ == "__main__":
    run_webserver()
