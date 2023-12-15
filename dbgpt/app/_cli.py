from typing import Optional
import click
import os
import functools
from dbgpt.app.base import WebServerParameters
from dbgpt.configs.model_config import LOGDIR
from dbgpt.util.parameter_utils import EnvArgumentParser
from dbgpt.util.command_utils import _run_current_with_daemon, _stop_service


@click.command(name="webserver")
@EnvArgumentParser.create_click_option(WebServerParameters)
def start_webserver(**kwargs):
    """Start webserver(dbgpt_server.py)"""
    if kwargs["daemon"]:
        log_file = os.path.join(LOGDIR, "webserver_uvicorn.log")
        _run_current_with_daemon("WebServer", log_file)
    else:
        from dbgpt.app.dbgpt_server import run_webserver

        run_webserver(WebServerParameters(**kwargs))


@click.command(name="webserver")
@click.option(
    "--port",
    type=int,
    default=None,
    required=False,
    help=("The port to stop"),
)
def stop_webserver(port: int):
    """Stop webserver(dbgpt_server.py)"""
    _stop_service("webserver", "WebServer", port=port)


def _stop_all_dbgpt_server():
    _stop_service("webserver", "WebServer")


@click.group("migration")
def migration():
    """Manage database migration"""
    pass


def add_migration_options(func):
    @click.option(
        "--alembic_ini_path",
        required=False,
        type=str,
        default=None,
        show_default=True,
        help="Alembic ini path, if not set, use 'pilot/meta_data/alembic.ini'",
    )
    @click.option(
        "--script_location",
        required=False,
        type=str,
        default=None,
        show_default=True,
        help="Alembic script location, if not set, use 'pilot/meta_data/alembic'",
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@migration.command()
@add_migration_options
@click.option(
    "-m",
    "--message",
    required=False,
    type=str,
    default="Init migration",
    show_default=True,
    help="The message for create migration repository",
)
def init(alembic_ini_path: str, script_location: str, message: str):
    """Initialize database migration repository"""
    from dbgpt.util._db_migration_utils import create_migration_script

    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)
    create_migration_script(alembic_cfg, db_manager.engine, message)


@migration.command()
@add_migration_options
@click.option(
    "-m",
    "--message",
    required=False,
    type=str,
    default="New migration",
    show_default=True,
    help="The message for migration script",
)
def migrate(alembic_ini_path: str, script_location: str, message: str):
    """Create migration script"""
    from dbgpt.util._db_migration_utils import create_migration_script

    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)
    create_migration_script(alembic_cfg, db_manager.engine, message)


@migration.command()
@add_migration_options
def upgrade(alembic_ini_path: str, script_location: str):
    """Upgrade database to target version"""
    from dbgpt.util._db_migration_utils import upgrade_database

    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)
    upgrade_database(alembic_cfg, db_manager.engine)


@migration.command()
@add_migration_options
@click.option(
    "-y",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Confirm to downgrade database",
)
@click.option(
    "-r",
    "--revision",
    default="-1",
    show_default=True,
    help="Revision to downgrade to",
)
def downgrade(alembic_ini_path: str, script_location: str, y: bool, revision: str):
    """Downgrade database to target version"""
    from dbgpt.util._db_migration_utils import downgrade_database

    if not y:
        click.confirm("Are you sure you want to downgrade the database?", abort=True)
    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)
    downgrade_database(alembic_cfg, db_manager.engine, revision)


@migration.command()
@add_migration_options
@click.option(
    "--drop_all_tables",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Drop all tables",
)
@click.option(
    "-y",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Confirm to clean migration data",
)
@click.option(
    "--confirm_drop_all_tables",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Confirm to drop all tables",
)
def clean(
    alembic_ini_path: str,
    script_location: str,
    drop_all_tables: bool,
    y: bool,
    confirm_drop_all_tables: bool,
):
    """Clean Alembic migration scripts and history"""
    from dbgpt.util._db_migration_utils import clean_alembic_migration

    if not y:
        click.confirm(
            "Are you sure clean alembic migration scripts and history?", abort=True
        )
    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)
    clean_alembic_migration(alembic_cfg, db_manager.engine)
    if drop_all_tables:
        if not confirm_drop_all_tables:
            click.confirm("\nAre you sure drop all tables?", abort=True)
        with db_manager.engine.connect() as connection:
            for tbl in reversed(db_manager.Model.metadata.sorted_tables):
                print(f"Drop table {tbl.name}")
                connection.execute(tbl.delete())


@migration.command()
@add_migration_options
def list(alembic_ini_path: str, script_location: str):
    """List all versions in the migration history, marking the current one"""
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)

    # Set up Alembic environment and script directory
    script = ScriptDirectory.from_config(alembic_cfg)

    # Get current revision
    def get_current_revision():
        with db_manager.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

    current_rev = get_current_revision()

    # List all revisions and mark the current one
    for revision in script.walk_revisions():
        current_marker = "(current)" if revision.revision == current_rev else ""
        print(f"{revision.revision} {current_marker}: {revision.doc}")


@migration.command()
@add_migration_options
@click.argument("revision", required=True)
def show(alembic_ini_path: str, script_location: str, revision: str):
    """Show the migration script for a specific version."""
    from alembic.script import ScriptDirectory

    alembic_cfg, db_manager = _get_migration_config(alembic_ini_path, script_location)

    script = ScriptDirectory.from_config(alembic_cfg)

    rev = script.get_revision(revision)
    if rev is None:
        print(f"Revision {revision} not found.")
        return

    # Find the migration script file
    script_files = os.listdir(os.path.join(script.dir, "versions"))
    script_file = next((f for f in script_files if f.startswith(revision)), None)

    if script_file is None:
        print(f"Migration script for revision {revision} not found.")
        return
    # Print the migration script
    script_file_path = os.path.join(script.dir, "versions", script_file)
    print(f"Migration script for revision {revision}: {script_file_path}")
    try:
        with open(script_file_path, "r") as file:
            print(file.read())
    except FileNotFoundError:
        print(f"Migration script {script_file_path} not found.")


def _get_migration_config(
    alembic_ini_path: Optional[str] = None, script_location: Optional[str] = None
):
    from dbgpt.storage.metadata.db_manager import db as db_manager
    from dbgpt.util._db_migration_utils import create_alembic_config

    # Must import dbgpt_server for initialize db metadata
    from dbgpt.app.dbgpt_server import initialize_app as _
    from dbgpt.app.base import _initialize_db

    # initialize db
    default_meta_data_path = _initialize_db()
    alembic_cfg = create_alembic_config(
        default_meta_data_path,
        db_manager.engine,
        db_manager.Model,
        db_manager.session(),
        alembic_ini_path,
        script_location,
    )
    return alembic_cfg, db_manager
