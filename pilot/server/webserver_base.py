import signal
import os
import threading
import traceback
import sys

from pilot.summary.db_summary_client import DBSummaryClient
from pilot.commands.command_mange import CommandRegistry
from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    LLM_MODEL_CONFIG,
    LOGDIR,
)
from pilot.common.plugins import scan_plugins, load_native_plugins
from pilot.utils import build_logger

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

logger = build_logger("webserver", LOGDIR + "webserver.log")


def signal_handler(sig, frame):
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


def async_db_summery():
    client = DBSummaryClient()
    thread = threading.Thread(target=client.init_db_summary)
    thread.start()


def server_init(args):
    logger.info(f"args: {args}")

    # init config
    cfg = Config()
    load_native_plugins(cfg)
    signal.signal(signal.SIGINT, signal_handler)
    async_db_summery()
    cfg.set_plugins(scan_plugins(cfg, cfg.debug_mode))

    # Loader plugins and commands
    command_categories = [
        "pilot.commands.built_in.audio_text",
        "pilot.commands.built_in.image_gen",
    ]
    # exclude commands
    command_categories = [
        x for x in command_categories if x not in cfg.disabled_command_categories
    ]
    command_registry = CommandRegistry()
    for command_category in command_categories:
        command_registry.import_commands(command_category)

    cfg.command_registry = command_registry
