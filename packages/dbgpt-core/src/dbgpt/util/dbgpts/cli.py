import functools
import shutil
import subprocess
from pathlib import Path

import click

from ..console import CliLogger
from .base import DEFAULT_PACKAGE_TYPES

cl = CliLogger()


def check_build_tools_installed():
    """Check if any supported build tools are installed (uv, poetry, build, or
    setuptools)

    Warns if uv is not installed but does not exit.
    Only exits if no build tools are available.
    """
    tools_available = []

    # Check for uv (preferred tool)
    if shutil.which("uv"):
        try:
            subprocess.run(
                ["uv", "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            tools_available.append("uv")
        except subprocess.CalledProcessError:
            pass

    # Check for poetry
    if shutil.which("poetry"):
        try:
            subprocess.run(
                ["poetry", "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            tools_available.append("poetry")
        except subprocess.CalledProcessError:
            pass

    # Check for build package
    try:
        # Check if python and build are available
        result = subprocess.run(
            ["python", "-c", "import build; print('yes')"],
            check=True,
            capture_output=True,
            text=True,
        )
        if "yes" in result.stdout:
            tools_available.append("build")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check for python with setuptools
    try:
        # Check if python and setuptools are available for basic package building
        result = subprocess.run(
            ["python", "-c", "import setuptools; print('yes')"],
            check=True,
            capture_output=True,
            text=True,
        )
        if "yes" in result.stdout:
            tools_available.append("setuptools")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Provide appropriate feedback based on available tools
    if not tools_available:
        cl.error("No build tools found. Please install one of the following:")
        cl.error(" - uv: A fast Python package installer and resolver (recommended)")
        cl.error(" - poetry: A Python package and dependency manager")
        cl.error(" - build: A PEP 517 compatible Python package builder")
        cl.error(" - setuptools: A classic Python package build system")
        cl.error(
            "For uv: https://github.com/astral-sh/uv\n"
            "For poetry: https://python-poetry.org/docs/#installation\n"
            "For build: pip install build\n"
            "For setuptools: pip install setuptools",
            exit_code=1,
        )
    elif "uv" not in tools_available:
        cl.warning(
            "uv is not installed. We recommend using uv for better performance."
            " Install with: 'pip install uv' or visit https://github.com/astral-sh/uv"
        )
        if "build" not in tools_available:
            cl.warning(
                "build package is not installed. For better compatibility without uv,"
                " we recommend installing it with: 'pip install build'"
            )

    return tools_available


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


def add_add_common_options(func):
    @click.option(
        "-r",
        "--repo",
        type=str,
        default=None,
        required=False,
        help="The repository to install the dbgpts from",
    )
    @click.option(
        "-U",
        "--update",
        type=bool,
        required=False,
        default=False,
        is_flag=True,
        help="Whether to update the repo",
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.command(name="install")
@add_add_common_options
@click.argument("names", type=str, nargs=-1)
def install(repo: str | None, update: bool, names: list[str]):
    """Install your dbgpts(operators,agents,workflows or apps)"""
    from .repo import _install_default_repos_if_no_repos, install

    check_build_tools_installed()
    _install_default_repos_if_no_repos()
    for name in names:
        install(name, repo, with_update=update)


@click.command(name="uninstall")
@click.argument("names", type=str, nargs=-1)
def uninstall(names: list[str]):
    """Uninstall your dbgpts(operators,agents,workflows or apps)"""
    from .repo import uninstall

    for name in names:
        uninstall(name)


@click.command(name="reinstall")
@add_add_common_options
@click.argument("names", type=str, nargs=-1)
def reinstall(repo: str | None, update: bool, names: list[str]):
    """Reinstall your dbgpts(operators,agents,workflows or apps)"""
    from .repo import reinstall

    for name in names:
        reinstall(name, repo, with_update=update)


@click.command(name="list-remote")
@add_add_common_options
def list_all_apps(
    repo: str | None,
    update: bool,
):
    """List all available dbgpts"""
    from .repo import _install_default_repos_if_no_repos, list_repo_apps

    _install_default_repos_if_no_repos()
    list_repo_apps(repo, with_update=update)


@click.command(name="list")
def list_installed_apps():
    """List all installed dbgpts"""
    from .repo import list_installed_apps

    list_installed_apps()


@click.command(name="list")
def list_repos():
    """List all repos"""
    from .repo import _print_repos

    _print_repos()


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

    check_build_tools_installed()
    from .template import create_template

    create_template(name, label, description, type, definition_type, directory)
