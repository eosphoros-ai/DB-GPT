import signal
import os
import threading
import sys
from typing import Optional
from dataclasses import dataclass, field

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.util.parameter_utils import BaseParameters
from dbgpt.storage.metadata.meta_data import ddl_init_and_upgrade

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)


def signal_handler(sig, frame):
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


def async_db_summary(system_app: SystemApp):
    """async db schema into vector db"""
    from dbgpt.rag.summary.db_summary_client import DBSummaryClient

    client = DBSummaryClient(system_app=system_app)
    thread = threading.Thread(target=client.init_db_summary)
    thread.start()


def server_init(param: "WebServerParameters", system_app: SystemApp):
    from dbgpt.agent.commands.command_mange import CommandRegistry

    # logger.info(f"args: {args}")

    # init config
    cfg = Config()
    cfg.SYSTEM_APP = system_app

    ddl_init_and_upgrade(param.disable_alembic_upgrade)

    # load_native_plugins(cfg)
    signal.signal(signal.SIGINT, signal_handler)

    # Loader plugins and commands
    command_categories = [
        "dbgpt.agent.commands.built_in.audio_text",
        "dbgpt.agent.commands.built_in.image_gen",
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
        "dbgpt.agent.commands.disply_type.show_chart_gen",
        "dbgpt.agent.commands.disply_type.show_table_gen",
        "dbgpt.agent.commands.disply_type.show_text_gen",
    ]
    command_disply_registry = CommandRegistry()
    for command in command_disply_commands:
        command_disply_registry.import_commands(command)
    cfg.command_disply = command_disply_registry


def _create_model_start_listener(system_app: SystemApp):
    from dbgpt.datasource.manages.connection_manager import ConnectManager

    cfg = Config()

    def startup_event(wh):
        # init connect manage
        print("begin run _add_app_startup_event")
        conn_manage = ConnectManager(system_app)
        cfg.LOCAL_DB_MANAGE = conn_manage
        async_db_summary(system_app)

    return startup_event


@dataclass
class WebServerParameters(BaseParameters):
    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": "Webserver deploy host"}
    )
    port: Optional[int] = field(
        default=5000, metadata={"help": "Webserver deploy port"}
    )
    daemon: Optional[bool] = field(
        default=False, metadata={"help": "Run Webserver in background"}
    )
    controller_addr: Optional[str] = field(
        default=None,
        metadata={
            "help": "The Model controller address to connect. If None, read model controller address from environment key `MODEL_SERVER`."
        },
    )
    model_name: str = field(
        default=None,
        metadata={
            "help": "The default model name to use. If None, read model name from environment key `LLM_MODEL`.",
            "tags": "fixed",
        },
    )
    share: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to create a publicly shareable link for the interface. Creates an SSH tunnel to make your UI accessible from anywhere. "
        },
    )
    remote_embedding: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to enable remote embedding models. If it is True, you need to start a embedding model through `dbgpt start worker --worker_type text2vec --model_name xxx --model_path xxx`"
        },
    )
    log_level: Optional[str] = field(
        default=None,
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
    log_file: Optional[str] = field(
        default="dbgpt_webserver.log",
        metadata={
            "help": "The filename to store log",
        },
    )
    tracer_file: Optional[str] = field(
        default="dbgpt_webserver_tracer.jsonl",
        metadata={
            "help": "The filename to store tracer span records",
        },
    )
    tracer_storage_cls: Optional[str] = field(
        default=None,
        metadata={
            "help": "The storage class to storage tracer span records",
        },
    )
    disable_alembic_upgrade: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to disable alembic to initialize and upgrade database metadata",
        },
    )
