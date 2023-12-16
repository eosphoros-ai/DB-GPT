import signal
import os
import threading
import sys
import logging
from typing import Optional
from dataclasses import dataclass, field

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.util.parameter_utils import BaseParameters

from dbgpt.util._db_migration_utils import _ddl_init_and_upgrade

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

logger = logging.getLogger(__name__)


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
    # Initialize db storage first
    _initialize_db_storage(param)

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


def _initialize_db_storage(param: "WebServerParameters"):
    """Initialize the db storage.

    Now just support sqlite and mysql. If db type is sqlite, the db path is `pilot/meta_data/{db_name}.db`.
    """
    default_meta_data_path = _initialize_db(
        try_to_create_db=not param.disable_alembic_upgrade
    )
    _ddl_init_and_upgrade(default_meta_data_path, param.disable_alembic_upgrade)


def _initialize_db(try_to_create_db: Optional[bool] = False) -> str:
    """Initialize the database

    Now just support sqlite and mysql. If db type is sqlite, the db path is `pilot/meta_data/{db_name}.db`.
    """
    from dbgpt.configs.model_config import PILOT_PATH
    from dbgpt.storage.metadata.db_manager import initialize_db
    from urllib.parse import quote_plus as urlquote, quote

    CFG = Config()
    db_name = CFG.LOCAL_DB_NAME
    default_meta_data_path = os.path.join(PILOT_PATH, "meta_data")
    os.makedirs(default_meta_data_path, exist_ok=True)
    if CFG.LOCAL_DB_TYPE == "mysql":
        db_url = f"mysql+pymysql://{quote(CFG.LOCAL_DB_USER)}:{urlquote(CFG.LOCAL_DB_PASSWORD)}@{CFG.LOCAL_DB_HOST}:{str(CFG.LOCAL_DB_PORT)}/{db_name}"
        # Try to create database, if failed, will raise exception
        _create_mysql_database(db_name, db_url, try_to_create_db)
    else:
        sqlite_db_path = os.path.join(default_meta_data_path, f"{db_name}.db")
        db_url = f"sqlite:///{sqlite_db_path}"
    engine_args = {
        "pool_size": CFG.LOCAL_DB_POOL_SIZE,
        "max_overflow": CFG.LOCAL_DB_POOL_OVERFLOW,
        "pool_timeout": 30,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }
    initialize_db(db_url, db_name, engine_args, try_to_create_db=try_to_create_db)
    return default_meta_data_path


def _create_mysql_database(db_name: str, db_url: str, try_to_create_db: bool = False):
    """Create mysql database if not exists

    Args:
        db_name (str): The database name
        db_url (str): The database url, include host, port, user, password and database name
        try_to_create_db (bool, optional): Whether to try to create database. Defaults to False.

    Raises:
        Exception: Raise exception if database operation failed
    """
    from sqlalchemy import create_engine, DDL
    from sqlalchemy.exc import SQLAlchemyError, OperationalError

    if not try_to_create_db:
        logger.info(f"Skipping creation of database {db_name}")
        return
    engine = create_engine(db_url)

    try:
        # Try to connect to the database
        with engine.connect() as conn:
            logger.info(f"Database {db_name} already exists")
            return
    except OperationalError as oe:
        # If the error indicates that the database does not exist, try to create it
        if "Unknown database" in str(oe):
            try:
                # Create the database
                no_db_name_url = db_url.rsplit("/", 1)[0]
                engine_no_db = create_engine(no_db_name_url)
                with engine_no_db.connect() as conn:
                    conn.execute(DDL(f"CREATE DATABASE {db_name}"))
                    logger.info(f"Database {db_name} successfully created")
            except SQLAlchemyError as e:
                logger.error(f"Failed to create database {db_name}: {e}")
                raise
        else:
            logger.error(f"Error connecting to database {db_name}: {oe}")
            raise


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
