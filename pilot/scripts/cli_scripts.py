import sys
import click
import os
import copy
import logging

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
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


def add_command_alias(command, name: str, hidden: bool = False):
    new_command = copy.deepcopy(command)
    new_command.hidden = hidden
    cli.add_command(new_command, name=name)


try:
    from pilot.model.cli import model_cli_group

    add_command_alias(model_cli_group, name="model")
except ImportError as e:
    logging.warning(f"Integrating dbgpt model command line tool failed: {e}")


def main():
    return cli()


if __name__ == "__main__":
    main()
