import signal
import os
import threading
import sys
from typing import Optional
from dataclasses import dataclass, field

from pilot.configs.config import Config
from pilot.utils.parameter_utils import BaseParameters


ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)


def signal_handler(sig, frame):
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


def async_db_summery():
    from pilot.summary.db_summary_client import DBSummaryClient

    client = DBSummaryClient()
    thread = threading.Thread(target=client.init_db_summary)
    thread.start()


def server_init(args):
    from pilot.commands.command_mange import CommandRegistry
    from pilot.connections.manages.connection_manager import ConnectManager
    from pilot.common.plugins import scan_plugins

    # logger.info(f"args: {args}")

    # init config
    cfg = Config()
    # init connect manage
    conn_manage = ConnectManager()
    cfg.LOCAL_DB_MANAGE = conn_manage

    # load_native_plugins(cfg)
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

    command_disply_commands = [
        "pilot.commands.disply_type.show_chart_gen",
        "pilot.commands.disply_type.show_table_gen",
        "pilot.commands.disply_type.show_text_gen",
    ]
    command_disply_registry = CommandRegistry()
    for command in command_disply_commands:
        command_disply_registry.import_commands(command)
    cfg.command_disply = command_disply_registry


@dataclass
class WebWerverParameters(BaseParameters):
    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": "Webserver deploy host"}
    )
    port: Optional[int] = field(
        default=5000, metadata={"help": "Webserver deploy port"}
    )
    daemon: Optional[bool] = field(
        default=False, metadata={"help": "Run Webserver in background"}
    )
    share: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to create a publicly shareable link for the interface. Creates an SSH tunnel to make your UI accessible from anywhere. "
        },
    )
    log_level: Optional[str] = field(
        default="INFO",
        metadata={
            "help": "Logging level",
            "valid_values": [
                "FATAL",
                "ERROR",
                "WARNING",
                "WARNING",
                "INFO",
                "DEBUG",
                "NOTSET",
            ],
        },
    )
    light: Optional[bool] = field(default=False, metadata={"help": "enable light mode"})
