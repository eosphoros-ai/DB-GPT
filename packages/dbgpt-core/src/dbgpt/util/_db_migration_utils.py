import logging
import os
from typing import Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.util.exc import CommandError
from sqlalchemy import Engine, text
from sqlalchemy.orm import DeclarativeMeta, Session

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
    alembic_cfg: AlembicConfig,
    engine: Engine,
    message: str = "New migration",
    create_new_revision_if_noting_to_update: Optional[bool] = True,
) -> str:
    """Create migration script.

    Args:
        alembic_cfg: alembic config
        engine: sqlalchemy engine
        message: migration message
        create_new_revision_if_noting_to_update: Whether to create a new revision if
        there is nothing to update,
            pass False to avoid creating a new revision if there is nothing to update,
            default is True
    Returns:
        The path of the generated migration script.
    """
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    # Check if the database is up-to-date
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection=connection)
        current_rev = context.get_current_revision()
        head_rev = script_dir.get_current_head()

    logger.info(
        f"alembic migration current revision: {current_rev}, latest revision: "
        f"{head_rev}"
    )
    should_create_revision = (
        (current_rev is None and head_rev is None)
        or current_rev != head_rev
        or create_new_revision_if_noting_to_update
    )
    if should_create_revision:
        with engine.connect() as connection:
            alembic_cfg.attributes["connection"] = connection
            revision = command.revision(alembic_cfg, message=message, autogenerate=True)
            # Return the path of the generated migration script
            return revision.path
    elif current_rev == head_rev:
        logger.info("No migration script to generate, database is up-to-date")
    # If no new revision is created, return None or an appropriate message
    return None


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


def generate_sql_for_upgrade(
    alembic_cfg: AlembicConfig,
    engine: Engine,
    target_version: Optional[str] = "head",
    output_file: Optional[str] = "migration.sql",
) -> None:
    """Generate SQL for upgrading database to target version.

    Args:
        alembic_cfg: alembic config
        engine: sqlalchemy engine
        target_version: target version, default is head (latest version)
        output_file: file to write the SQL script

    TODO: Can't generate SQL for most of the operations.
    """
    import contextlib
    import io

    with (
        engine.connect() as connection,
        contextlib.redirect_stdout(io.StringIO()) as stdout,
    ):
        alembic_cfg.attributes["connection"] = connection
        # Generating SQL instead of applying changes
        command.upgrade(alembic_cfg, target_version, sql=True)

        # Write the generated SQL to a file
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(stdout.getvalue())


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
you can try the following command to clean the migration script, migration history and \
your data.
warning: This command will delete all your data!!! Please use it with caution.

```commandline
dbgpt db migration clean --drop_all_tables -y --confirm_drop_all_tables
```
or 
```commandline
rm -rf pilot/meta_data/alembic/versions/*
rm -rf pilot/meta_data/alembic/dbgpt.db
```

If your database is a shared database, and you run DB-GPT in multiple instances, you \
should make sure that all migration scripts are same in all instances, in this case,
wo strongly recommend you close migration feature by setting \
`--disable_alembic_upgrade`.
and use `dbgpt db migration` command to manage migration scripts.
"""


def _check_database_migration_status(alembic_cfg: AlembicConfig, engine: Engine):
    """Check if the database is at the latest migration revision.

    If your database is a shared database, and you run DB-GPT in multiple instances,
    you should make sure that all migration scripts are same in all instances, in this
    case,
    wo strongly recommend you close migration feature by setting
    `disable_alembic_upgrade` to True.
    and use `dbgpt db migration` command to manage migration scripts.

    Args:
        alembic_cfg: Alembic configuration object.
        engine: SQLAlchemy engine instance.
    Raises:
        Exception: If the database is not at the latest revision.
    """
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_cfg)

    def get_current_revision(engine):
        with engine.connect() as connection:
            context = MigrationContext.configure(connection=connection)
            return context.get_current_revision()

    current_rev = get_current_revision(engine)
    head_rev = script.get_current_head()

    script_info_msg = "Migration versions and their file paths:"
    script_info_msg += f"\n{'=' * 40}Migration versions{'=' * 40}\n"
    for revision in script.walk_revisions(base="base"):
        current_marker = "(current)" if revision.revision == current_rev else ""
        script_path = script.get_revision(revision.revision).path
        script_info_msg += (
            f"\n{revision.revision} {current_marker}: {revision.doc} "
            f"(Path: {script_path})"
        )
    script_info_msg += f"\n{'=' * 90}"

    logger.info(script_info_msg)

    if current_rev != head_rev:
        logger.error(
            "Database is not at the latest revision. "
            f"Current revision: {current_rev}, latest revision: {head_rev}\n"
            "Please apply existing migration scripts before generating new ones. "
            "Check the listed file paths for migration scripts.\n"
            f"Also you can try the following solutions:\n{_MIGRATION_SOLUTION}\n"
        )
        raise Exception(
            "Check database migration status failed, you can see the error and "
            "solutions above"
        )


def _get_latest_revision(alembic_cfg: AlembicConfig, engine: Engine) -> str:
    """Get the latest revision of the database.

    Args:
        alembic_cfg: Alembic configuration object.
        engine: SQLAlchemy engine instance.

    Returns:
        The latest revision as a string.
    """
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        context = MigrationContext.configure(connection=connection)
        return context.get_current_revision()


def _delete_migration_script(script_path: str):
    """Delete a migration script.

    Args:
        script_path: The path of the migration script to delete.
    """
    if os.path.exists(script_path):
        os.remove(script_path)
        logger.info(f"Deleted migration script at: {script_path}")
    else:
        logger.warning(f"Migration script not found at: {script_path}")


def _ddl_init_and_upgrade(
    default_meta_data_path: str,
    disable_alembic_upgrade: bool,
    alembic_ini_path: Optional[str] = None,
    script_location: Optional[str] = None,
):
    """Initialize and upgrade database metadata

    Args:
        default_meta_data_path (str): default meta data path
        disable_alembic_upgrade (bool): Whether to enable alembic to initialize and
            upgrade database metadata
        alembic_ini_path (Optional[str]): alembic ini path
        script_location (Optional[str]): alembic script location
    """
    if disable_alembic_upgrade:
        logger.info(
            "disable_alembic_upgrade is true, not to initialize and upgrade database "
            "metadata with alembic"
        )
        return
    else:
        warn_msg = (
            "Initialize and upgrade database metadata with alembic, "
            "just run this in your development environment, if you deploy this in "
            "production environment, "
            "please run webserver with --disable_alembic_upgrade"
            "(`python dbgpt/app/dbgpt_server.py "
            "--disable_alembic_upgrade`).\n"
            "we suggest you to use `dbgpt db migration` to initialize and upgrade "
            "database metadata with alembic, "
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
        _check_database_migration_status(alembic_cfg, db.engine)
    except Exception as e:
        logger.error(f"Failed to check database migration status: {e}")
        raise
    latest_revision_before = "__latest_revision_before__"
    new_script_path = None
    try:
        latest_revision_before = _get_latest_revision(alembic_cfg, db.engine)
        # create_new_revision_if_noting_to_update=False avoid creating a lot of empty
        # migration scripts
        # TODO Set create_new_revision_if_noting_to_update=False, not working now.
        new_script_path = create_migration_script(
            alembic_cfg, db.engine, create_new_revision_if_noting_to_update=True
        )
        upgrade_database(alembic_cfg, db.engine)
    except CommandError as e:
        if "Target database is not up to date" in str(e):
            logger.error(
                f"Initialize and upgrade database metadata with alembic failed, error "
                f"detail: {str(e)} "
                f"you can try the following solutions:\n{_MIGRATION_SOLUTION}\n"
            )
            raise Exception(
                "Initialize and upgrade database metadata with alembic failed, "
                "you can see the error and solutions above"
            ) from e
        else:
            latest_revision_after = _get_latest_revision(alembic_cfg, db.engine)
            if latest_revision_before != latest_revision_after:
                logger.error(
                    f"Upgrade database failed. Please review the migration script "
                    f"manually. Failed script path: {new_script_path}\nError: {e}"
                )
            raise e
