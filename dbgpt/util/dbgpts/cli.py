import functools
import subprocess
import sys
from pathlib import Path

import click

from .base import DEFAULT_PACKAGE_TYPES


def check_poetry_installed():
    try:
        # Check if poetry is installed
        subprocess.run(
            ["poetry", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Poetry is not installed. Please install Poetry to proceed.")
        print(
            "Visit https://python-poetry.org/docs/#installation for installation "
            "instructions."
        )
        # Exit with error
        sys.exit(1)


def add_tap_options(func):
    @click.option(
        "-r",
        "--repo",
        type=str,
        default=None,
        required=False,
        help="The repository to install the dbgpts from",
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.command(name="install")
@add_tap_options
@click.argument("name", type=str)
def install(repo: str | None, name: str):
    """Install your dbgpts(operators,agents,workflows or apps)"""
    from .repo import install

    check_poetry_installed()
    install(name, repo)


@click.command(name="uninstall")
@click.argument("name", type=str)
def uninstall(name: str):
    """Uninstall your dbgpts(operators,agents,workflows or apps)"""
    from .repo import uninstall

    uninstall(name)


@click.command(name="list")
def list_all_apps():
    """List all installed dbgpts"""
    from .repo import list_repo_apps

    list_repo_apps()


@click.command(name="list")
def list_repos():
    """List all repos"""
    from .repo import list_repos

    print("\n".join(list_repos()))


@click.command(name="add")
@add_tap_options
@click.option(
    "-b",
    "--branch",
    type=str,
    default=None,
    required=False,
    help="The branch of the repository(Just for git repo)",
)
@click.option(
    "--url",
    type=str,
    required=True,
    help="The URL of the repo",
)
def add_repo(repo: str, branch: str | None, url: str):
    """Add a new repo"""
    from .repo import add_repo

    add_repo(repo, url, branch)


@click.command(name="remove")
@click.argument("repo", type=str)
def remove_repo(repo: str):
    """Remove the specified repo"""
    from .repo import remove_repo

    remove_repo(repo)


@click.command(name="update")
@click.option(
    "-r",
    "--repo",
    type=str,
    default=None,
    required=False,
    help="The repository to update(Default: all repos)",
)
def update_repo(repo: str | None):
    """Update the specified repo"""
    from .repo import list_repos, update_repo

    for p in list_repos():
        if repo:
            if p == repo or repo == "all":
                print(f"Updating repo '{p}'...")
                update_repo(p)

        else:
            print(f"Updating repo '{p}'...")
            update_repo(p)


@click.command(name="app")
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help="The name you want to give to the dbgpt",
)
@click.option(
    "-l",
    "--label",
    type=str,
    default=None,
    required=False,
    help="The label of the dbgpt",
)
@click.option(
    "-d",
    "--description",
    type=str,
    default=None,
    required=False,
    help="The description of the dbgpt",
)
@click.option(
    "-t",
    "--type",
    type=click.Choice(DEFAULT_PACKAGE_TYPES),
    default="flow",
    required=False,
    help="The type of the dbgpt",
)
@click.option(
    "--definition_type",
    type=click.Choice(["json", "python"]),
    default="json",
    required=False,
    help="The definition type of the dbgpt",
)
@click.option(
    "-C",
    "--directory",
    type=str,
    default=None,
    required=False,
    help="The working directory of the dbgpt(defaults to the current directory).",
)
def new_dbgpts(
    name: str,
    label: str | None,
    description: str | None,
    type: str,
    definition_type: str,
    directory: str | None,
):
    """New a dbgpts module structure"""
    if not label:
        # Set label to the name
        default_label = name.replace("-", " ").replace("_", " ").title()
        label = click.prompt(
            "Please input the label of the dbgpt", default=default_label
        )
    if not description:
        # Read with click
        description = click.prompt(
            "Please input the description of the dbgpt", default=""
        )
    if not directory:
        # Set directory to the current directory(abs path)
        directory = click.prompt(
            "Please input the working directory of the dbgpt",
            default=str(Path.cwd()),
            type=click.Path(exists=True, file_okay=False, dir_okay=True),
        )

    check_poetry_installed()
    from .template import create_template

    create_template(name, label, description, type, definition_type, directory)
