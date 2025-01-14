import logging
import os
import signal
import sys
import threading
from dataclasses import dataclass, field
from typing import Optional

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.storage import DBType
from dbgpt.util.parameter_utils import BaseServerParameters

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
    # logger.info(f"args: {args}")
    # init config
    cfg = Config()
    cfg.SYSTEM_APP = system_app
    # Initialize db storage first
    _initialize_db_storage(param, system_app)

    # load_native_plugins(cfg)
    signal.signal(signal.SIGINT, signal_handler)


def _create_model_start_listener(system_app: SystemApp):
    def startup_event(wh):
        print("begin run _add_app_startup_event")
        async_db_summary(system_app)

    return startup_event


def _initialize_db_storage(param: "WebServerParameters", system_app: SystemApp):
    """Initialize the db storage.

    Now just support sqlite and mysql. If db type is sqlite, the db path is `pilot/meta_data/{db_name}.db`.
    """
    _initialize_db(
        try_to_create_db=not param.disable_alembic_upgrade, system_app=system_app
    )


def _migration_db_storage(param: "WebServerParameters"):
    """Migration the db storage."""
    # Import all models to make sure they are registered with SQLAlchemy.
    from dbgpt.app.initialization.db_model_initialization import _MODELS
    from dbgpt.configs.model_config import PILOT_PATH

    default_meta_data_path = os.path.join(PILOT_PATH, "meta_data")
    if not param.disable_alembic_upgrade:
        from dbgpt.storage.metadata.db_manager import db
        from dbgpt.util._db_migration_utils import _ddl_init_and_upgrade

        # Try to create all tables, when the dbtype is sqlite, it will auto create and upgrade system schema,
        # Otherwise, you need to execute initialization scripts to create schemas.
        CFG = Config()
        if CFG.LOCAL_DB_TYPE == "sqlite":
            try:
                db.create_all()
            except Exception as e:
                logger.warning(
                    f"Create all tables stored in this metadata error: {str(e)}"
                )

            _ddl_init_and_upgrade(default_meta_data_path, param.disable_alembic_upgrade)
        else:
            warn_msg = """For safety considerations, MySQL Database not support DDL init and upgrade. "
                "1.If you are use DB-GPT firstly, please manually execute the following command to initialize, 
                `mysql -h127.0.0.1 -uroot -p{your_password} < ./assets/schema/dbgpt.sql` "
                "2.If there are any changes to the table columns in the DB-GPT database, 
                it is necessary to compare with the DB-GPT/assets/schema/dbgpt.sql file 
                and manually make the columns changes in the MySQL database instance."""
            logger.warning(warn_msg)


def _initialize_db(
    try_to_create_db: Optional[bool] = False, system_app: Optional[SystemApp] = None
) -> str:
    """Initialize the database

    Now just support sqlite and MySQL. If db type is sqlite, the db path is `pilot/meta_data/{db_name}.db`.
    """
    from urllib.parse import quote
    from urllib.parse import quote_plus as urlquote

    from dbgpt.configs.model_config import PILOT_PATH
    from dbgpt.datasource.rdbms.dialect.oceanbase.ob_dialect import (  # noqa: F401
        OBDialect,
    )
    from dbgpt.storage.metadata.db_manager import initialize_db

    CFG = Config()
    db_name = CFG.LOCAL_DB_NAME
    default_meta_data_path = os.path.join(PILOT_PATH, "meta_data")
    os.makedirs(default_meta_data_path, exist_ok=True)
    if CFG.LOCAL_DB_TYPE == DBType.MySQL.value():
        db_url = (
            f"mysql+pymysql://{quote(CFG.LOCAL_DB_USER)}:"
            f"{urlquote(CFG.LOCAL_DB_PASSWORD)}@"
            f"{CFG.LOCAL_DB_HOST}:"
            f"{str(CFG.LOCAL_DB_PORT)}/"
            f"{db_name}?charset=utf8mb4"
        )
        if CFG.LOCAL_DB_SSL_VERIFY:
            db_url += "&ssl_verify_cert=true&ssl_verify_identity=true"
        # Try to create database, if failed, will raise exception
        _create_mysql_database(db_name, db_url, try_to_create_db)
    elif CFG.LOCAL_DB_TYPE == DBType.OceanBase.value():
        db_url = (
            f"mysql+ob://{quote(CFG.LOCAL_DB_USER)}:"
            f"{urlquote(CFG.LOCAL_DB_PASSWORD)}@"
            f"{CFG.LOCAL_DB_HOST}:"
            f"{str(CFG.LOCAL_DB_PORT)}/"
            f"{db_name}?charset=utf8mb4"
        )
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
    db = initialize_db(db_url, db_name, engine_args)
    if system_app:
        from dbgpt.storage.metadata import UnifiedDBManagerFactory

        system_app.register(UnifiedDBManagerFactory, db)
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
    from sqlalchemy import DDL, create_engine
    from sqlalchemy.exc import OperationalError, SQLAlchemyError

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
                    conn.execute(
                        DDL(
                            f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE "
                            f"utf8mb4_unicode_ci"
                        )
                    )
                    logger.info(f"Database {db_name} successfully created")
            except SQLAlchemyError as e:
                logger.error(f"Failed to create database {db_name}: {e}")
                raise
        else:
            logger.error(f"Error connecting to database {db_name}: {oe}")
            raise


@dataclass
class WebServerParameters(BaseServerParameters):
    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": "Webserver deploy host"}
    )
    port: Optional[int] = field(
        default=None, metadata={"help": "Webserver deploy port"}
    )
    daemon: Optional[bool] = field(
        default=False, metadata={"help": "Run Webserver in background"}
    )
    controller_addr: Optional[str] = field(
        default=None,
        metadata={
            "help": "The Model controller address to connect. If None, read model "
            "controller address from environment key `MODEL_SERVER`."
        },
    )
    model_name: str = field(
        default=None,
        metadata={
            "help": "The default model name to use. If None, read model name from "
            "environment key `LLM_MODEL`.",
            "tags": "fixed",
        },
    )
    share: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to create a publicly shareable link for the interface. "
            "Creates an SSH tunnel to make your UI accessible from anywhere. "
        },
    )
    remote_embedding: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to enable remote embedding models. If it is True, you need"
            " to start a embedding model through `dbgpt start worker --worker_type "
            "text2vec --model_name xxx --model_path xxx`"
        },
    )
    remote_rerank: Optional[bool] = field(
        default=False,
        metadata={
            "help": "Whether to enable remote rerank models. If it is True, you need"
            " to start a rerank model through `dbgpt start worker --worker_type "
            "text2vec --rerank --model_name xxx --model_path xxx`"
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
    awel_dirs: Optional[str] = field(
        default=None,
        metadata={
            "help": "The directories to search awel files, split by `,`",
        },
    )
    default_thread_pool_size: Optional[int] = field(
        default=None,
        metadata={
            "help": "The default thread pool size, If None, "
            "use default config of python thread pool",
        },
    )
