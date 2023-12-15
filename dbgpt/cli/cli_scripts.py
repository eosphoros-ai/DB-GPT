import click
import copy
import logging

logging.basicConfig(
    level=logging.WARNING,
    encoding="utf-8",
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("dbgpt_cli")


@click.group()
@click.option(
    "--log-level",
    required=False,
    type=str,
    default="warn",
    help="Log level",
)
@click.version_option()
def cli(log_level: str):
    logger.setLevel(logging.getLevelName(log_level.upper()))


def add_command_alias(command, name: str, hidden: bool = False, parent_group=None):
    if not parent_group:
        parent_group = cli
    new_command = copy.deepcopy(command)
    new_command.hidden = hidden
    parent_group.add_command(new_command, name=name)


@click.group()
def start():
    """Start specific server."""
    pass


@click.group()
def stop():
    """Start specific server."""
    pass


@click.group()
def install():
    """Install dependencies, plugins, etc."""
    pass


@click.group()
def db():
    """Manage your metadata database and your datasources."""
    pass


stop_all_func_list = []


@click.command(name="all")
def stop_all():
    """Stop all servers"""
    for stop_func in stop_all_func_list:
        stop_func()


cli.add_command(start)
cli.add_command(stop)
cli.add_command(install)
cli.add_command(db)
add_command_alias(stop_all, name="all", parent_group=stop)

try:
    from dbgpt.model.cli import (
        model_cli_group,
        start_model_controller,
        stop_model_controller,
        start_model_worker,
        stop_model_worker,
        start_apiserver,
        stop_apiserver,
        _stop_all_model_server,
    )

    add_command_alias(model_cli_group, name="model", parent_group=cli)
    add_command_alias(start_model_controller, name="controller", parent_group=start)
    add_command_alias(start_model_worker, name="worker", parent_group=start)
    add_command_alias(start_apiserver, name="apiserver", parent_group=start)

    add_command_alias(stop_model_controller, name="controller", parent_group=stop)
    add_command_alias(stop_model_worker, name="worker", parent_group=stop)
    add_command_alias(stop_apiserver, name="apiserver", parent_group=stop)
    stop_all_func_list.append(_stop_all_model_server)

except ImportError as e:
    logging.warning(f"Integrating dbgpt model command line tool failed: {e}")

try:
    from dbgpt.app._cli import (
        start_webserver,
        stop_webserver,
        _stop_all_dbgpt_server,
        migration,
    )

    add_command_alias(start_webserver, name="webserver", parent_group=start)
    add_command_alias(stop_webserver, name="webserver", parent_group=stop)
    # Add migration command
    add_command_alias(migration, name="migration", parent_group=db)
    stop_all_func_list.append(_stop_all_dbgpt_server)

except ImportError as e:
    logging.warning(f"Integrating dbgpt webserver command line tool failed: {e}")

try:
    from dbgpt.app.knowledge._cli.knowledge_cli import knowledge_cli_group

    add_command_alias(knowledge_cli_group, name="knowledge", parent_group=cli)
except ImportError as e:
    logging.warning(f"Integrating dbgpt knowledge command line tool failed: {e}")


try:
    from dbgpt.util.tracer.tracer_cli import trace_cli_group

    add_command_alias(trace_cli_group, name="trace", parent_group=cli)
except ImportError as e:
    logging.warning(f"Integrating dbgpt trace command line tool failed: {e}")


def main():
    return cli()


if __name__ == "__main__":
    main()
