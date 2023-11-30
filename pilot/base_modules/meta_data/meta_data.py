import os
import sqlite3
import logging

from sqlalchemy import create_engine, DDL
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from alembic import command
from alembic.config import Config as AlembicConfig
from urllib.parse import quote
from pilot.configs.config import Config


logger = logging.getLogger(__name__)
# DB-GPT meta_data database config, now support mysql and sqlite
CFG = Config()
default_db_path = os.path.join(os.getcwd(), "meta_data")

os.makedirs(default_db_path, exist_ok=True)

# Meta Info
META_DATA_DATABASE = CFG.LOCAL_DB_NAME
db_name = META_DATA_DATABASE
db_path = default_db_path + f"/{db_name}.db"
connection = sqlite3.connect(db_path)


if CFG.LOCAL_DB_TYPE == "mysql":
    engine_temp = create_engine(
        f"mysql+pymysql://"
        + quote(CFG.LOCAL_DB_USER)
        + ":"
        + quote(CFG.LOCAL_DB_PASSWORD)
        + "@"
        + CFG.LOCAL_DB_HOST
        + ":"
        + str(CFG.LOCAL_DB_PORT)
    )
    # check and auto create mysqldatabase
    try:
        # try to connect
        with engine_temp.connect() as conn:
            # TODO We should consider that the production environment does not have permission to execute the DDL
            conn.execute(DDL(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
        print(f"Already connect '{db_name}'")

    except OperationalError as e:
        # if connect failed, create dbgpt database
        logger.error(f"{db_name} not connect success!")

    engine = create_engine(
        f"mysql+pymysql://"
        + quote(CFG.LOCAL_DB_USER)
        + ":"
        + quote(CFG.LOCAL_DB_PASSWORD)
        + "@"
        + CFG.LOCAL_DB_HOST
        + ":"
        + str(CFG.LOCAL_DB_PORT)
        + f"/{db_name}"
    )
else:
    engine = create_engine(f"sqlite:///{db_path}")


Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = Session()

Base = declarative_base()

# Base.metadata.create_all()

alembic_ini_path = default_db_path + "/alembic.ini"
alembic_cfg = AlembicConfig(alembic_ini_path)

alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))

os.makedirs(default_db_path + "/alembic", exist_ok=True)
os.makedirs(default_db_path + "/alembic/versions", exist_ok=True)

alembic_cfg.set_main_option("script_location", default_db_path + "/alembic")

alembic_cfg.attributes["target_metadata"] = Base.metadata
alembic_cfg.attributes["session"] = session


def ddl_init_and_upgrade(disable_alembic_upgrade: bool):
    """Initialize and upgrade database metadata

    Args:
        disable_alembic_upgrade (bool): Whether to enable alembic to initialize and upgrade database metadata
    """
    if disable_alembic_upgrade:
        logger.info(
            "disable_alembic_upgrade is true, not to initialize and upgrade database metadata with alembic"
        )
        return

    with engine.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        heads = command.heads(alembic_cfg)
        print("heads:" + str(heads))

        command.revision(alembic_cfg, "dbgpt ddl upate", True)
        command.upgrade(alembic_cfg, "head")
