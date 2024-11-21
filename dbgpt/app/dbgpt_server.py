import argparse
import os
import sys
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# fastapi import time cost about 0.05s
from fastapi.staticfiles import StaticFiles

from dbgpt._private.config import Config
from dbgpt._version import version
from dbgpt.app.base import (
    WebServerParameters,
    _create_model_start_listener,
    _migration_db_storage,
    server_init,
)

# initialize_components import time cost about 0.1s
from dbgpt.app.component_configs import initialize_components
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    LLM_MODEL_CONFIG,
    LOGDIR,
    STATIC_MESSAGE_IMG_PATH,
)
from dbgpt.serve.core import add_exception_handler
from dbgpt.util.fastapi import create_app, register_event_handler, replace_router
from dbgpt.util.i18n_utils import _, set_default_language
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.system_utils import get_system_info
from dbgpt.util.tracer import SpanType, SpanTypeRunName, initialize_tracer, root_tracer
from dbgpt.util.utils import (
    _get_logging_level,
    logging_str_to_uvicorn_level,
    setup_http_service_logging,
    setup_logging,
)

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

CFG = Config()
set_default_language(CFG.LANGUAGE)

if CFG.USE_NEW_WEB_UI:
    static_file_path = os.path.join(ROOT_PATH, "dbgpt", "app/static/web")
else:
    static_file_path = os.path.join(ROOT_PATH, "dbgpt", "app/static/old_web")

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
    from dbgpt.app.knowledge.api import router as knowledge_router
    from dbgpt.app.llm_manage.api import router as llm_manage_api
    from dbgpt.app.openapi.api_v1.api_v1 import router as api_v1
    from dbgpt.app.openapi.api_v1.editor.api_editor_v1 import (
        router as api_editor_route_v1,
    )
    from dbgpt.app.openapi.api_v1.feedback.api_fb_v1 import router as api_fb_v1
    from dbgpt.app.openapi.api_v2 import router as api_v2
    from dbgpt.serve.agent.app.controller import router as gpts_v1
    from dbgpt.serve.agent.app.endpoints import router as app_v2

    app.include_router(api_v1, prefix="/api", tags=["Chat"])
    app.include_router(api_v2, prefix="/api", tags=["ChatV2"])
    app.include_router(api_editor_route_v1, prefix="/api", tags=["Editor"])
    app.include_router(llm_manage_api, prefix="/api", tags=["LLM Manage"])
    app.include_router(api_fb_v1, prefix="/api", tags=["FeedBack"])
    app.include_router(gpts_v1, prefix="/api", tags=["GptsApp"])
    app.include_router(app_v2, prefix="/api", tags=["App"])

    app.include_router(knowledge_router, tags=["Knowledge"])

    from dbgpt.serve.agent.app.recommend_question.controller import (
        router as recommend_question_v1,
    )

    app.include_router(recommend_question_v1, prefix="/api", tags=["RecommendQuestion"])


def mount_static_files(app: FastAPI):
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


def _get_webserver_params(args: List[str] = None):
    from dbgpt.util.parameter_utils import EnvArgumentParser

    parser = EnvArgumentParser()

    env_prefix = "webserver_"
    webserver_params: WebServerParameters = parser.parse_args_into_dataclass(
        WebServerParameters,
        env_prefixes=[env_prefix],
        command_args=args,
    )
    return webserver_params


def initialize_app(param: WebServerParameters = None, args: List[str] = None):
    """Initialize app
    If you use gunicorn as a process manager, initialize_app can be invoke in `on_starting` hook.
    Args:
        param:WebWerverParameters
        args:List[str]
    """
    if not param:
        param = _get_webserver_params(args)

    # import after param is initialized, accelerate --help speed
    from dbgpt.model.cluster import initialize_worker_manager_in_client

    if not param.log_level:
        param.log_level = _get_logging_level()
    setup_logging(
        "dbgpt", logging_level=param.log_level, logger_filename=param.log_file
    )

    model_name = param.model_name or CFG.LLM_MODEL
    param.model_name = model_name
    param.port = param.port or CFG.DBGPT_WEBSERVER_PORT
    if not param.port:
        param.port = 5670

    print(param)

    embedding_model_name = CFG.EMBEDDING_MODEL
    embedding_model_path = EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
    rerank_model_name = CFG.RERANK_MODEL
    rerank_model_path = None
    if rerank_model_name:
        rerank_model_path = CFG.RERANK_MODEL_PATH or EMBEDDING_MODEL_CONFIG.get(
            rerank_model_name
        )

    server_init(param, system_app)
    mount_routers(app)
    model_start_listener = _create_model_start_listener(system_app)
    initialize_components(
        param,
        system_app,
        embedding_model_name,
        embedding_model_path,
        rerank_model_name,
        rerank_model_path,
    )
    system_app.on_init()

    # Migration db storage, so you db models must be imported before this
    _migration_db_storage(param)

    model_path = CFG.LLM_MODEL_PATH or LLM_MODEL_CONFIG.get(model_name)
    # TODO: initialize_worker_manager_in_client as a component register in system_app
    if not param.light:
        print("Model Unified Deployment Mode!")
        if not param.remote_embedding:
            # Embedding model is running in the same process, set embedding_model_name
            # and embedding_model_path to None
            embedding_model_name, embedding_model_path = None, None
        if not param.remote_rerank:
            # Rerank model is running in the same process, set rerank_model_name and
            # rerank_model_path to None
            rerank_model_name, rerank_model_path = None, None
        initialize_worker_manager_in_client(
            app=app,
            model_name=model_name,
            model_path=model_path,
            local_port=param.port,
            embedding_model_name=embedding_model_name,
            embedding_model_path=embedding_model_path,
            rerank_model_name=rerank_model_name,
            rerank_model_path=rerank_model_path,
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

    # Before start, after on_init
    system_app.before_start()
    return param


def run_uvicorn(param: WebServerParameters):
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
    uvicorn.run(
        cors_app,
        host=param.host,
        port=param.port,
        log_level=logging_str_to_uvicorn_level(param.log_level),
    )


def run_webserver(param: WebServerParameters = None):
    if not param:
        param = _get_webserver_params()
    initialize_tracer(
        os.path.join(LOGDIR, param.tracer_file),
        system_app=system_app,
        tracer_storage_cls=param.tracer_storage_cls,
        enable_open_telemetry=param.tracer_to_open_telemetry,
        otlp_endpoint=param.otel_exporter_otlp_traces_endpoint,
        otlp_insecure=param.otel_exporter_otlp_traces_insecure,
        otlp_timeout=param.otel_exporter_otlp_traces_timeout,
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
        from dbgpt.serve.agent.agents.expand.app_start_assisant_agent import (  # noqa: F401
            StartAppAssistantAgent,
        )
        from dbgpt.serve.agent.agents.expand.intent_recognition_agent import (  # noqa: F401
            IntentRecognitionAgent,
        )

        run_uvicorn(param)


if __name__ == "__main__":
    run_webserver()
