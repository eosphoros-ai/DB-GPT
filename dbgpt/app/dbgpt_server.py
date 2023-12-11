import os
import argparse
import sys
from typing import List

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)
from dbgpt.configs.model_config import (
    LLM_MODEL_CONFIG,
    EMBEDDING_MODEL_CONFIG,
    LOGDIR,
    ROOT_PATH,
)
from dbgpt._private.config import Config
from dbgpt.component import SystemApp

from dbgpt.app.base import (
    server_init,
    WebServerParameters,
    _create_model_start_listener,
)
from dbgpt.app.component_configs import initialize_components

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, applications
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from dbgpt.app.knowledge.api import router as knowledge_router
from dbgpt.app.prompt.api import router as prompt_router
from dbgpt.app.llm_manage.api import router as llm_manage_api

from dbgpt.app.openapi.api_v1.api_v1 import router as api_v1
from dbgpt.app.openapi.base import validation_exception_handler
from dbgpt.app.openapi.api_v1.editor.api_editor_v1 import router as api_editor_route_v1
from dbgpt.app.openapi.api_v1.feedback.api_fb_v1 import router as api_fb_v1
from dbgpt.agent.commands.disply_type.show_chart_gen import (
    static_message_img_path,
)
from dbgpt.model.cluster import initialize_worker_manager_in_client
from dbgpt.util.utils import (
    setup_logging,
    _get_logging_level,
    logging_str_to_uvicorn_level,
    setup_http_service_logging,
)
from dbgpt.util.tracer import root_tracer, initialize_tracer, SpanType, SpanTypeRunName
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.system_utils import get_system_info

static_file_path = os.path.join(ROOT_PATH, "dbgpt", "app/static")

CFG = Config()


def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.10.3/swagger-ui.css",
    )


app = FastAPI()
applications.get_swagger_ui_html = swagger_monkey_patch

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

app.include_router(api_v1, prefix="/api", tags=["Chat"])
app.include_router(api_editor_route_v1, prefix="/api", tags=["Editor"])
app.include_router(llm_manage_api, prefix="/api", tags=["LLM Manage"])
app.include_router(api_fb_v1, prefix="/api", tags=["FeedBack"])

app.include_router(knowledge_router, tags=["Knowledge"])
app.include_router(prompt_router, tags=["Prompt"])


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


def _get_webserver_params(args: List[str] = None):
    from dbgpt.util.parameter_utils import EnvArgumentParser

    parser: argparse.ArgumentParser = EnvArgumentParser.create_argparse_option(
        WebServerParameters
    )
    return WebServerParameters(**vars(parser.parse_args(args=args)))


def initialize_app(param: WebServerParameters = None, args: List[str] = None):
    """Initialize app
    If you use gunicorn as a process manager, initialize_app can be invoke in `on_starting` hook.
    Args:
        param:WebWerverParameters
        args:List[str]
    """
    if not param:
        param = _get_webserver_params(args)

    if not param.log_level:
        param.log_level = _get_logging_level()
    setup_logging(
        "dbgpt", logging_level=param.log_level, logger_filename=param.log_file
    )

    # Before start
    system_app.before_start()
    model_name = param.model_name or CFG.LLM_MODEL
    param.model_name = model_name
    print(param)

    embedding_model_name = CFG.EMBEDDING_MODEL
    embedding_model_path = EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]

    server_init(param, system_app)
    model_start_listener = _create_model_start_listener(system_app)
    initialize_components(param, system_app, embedding_model_name, embedding_model_path)

    model_path = CFG.LLM_MODEL_PATH or LLM_MODEL_CONFIG.get(model_name)
    if not param.light:
        print("Model Unified Deployment Mode!")
        if not param.remote_embedding:
            embedding_model_name, embedding_model_path = None, None
        initialize_worker_manager_in_client(
            app=app,
            model_name=model_name,
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
        controller_addr = param.controller_addr or CFG.MODEL_SERVER
        initialize_worker_manager_in_client(
            app=app,
            model_name=model_name,
            model_path=model_path,
            run_locally=False,
            controller_addr=controller_addr,
            local_port=param.port,
            start_listener=model_start_listener,
            system_app=system_app,
        )
        CFG.SERVER_LIGHT_MODE = True

    mount_static_files(app)
    return param


def run_uvicorn(param: WebServerParameters):
    import uvicorn

    setup_http_service_logging()
    uvicorn.run(
        app,
        host=param.host,
        port=param.port,
        log_level=logging_str_to_uvicorn_level(param.log_level),
    )


def run_webserver(param: WebServerParameters = None):
    if not param:
        param = _get_webserver_params()
    initialize_tracer(
        system_app,
        os.path.join(LOGDIR, param.tracer_file),
        tracer_storage_cls=param.tracer_storage_cls,
    )

    with root_tracer.start_span(
        "run_webserver",
        span_type=SpanType.RUN,
        metadata={
            "run_service": SpanTypeRunName.WEBSERVER,
            "params": _get_dict_from_obj(param),
            "sys_infos": _get_dict_from_obj(get_system_info()),
        },
    ):
        param = initialize_app(param)
        run_uvicorn(param)


if __name__ == "__main__":
    run_webserver()
