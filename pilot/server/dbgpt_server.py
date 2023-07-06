import traceback
import os
import shutil
import argparse
import sys

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)
import signal
from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    LLM_MODEL_CONFIG,
    LOGDIR,
)
from pilot.utils import build_logger

from pilot.server.webserver_base import server_init

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, applications
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pilot.server.knowledge.api import router as knowledge_router


from pilot.openapi.api_v1.api_v1 import router as api_v1, validation_exception_handler


static_file_path = os.path.join(os.getcwd(), "server/static")


CFG = Config()
logger = build_logger("webserver", LOGDIR + "webserver.log")


def signal_handler(sig, frame):
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

app.include_router(api_v1)
app.include_router(knowledge_router)

app.mount("/_next/static", StaticFiles(directory=static_file_path + "/_next/static"))
app.mount("/", StaticFiles(directory=static_file_path, html=True), name="static")
# app.mount("/chat", StaticFiles(directory=static_file_path + "/chat.html", html=True), name="chat")


app.add_exception_handler(RequestValidationError, validation_exception_handler)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_list_mode", type=str, default="once", choices=["once", "reload"]
    )

    # old version server config
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--concurrency-count", type=int, default=10)
    parser.add_argument("--share", default=False, action="store_true")
    parser.add_argument(
        "-light",
        "--light",
        default=False,
        action="store_true",
        help="enable light mode",
    )
    signal.signal(signal.SIGINT, signal_handler)

    # init server config
    args = parser.parse_args()
    server_init(args)

    if not args.light:
        print("Model Unified Deployment Mode!")
        from pilot.server.llmserver import worker

        worker.start_check()
        CFG.NEW_SERVER_MODE = True
    else:
        CFG.SERVER_LIGHT_MODE = True

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=args.port)
