import sys
import click
import os
import copy
import logging

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


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
    # TODO not working now
    logging.basicConfig(level=log_level, encoding="utf-8")


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


cli.add_command(start)
cli.add_command(stop)

try:
    from pilot.model.cli import (
        model_cli_group,
        start_model_controller,
        stop_model_controller,
        start_model_worker,
        stop_model_worker,
        start_webserver,
        stop_webserver,
        start_apiserver,
        stop_apiserver,
    )

    add_command_alias(model_cli_group, name="model", parent_group=cli)
    add_command_alias(start_model_controller, name="controller", parent_group=start)
    add_command_alias(start_model_worker, name="worker", parent_group=start)
    add_command_alias(start_webserver, name="webserver", parent_group=start)
    add_command_alias(start_apiserver, name="apiserver", parent_group=start)

    add_command_alias(stop_model_controller, name="controller", parent_group=stop)
    add_command_alias(stop_model_worker, name="worker", parent_group=stop)
    add_command_alias(stop_webserver, name="webserver", parent_group=stop)
    add_command_alias(stop_apiserver, name="apiserver", parent_group=stop)

except ImportError as e:
    logging.warning(f"Integrating dbgpt model command line tool failed: {e}")


def main():
    return cli()


if __name__ == "__main__":
    main()
