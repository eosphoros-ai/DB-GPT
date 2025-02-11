import logging
import os
import sys
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# fastapi import time cost about 0.05s
from fastapi.staticfiles import StaticFiles

from dbgpt._version import version
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import (
    LOGDIR,
    STATIC_MESSAGE_IMG_PATH,
)
from dbgpt.util.fastapi import create_app, replace_router
from dbgpt.util.i18n_utils import _, set_default_language
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.system_utils import get_system_info
from dbgpt.util.tracer import SpanType, SpanTypeRunName, initialize_tracer, root_tracer
from dbgpt.util.utils import (
    logging_str_to_uvicorn_level,
    setup_http_service_logging,
    setup_logging,
)
from dbgpt_app.base import (
    _create_model_start_listener,
    _migration_db_storage,
    server_init,
)

# initialize_components import time cost about 0.1s
from dbgpt_app.component_configs import initialize_components
from dbgpt_app.config import ApplicationConfig, ServiceWebParameters
from dbgpt_serve.core import add_exception_handler

logger = logging.getLogger(__name__)
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

app = create_app(
    title=_("DB-GPT Open API"),
    description=_("DB-GPT Open API"),
    version=version,
    openapi_tags=[],
)
# Use custom router to support priority
replace_router(app)

system_app = SystemApp(app)


def mount_routers(app: FastAPI):
    """Lazy import to avoid high time cost"""
    from dbgpt_app.knowledge.api import router as knowledge_router
    from dbgpt_app.llm_manage.api import router as llm_manage_api
    from dbgpt_app.openapi.api_v1.api_v1 import router as api_v1
    from dbgpt_app.openapi.api_v1.editor.api_editor_v1 import (
        router as api_editor_route_v1,
    )
    from dbgpt_app.openapi.api_v1.feedback.api_fb_v1 import router as api_fb_v1
    from dbgpt_app.openapi.api_v2 import router as api_v2
    from dbgpt_serve.agent.app.controller import router as gpts_v1
    from dbgpt_serve.agent.app.endpoints import router as app_v2

    app.include_router(api_v1, prefix="/api", tags=["Chat"])
    app.include_router(api_v2, prefix="/api", tags=["ChatV2"])
    app.include_router(api_editor_route_v1, prefix="/api", tags=["Editor"])
    app.include_router(llm_manage_api, prefix="/api", tags=["LLM Manage"])
    app.include_router(api_fb_v1, prefix="/api", tags=["FeedBack"])
    app.include_router(gpts_v1, prefix="/api", tags=["GptsApp"])
    app.include_router(app_v2, prefix="/api", tags=["App"])

    app.include_router(knowledge_router, tags=["Knowledge"])

    from dbgpt_serve.agent.app.recommend_question.controller import (
        router as recommend_question_v1,
    )

    app.include_router(recommend_question_v1, prefix="/api", tags=["RecommendQuestion"])


def mount_static_files(app: FastAPI, param: ApplicationConfig):
    if param.service.web.new_web_ui:
        static_file_path = os.path.join(ROOT_PATH, "src", "dbgpt_app/static/web")
    else:
        static_file_path = os.path.join(ROOT_PATH, "src", "dbgpt_app/static/old_web")

    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
    app.mount(
        "/images",
        StaticFiles(directory=STATIC_MESSAGE_IMG_PATH, html=True),
        name="static2",
    )
    app.mount(
        "/_next/static", StaticFiles(directory=static_file_path + "/_next/static")
    )
    app.mount("/", StaticFiles(directory=static_file_path, html=True), name="static")

    app.mount(
        "/swagger_static",
        StaticFiles(directory=static_file_path),
        name="swagger_static",
    )


add_exception_handler(app)


def initialize_app(param: ApplicationConfig, args: List[str] = None):
    """Initialize app
    If you use gunicorn as a process manager, initialize_app can be invoke in
    `on_starting` hook.
    Args:
        param:WebWerverParameters
        args:List[str]
    """

    # import after param is initialized, accelerate --help speed
    from dbgpt.model.cluster import initialize_worker_manager_in_client

    web_config = param.service.web
    log_config = web_config.log or param.log

    logger_filename = log_config.file or os.path.join(LOGDIR, "dbgpt_webserver.log")
    setup_logging(
        "dbgpt", logging_level=log_config.level, logger_filename=logger_filename
    )
    print(param)

    server_init(param, system_app)
    mount_routers(app)
    model_start_listener = _create_model_start_listener(system_app)
    initialize_components(
        param,
        system_app,
    )
    system_app.on_init()

    # Migration db storage, so you db models must be imported before this
    _migration_db_storage(web_config.disable_alembic_upgrade)

    local_port = web_config.port
    # TODO: initialize_worker_manager_in_client as a component register in system_app
    if not web_config.light:
        logger.info(
            "Model Unified Deployment Mode, run all services in the same process"
        )
        initialize_worker_manager_in_client(
            worker_params=param.generate_temp_model_worker_params(),
            models_config=param.models,
            app=app,
            local_port=local_port,
            start_listener=model_start_listener,
            system_app=system_app,
        )

    else:
        # MODEL_SERVER is controller address now
        controller_addr = web_config.controller_addr
        initialize_worker_manager_in_client(
            worker_params=param.generate_temp_model_worker_params(),
            models_config=param.models,
            app=app,
            run_locally=False,
            controller_addr=controller_addr,
            local_port=local_port,
            start_listener=model_start_listener,
            system_app=system_app,
        )

    mount_static_files(app, param)

    # Before start, after on_init
    system_app.before_start()
    return param


def run_uvicorn(param: ServiceWebParameters):
    import uvicorn

    setup_http_service_logging()

    # https://github.com/encode/starlette/issues/617
    cors_app = CORSMiddleware(
        app=app,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    log_level = "info"
    if param.log:
        log_level = logging_str_to_uvicorn_level(param.log.level)
    uvicorn.run(
        cors_app,
        host=param.host,
        port=param.port,
        log_level=log_level,
    )


def run_webserver(param: ApplicationConfig):
    trace_config = param.service.web.trace or param.trace
    trace_file = trace_config.file or os.path.join(
        "logs", "dbgpt_webserver_tracer.jsonl"
    )
    initialize_tracer(
        trace_file,
        system_app=system_app,
        root_operation_name=trace_config.root_operation_name or "DB-GPT-Webserver",
        tracer_parameters=trace_config,
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

        # TODO
        from dbgpt_serve.agent.agents.expand.app_start_assisant_agent import (  # noqa: F401
            StartAppAssistantAgent,
        )
        from dbgpt_serve.agent.agents.expand.intent_recognition_agent import (  # noqa: F401
            IntentRecognitionAgent,
        )

        run_uvicorn(param.service.web)


def load_config(config_file: str = None) -> ApplicationConfig:
    from dbgpt.configs.model_config import ROOT_PATH as DBGPT_ROOT_PATH
    from dbgpt.model import scan_model_providers
    from dbgpt.util.configure import ConfigurationManager
    from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

    cm = ConnectorManager(system_app)
    # pre import all connectors
    cm.on_init()
    # Register all model providers
    scan_model_providers()

    if config_file is None:
        config_file = os.path.join(DBGPT_ROOT_PATH, "configs", "dbgpt-siliconflow.toml")
    elif not os.path.isabs(config_file):
        # If config_file is a relative path, make it relative to DBGPT_ROOT_PATH
        config_file = os.path.join(DBGPT_ROOT_PATH, config_file)

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    logger.info(f"Loading configuration from: {config_file}")
    cfg = ConfigurationManager.from_file(config_file)
    app_config = cfg.parse_config(ApplicationConfig, hook_section="hooks")
    return app_config


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="DB-GPT Webserver")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to the configuration file. Default: configs/dbgpt-siliconflow.toml",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    # Load configuration with specified config file
    app_config = load_config(args.config)
    set_default_language(app_config.system.language)
    run_webserver(app_config)
