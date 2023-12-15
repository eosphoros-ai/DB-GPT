from typing import Optional
import os
import logging
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, DeclarativeMeta
from alembic import command
from alembic.util.exc import CommandError
from alembic.config import Config as AlembicConfig


logger = logging.getLogger(__name__)


def create_alembic_config(
    alembic_root_path: str,
    engine: Engine,
    base: DeclarativeMeta,
    session: Session,
    alembic_ini_path: Optional[str] = None,
    script_location: Optional[str] = None,
) -> AlembicConfig:
    """Create alembic config.

    Args:
        alembic_root_path: alembic root path
        engine: sqlalchemy engine
        base: sqlalchemy base
        session: sqlalchemy session
        alembic_ini_path (Optional[str]): alembic ini path
        script_location (Optional[str]): alembic script location

    Returns:
        alembic config
    """
    alembic_ini_path = alembic_ini_path or os.path.join(
        alembic_root_path, "alembic.ini"
    )
    alembic_cfg = AlembicConfig(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    script_location = script_location or os.path.join(alembic_root_path, "alembic")
    versions_dir = os.path.join(script_location, "versions")

    os.makedirs(script_location, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)

    alembic_cfg.set_main_option("script_location", script_location)

    alembic_cfg.attributes["target_metadata"] = base.metadata
    alembic_cfg.attributes["session"] = session
    return alembic_cfg


def create_migration_script(
    alembic_cfg: AlembicConfig, engine: Engine, message: str = "New migration"
) -> None:
    """Create migration script.

    Args:
        alembic_cfg: alembic config
        engine: sqlalchemy engine
        message: migration message

    """
    with engine.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.revision(alembic_cfg, message, autogenerate=True)


def upgrade_database(
    alembic_cfg: AlembicConfig, engine: Engine, target_version: str = "head"
) -> None:
    """Upgrade database to target version.

    Args:
        alembic_cfg: alembic config
        engine: sqlalchemy engine
        target_version: target version, default is head(latest version)
    """
    with engine.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        # Will create tables if not exists
        command.upgrade(alembic_cfg, target_version)


def downgrade_database(
    alembic_cfg: AlembicConfig, engine: Engine, revision: str = "-1"
):
    """Downgrade the database by one revision.

    Args:
        alembic_cfg: Alembic configuration object.
        engine: SQLAlchemy engine instance.
        revision: Revision identifier, default is "-1" which means one revision back.
    """
    with engine.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, revision)


def clean_alembic_migration(alembic_cfg: AlembicConfig, engine: Engine) -> None:
    """Clean Alembic migration scripts and history.

    Args:
        alembic_cfg: Alembic config object
        engine: SQLAlchemy engine instance

    """
    import shutil

    # Get migration script location
    script_location = alembic_cfg.get_main_option("script_location")
    print(f"Delete migration script location: {script_location}")

    # Delete all migration script files
    for file in os.listdir(script_location):
        if file.startswith("versions"):
            filepath = os.path.join(script_location, file)
            print(f"Delete migration script file: {filepath}")
            if os.path.isfile(filepath):
                os.remove(filepath)
            else:
                shutil.rmtree(filepath, ignore_errors=True)

    # Delete Alembic version table if exists
    version_table = alembic_cfg.get_main_option("version_table") or "alembic_version"
    if version_table:
        with engine.connect() as connection:
            print(f"Delete Alembic version table: {version_table}")
            connection.execute(text(f"DROP TABLE IF EXISTS {version_table}"))

    print("Cleaned Alembic migration scripts and history")


_MIGRATION_SOLUTION = """
**Solution 1:**

Run the following command to upgrade the database.
```commandline
dbgpt db migration upgrade
```

**Solution 2:**

Run the following command to clean the migration script and migration history.
```commandline
dbgpt db migration clean -y
```

**Solution 3:**

If you have already run the above command, but the error still exists, 
you can try the following command to clean the migration script, migration history and your data.
warning: This command will delete all your data!!! Please use it with caution.

```commandline
dbgpt db migration clean --drop_all_tables -y --confirm_drop_all_tables
```
or 
```commandline
rm -rf pilot/meta_data/alembic/versions/*
rm -rf pilot/meta_data/alembic/dbgpt.db
```
"""


def _ddl_init_and_upgrade(
    default_meta_data_path: str,
    disable_alembic_upgrade: bool,
    alembic_ini_path: Optional[str] = None,
    script_location: Optional[str] = None,
):
    """Initialize and upgrade database metadata

    Args:
        default_meta_data_path (str): default meta data path
        disable_alembic_upgrade (bool): Whether to enable alembic to initialize and upgrade database metadata
        alembic_ini_path (Optional[str]): alembic ini path
        script_location (Optional[str]): alembic script location
    """
    if disable_alembic_upgrade:
        logger.info(
            "disable_alembic_upgrade is true, not to initialize and upgrade database metadata with alembic"
        )
        return
    else:
        warn_msg = (
            "Initialize and upgrade database metadata with alembic, "
            "just run this in your development environment, if you deploy this in production environment, "
            "please run webserver with --disable_alembic_upgrade(`python dbgpt/app/dbgpt_server.py "
            "--disable_alembic_upgrade`).\n"
            "we suggest you to use `dbgpt db migration` to initialize and upgrade database metadata with alembic, "
            "your can run `dbgpt db migration --help` to get more information."
        )
        logger.warning(warn_msg)
    from dbgpt.storage.metadata.db_manager import db

    alembic_cfg = create_alembic_config(
        default_meta_data_path,
        db.engine,
        db.Model,
        db.session(),
        alembic_ini_path,
        script_location,
    )
    try:
        create_migration_script(alembic_cfg, db.engine)
        upgrade_database(alembic_cfg, db.engine)
    except CommandError as e:
        if "Target database is not up to date" in str(e):
            logger.error(
                f"Initialize and upgrade database metadata with alembic failed, error detail: {str(e)} "
                f"you can try the following solutions:\n{_MIGRATION_SOLUTION}\n"
            )
            raise Exception(
                "Initialize and upgrade database metadata with alembic failed, "
                "you can see the error and solutions above"
            ) from e
        else:
            raise e
