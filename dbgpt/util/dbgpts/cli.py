import functools

import click


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
    "--url",
    type=str,
    required=True,
    help="The URL of the repo",
)
def add_repo(repo: str, url: str):
    """Add a new repo"""
    from .repo import add_repo

    add_repo(repo, url)


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
