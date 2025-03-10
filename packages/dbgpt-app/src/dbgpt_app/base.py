import logging
import os
import signal
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import resolve_root_path
from dbgpt.core.interface.parameter import BaseServerParameters
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt_app.config import ApplicationConfig, ServiceConfig

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    print("in order to avoid chroma db atexit problem")
    os._exit(0)


def async_db_summary(system_app: SystemApp):
    """async db schema into vector db"""
    from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

    client = DBSummaryClient(system_app=system_app)
    thread = threading.Thread(target=client.init_db_summary)
    thread.start()


def server_init(param: ApplicationConfig, system_app: SystemApp):
    # logger.info(f"args: {args}")
    # init config
    cfg = Config()
    cfg.SYSTEM_APP = system_app
    # Initialize db storage first
    _initialize_db_storage(param.service, system_app)

    # load_native_plugins(cfg)
    signal.signal(signal.SIGINT, signal_handler)


def _create_model_start_listener(system_app: SystemApp):
    def startup_event(wh):
        print("begin run _add_app_startup_event")
        async_db_summary(system_app)

    return startup_event


def _initialize_db_storage(param: ServiceConfig, system_app: SystemApp):
    """Initialize the db storage.

    Now just support sqlite and mysql. If db type is sqlite, the db path is
    `pilot/meta_data/{db_name}.db`.
    """
    from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnectorParameters

    db_config: BaseDatasourceParameters = param.web.database
    if isinstance(db_config, SQLiteConnectorParameters):
        db_config.path = resolve_root_path(db_config.path)
        db_dir = os.path.dirname(db_config.path)
        os.makedirs(db_dir, exist_ok=True)
        # Parse the db name from the db path
        db_name = os.path.basename(db_config.path).split(".")[0]
    elif isinstance(db_config, RDBMSDatasourceParameters):
        db_name = db_config.database
    else:
        raise ValueError(
            "DB-GPT only support SQLite, MySQL and OceanBase database as metadata "
            "storage database"
        )

    disable_alembic_upgrade = param.web.disable_alembic_upgrade
    db_ssl_verify = param.web.db_ssl_verify
    connector = db_config.create_connector()
    if not isinstance(connector, RDBMSConnector):
        raise ValueError("Only support RDBMSConnector")
    db_url = db_config.db_url(ssl=db_ssl_verify, charset="utf8mb4")
    db_type = connector.db_type
    db_engine_args: Optional[Dict[str, Any]] = db_config.engine_args()
    _initialize_db(
        db_url,
        db_type,
        db_name,
        db_engine_args,
        try_to_create_db=not disable_alembic_upgrade,
        system_app=system_app,
    )


def _migration_db_storage(
    db_params: BaseDatasourceParameters, disable_alembic_upgrade: bool
):
    """Migration the db storage."""
    # Import all models to make sure they are registered with SQLAlchemy.
    from dbgpt.configs.model_config import PILOT_PATH
    from dbgpt_app.initialization.db_model_initialization import _MODELS  # noqa: F401
    from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnectorParameters

    default_meta_data_path = os.path.join(PILOT_PATH, "meta_data")
    if not disable_alembic_upgrade:
        from dbgpt.storage.metadata.db_manager import db
        from dbgpt.util._db_migration_utils import _ddl_init_and_upgrade

        # Try to create all tables, when the dbtype is sqlite, it will auto create and
        # upgrade system schema,
        # Otherwise, you need to execute initialization scripts to create schemas.
        if (
            isinstance(db_params, SQLiteConnectorParameters)
            or db_params.get_type_value() == "sqlite"
        ):
            try:
                db.create_all()
            except Exception as e:
                logger.warning(
                    f"Create all tables stored in this metadata error: {str(e)}"
                )

            _ddl_init_and_upgrade(default_meta_data_path, disable_alembic_upgrade)
        else:
            warn_msg = """For safety considerations, MySQL Database not support DDL \
            init and upgrade. "
                "1.If you are use DB-GPT firstly, please manually execute the following\
                 command to initialize, 
                `mysql -h127.0.0.1 -uroot -p{your_password} \
                < ./assets/schema/dbgpt.sql` "
                "2.If there are any changes to the table columns in the DB-GPT database,
                 it is necessary to compare with the DB-GPT/assets/schema/dbgpt.sql file
                 and manually make the columns changes in the MySQL database instance.
                 """
            logger.warning(warn_msg)


def _initialize_db(
    db_url: str,
    db_type: str,
    db_name: str,
    db_engine_args: Optional[Dict[str, Any]] = None,
    try_to_create_db: Optional[bool] = False,
    system_app: Optional[SystemApp] = None,
) -> str:
    """Initialize the database

    Now just support sqlite and MySQL. If db type is sqlite, the db path is
    `pilot/meta_data/{db_name}.db`.
    """

    from dbgpt.configs.model_config import PILOT_PATH
    from dbgpt.storage.metadata.db_manager import initialize_db
    from dbgpt_ext.datasource.rdbms.dialect.oceanbase.ob_dialect import (  # noqa: F401
        OBDialect,
    )

    default_meta_data_path = os.path.join(PILOT_PATH, "meta_data")
    if db_type == "mysql":
        # Try to create database, if failed, will raise exception
        _create_mysql_database(db_name, db_url, try_to_create_db)
    elif db_type == "oceanbase":
        _create_mysql_database(db_name, db_url, try_to_create_db)

    if not db_engine_args:
        db_engine_args = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        }
    db = initialize_db(db_url, db_name, db_engine_args)
    if system_app:
        from dbgpt.storage.metadata import UnifiedDBManagerFactory

        system_app.register(UnifiedDBManagerFactory, db)
    return default_meta_data_path


def _create_mysql_database(db_name: str, db_url: str, try_to_create_db: bool = False):
    """Create mysql database if not exists

    Args:
        db_name (str): The database name
        db_url (str): The database url, include host, port, user, password and database
            name
        try_to_create_db (bool, optional): Whether to try to create database. Defaults
            to False.

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
            "help": "Whether to disable alembic to initialize and upgrade database "
            "metadata",
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
