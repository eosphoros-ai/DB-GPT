import functools
import importlib.metadata
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from rich.table import Table

from ..console import CliLogger
from ..i18n_utils import _
from .base import (
    DBGPTS_METADATA_FILE,
    DBGPTS_REPO_HOME,
    DEFAULT_PACKAGES,
    DEFAULT_REPO_MAP,
    INSTALL_DIR,
    INSTALL_METADATA_FILE,
    _print_path,
)
from .loader import _load_package_from_path

cl = CliLogger()

_DEFAULT_REPO = "eosphoros/dbgpts"

logger = logging.getLogger(__name__)


def _is_poetry_project(package_path: Path) -> bool:
    """Check if the project uses poetry build system by examining pyproject.toml

    Args:
        package_path (Path): Path to the package directory

    Returns:
        bool: True if the project uses poetry, False otherwise
    """
    pyproject_path = package_path / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    try:
        import tomli  # Python 3.11+ uses tomllib from stdlib
    except ImportError:
        try:
            import tomlkit as tomli
        except ImportError:
            import tomli

    with open(pyproject_path, "rb") as f:
        pyproject_data = tomli.load(f)

    # Check if poetry is defined in build-system
    build_system = pyproject_data.get("build-system", {})
    build_backend = build_system.get("build-backend", "")
    requires = build_system.get("requires", [])

    return (
        "poetry" in build_backend.lower()
        or any("poetry" in req.lower() for req in requires)
        or "tool" in pyproject_data
        and "poetry" in pyproject_data.get("tool", {})
    )


def _is_module_installed(module_name: str) -> bool:
    """Check if a Python module is installed

    Args:
        module_name (str): Module name to check

    Returns:
        bool: True if installed, False otherwise
    """
    try:
        importlib.metadata.distribution(module_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _build_package(
    install_path: Path, is_poetry: bool, log_func=logger.info, error_func=logger.error
) -> tuple[bool, str]:
    """Build package using poetry or build module

    Args:
        install_path (Path): Path to the package
        is_poetry (bool): Whether to use poetry for build
        log_func: Function to use for logging info
        error_func: Function to use for logging errors

    Returns:
        tuple: (success, error_message)
    """
    python_executable = sys.executable
    os.chdir(install_path)

    if is_poetry and shutil.which("poetry"):
        log_func("Building with poetry...")
        process = subprocess.Popen(
            ["poetry", "build"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        # Check if build module is available
        if _is_module_installed("build"):
            log_func("Building with python -m build...")
            process = subprocess.Popen(
                [python_executable, "-m", "build", "--wheel"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            # Fallback to setuptools directly if available
            if (install_path / "setup.py").exists():
                log_func("Building with setuptools directly...")
                process = subprocess.Popen(
                    [python_executable, "setup.py", "bdist_wheel"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                error_msg = (
                    "No suitable build method found. Please install build: "
                    "pip install build"
                )
                error_func(error_msg)
                return False, error_msg

    out, err = process.communicate()
    log_func(f"Build output: {out.decode('utf-8', errors='replace')}")
    if err:
        error_msg = f"Build warnings/errors: {err.decode('utf-8', errors='replace')}"
        log_func(error_msg)

    return process.returncode == 0, "" if process.returncode == 0 else error_msg


def _install_wheel(
    wheel_path: str, log_func=logger.info, error_func=logger.error
) -> tuple[bool, str]:
    """Install wheel file using the best available method

    Args:
        wheel_path (str): Path to the wheel file
        log_func: Function to use for logging info
        error_func: Function to use for logging errors

    Returns:
        tuple: (success, error_message)
    """
    python_executable = sys.executable

    # Try uv first if available (faster)
    if shutil.which("uv"):
        log_func(f"Installing wheel with uv: {wheel_path}")
        process = subprocess.Popen(
            ["uv", "pip", "install", wheel_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = process.communicate()
        if process.returncode == 0:
            return True, ""
        log_func(f"uv install failed: {err.decode('utf-8', errors='replace')}")
        # Fall through to pip if uv fails

    # Try pip
    if shutil.which("pip") or _is_module_installed("pip"):
        log_func(f"Installing wheel with pip: {wheel_path}")
        process = subprocess.Popen(
            [python_executable, "-m", "pip", "install", wheel_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = process.communicate()
        if process.returncode == 0:
            return True, ""
        log_func(f"Pip install failed: {err.decode('utf-8', errors='replace')}")

    # Alternative: Try using importlib directly
    try:
        import site
        import zipfile

        log_func(f"Attempting manual wheel installation for {wheel_path}")

        # Get the site-packages directory
        site_packages = site.getsitepackages()[0]

        # Extract the wheel contents to site-packages
        with zipfile.ZipFile(wheel_path, "r") as wheel_zip:
            # Extract only the Python modules (*.py, *.so, etc.)
            for file in wheel_zip.namelist():
                if ".dist-info/" not in file and file.endswith((".py", ".so", ".pyd")):
                    wheel_zip.extract(file, site_packages)

        log_func(f"Manual installation to {site_packages} completed")
        return True, ""
    except Exception as e:
        error_msg = f"Manual installation failed: {str(e)}"
        error_func(error_msg)
        return False, error_msg


@functools.cache
def list_repos() -> List[str]:
    """List all repos

    Returns:
        List[str]: List of repos
    """
    repos = set()
    for repo in os.listdir(DBGPTS_REPO_HOME):
        full_path = os.path.join(DBGPTS_REPO_HOME, repo)
        if os.path.isdir(full_path):
            for sub_repo in os.listdir(full_path):
                if os.path.isdir(os.path.join(full_path, sub_repo)):
                    repos.add(f"{repo}/{sub_repo}")
    repos.add(_DEFAULT_REPO)
    return sorted(list(repos))


def _get_repo_path(repo: str) -> Path:
    repo_arr = repo.split("/")
    if len(repo_arr) != 2:
        cl.error(
            f"Invalid repo name '{repo}', repo name must split by '/', "
            f"eg.(eosphoros/dbgpts).",
            exit_code=1,
        )
    return Path(DBGPTS_REPO_HOME) / repo_arr[0] / repo_arr[1]


def _list_repos_details() -> List[Tuple[str, str]]:
    repos = list_repos()
    results = []
    for repo in repos:
        repo_arr = repo.split("/")
        repo_group, repo_name = repo_arr
        full_path = os.path.join(DBGPTS_REPO_HOME, repo_group, repo_name)
        results.append((repo, full_path))
    return results


def _print_repos():
    """Print all repos"""
    repos = _list_repos_details()
    repos.sort(key=lambda x: (x[0], x[1]))
    table = Table(title=_("Repos"))
    table.add_column(_("Repository"), justify="right", style="cyan", no_wrap=True)
    table.add_column(_("Path"), justify="right", style="green")
    for repo, full_path in repos:
        full_path = _print_path(full_path)
        table.add_row(repo, full_path)
    cl.print(table)


def _install_default_repos_if_no_repos():
    """Install the default repos if no repos exist."""
    has_repos = False
    for repo, full_path in _list_repos_details():
        if os.path.exists(full_path):
            has_repos = True
            break
    if not has_repos:
        repo_url = DEFAULT_REPO_MAP[_DEFAULT_REPO]
        cl.info(
            f"No repos found, installing default repos {_DEFAULT_REPO} from {repo_url}"
        )
        add_repo(_DEFAULT_REPO, repo_url)


def add_repo(repo: str, repo_url: str, branch: str | None = None):
    """Add a new repo

    Args:
        repo (str): The name of the repo
        repo_url (str): The URL of the repo
        branch (str): The branch of the repo
    """
    exist_repos = list_repos()
    if repo in exist_repos and repo_url not in DEFAULT_REPO_MAP.values():
        cl.error(f"The repo '{repo}' already exists.", exit_code=1)
    repo_arr = repo.split("/")

    if len(repo_arr) != 2:
        cl.error(
            f"Invalid repo name '{repo}', repo name must split by '/', "
            "eg.(eosphoros/dbgpts).",
            exit_code=1,
        )
    repo_name = repo_arr[1]
    repo_group_dir = os.path.join(DBGPTS_REPO_HOME, repo_arr[0])
    os.makedirs(repo_group_dir, exist_ok=True)
    if repo_url.startswith("http") or repo_url.startswith("git"):
        clone_repo(repo, repo_group_dir, repo_name, repo_url, branch)
    elif os.path.isdir(repo_url):
        # Create soft link
        os.symlink(repo_url, os.path.join(repo_group_dir, repo_name))


def remove_repo(repo: str):
    """Remove the specified repo

    Args:
        repo (str): The name of the repo
    """
    repo_path = _get_repo_path(repo)
    if not os.path.exists(repo_path):
        cl.error(f"The repo '{repo}' does not exist.", exit_code=1)
    if os.path.islink(repo_path):
        os.unlink(repo_path)
    else:
        shutil.rmtree(repo_path)
    cl.info(f"Repo '{repo}' removed successfully.")


def clone_repo(
    repo: str,
    repo_group_dir: str,
    repo_name: str,
    repo_url: str,
    branch: str | None = None,
):
    """Clone the specified repo

    Args:
        repo (str): The name of the repo
        repo_group_dir (str): The directory of the repo group
        repo_name (str): The name of the repo
        repo_url (str): The URL of the repo
        branch (str): The branch of the repo
    """
    os.chdir(repo_group_dir)
    clone_command = ["git", "clone", repo_url, repo_name]

    # If the branch is specified, add it to the clone command
    if branch:
        clone_command += ["-b", branch]

    # subprocess.run(clone_command, check=True)
    process = subprocess.Popen(
        clone_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    if branch:
        cl.info(
            f"Repo '{repo}' cloned from {repo_url} with branch '{branch}' successfully."
        )
    else:
        cl.info(f"Repo '{repo}' cloned from {repo_url} successfully.")


def update_repo(repo: str):
    """Update the specified repo

    Args:
        repo (str): The name of the repo
    """
    cl.info(f"Updating repo '{repo}'...")
    repo_path = os.path.join(DBGPTS_REPO_HOME, repo)
    if not os.path.exists(repo_path):
        if repo in DEFAULT_REPO_MAP:
            add_repo(repo, DEFAULT_REPO_MAP[repo])
            if not os.path.exists(repo_path):
                cl.error(f"The repo '{repo}' does not exist.", exit_code=1)
        else:
            cl.error(f"The repo '{repo}' does not exist.", exit_code=1)
    os.chdir(repo_path)
    if not os.path.exists(".git"):
        cl.info(f"Repo '{repo}' is not a git repository.")
        return
    cl.info(f"Updating repo '{repo}'...")
    subprocess.run(["git", "pull"], check=False)


def install(
    name: str,
    repo: str | None = None,
    with_update: bool = True,
):
    """Install the specified dbgpt from the specified repo

    Args:
        name (str): The name of the dbgpt
        repo (str): The name of the repo
        with_update (bool): Whether to update the repo before installing
    """
    repo_info = check_with_retry(name, repo, with_update=with_update, is_first=True)
    if not repo_info:
        cl.error(f"The specified dbgpt '{name}' does not exist.", exit_code=1)
    repo, dbgpt_path = repo_info
    copy_and_install(repo, name, dbgpt_path)


def uninstall(name: str):
    """Uninstall the specified dbgpt

    Args:
        name (str): The name of the dbgpt
    """
    install_path = INSTALL_DIR / name
    if not install_path.exists():
        cl.error(f"The dbgpt '{name}' has not been installed yet.", exit_code=1)
    os.chdir(install_path)
    subprocess.run(["pip", "uninstall", name, "-y"], check=True)
    shutil.rmtree(install_path)
    cl.info(f"Uninstalling dbgpt '{name}'...")


def reinstall(
    name: str,
    repo: str | None = None,
    with_update: bool = True,
):
    """Reinstall the specified dbgpt

    Args:
        name (str): The name of the dbgpt
    """
    uninstall(name)
    install(name, repo, with_update=with_update)


def inner_uninstall(name: str):
    """Uninstall the specified dbgpt

    Args:
        name (str): The name of the dbgpt
    """
    install_path = INSTALL_DIR / name
    if not install_path.exists():
        logger.warning(f"The dbgpt '{name}' has not been installed yet.")
        return
    os.chdir(install_path)
    # subprocess.run(["pip", "uninstall", name, "-y"], check=True)
    process = subprocess.Popen(
        ["pip", "uninstall", name, "-y"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    logger.info(f"{out},{err}")
    shutil.rmtree(install_path)
    logger.info(f"Uninstalling dbgpt '{name}'...")


def inner_copy_and_install(repo: str, name: str, package_path: Path):
    if not package_path.exists():
        raise ValueError(
            f"The specified dbgpt '{name}' does not exist in the {repo} tap."
        )
    install_path = INSTALL_DIR / name
    if install_path.exists():
        logger.info(
            f"The dbgpt '{name}' has already been installed"
            f"({_print_path(install_path)})."
        )
        return True

    try:
        shutil.copytree(package_path, install_path)
        logger.info(f"Installing dbgpts '{name}' from {repo}...")

        # Check if it's a poetry project
        is_poetry = _is_poetry_project(install_path)

        # Build the package
        build_success = _build_package(install_path, is_poetry)
        if not build_success:
            raise ValueError("Failed to build the package")

        wheel_files = list(install_path.glob("dist/*.whl"))
        if not wheel_files:
            logger.error("No wheel file found after building the package.")
            raise ValueError("No wheel file found after building the package.")

        # Install the wheel file
        wheel_file = wheel_files[0]
        logger.info(
            f"Installing dbgpts '{name}' wheel file {_print_path(wheel_file)}..."
        )

        install_success = _install_wheel(str(wheel_file))
        if not install_success:
            raise ValueError(f"Failed to install wheel file: {wheel_file}")

        _write_install_metadata(name, repo, install_path)
        logger.info(f"Installed dbgpts at {_print_path(install_path)}.")
        logger.info(f"dbgpts '{name}' installed successfully.")
        return True
    except Exception as e:
        if install_path.exists():
            shutil.rmtree(install_path)
        raise e


def copy_and_install(repo: str, name: str, package_path: Path):
    """Install the specified dbgpt from a repository

    This function reuses the inner implementation but provides CLI feedback

    Args:
        repo (str): The name of the repo
        name (str): The name of the dbgpt
        package_path (Path): The path to the package
    """
    if not package_path.exists():
        cl.error(
            f"The specified dbgpt '{name}' does not exist in the {repo} tap.",
            exit_code=1,
        )
    install_path = INSTALL_DIR / name
    if install_path.exists():
        cl.error(
            f"The dbgpt '{name}' has already been installed"
            f"({_print_path(install_path)}).",
            exit_code=1,
        )
    try:
        shutil.copytree(package_path, install_path)
        cl.info(f"Installing dbgpts '{name}' from {repo}...")

        # Check if it's a poetry project
        is_poetry = _is_poetry_project(install_path)

        # Build the package using the shared implementation but with CLI logging
        build_success, build_error = _build_package(
            install_path, is_poetry, log_func=cl.info, error_func=cl.error
        )

        if not build_success:
            cl.error(f"Failed to build the package: {build_error}", exit_code=1)

        wheel_files = list(install_path.glob("dist/*.whl"))
        if not wheel_files:
            cl.error("No wheel file found after building the package.", exit_code=1)

        # Install the wheel file using the shared implementation but with CLI logging
        wheel_file = wheel_files[0]
        cl.info(f"Installing dbgpts '{name}' wheel file {_print_path(wheel_file)}...")

        install_success, install_error = _install_wheel(
            str(wheel_file), log_func=cl.info, error_func=cl.error
        )

        if not install_success:
            cl.error(f"Failed to install wheel file: {install_error}", exit_code=1)

        _write_install_metadata(name, repo, install_path)
        cl.success(f"Installed dbgpts at {_print_path(install_path)}.")
        cl.success(f"dbgpts '{name}' installed successfully.")
    except Exception as e:
        if install_path.exists():
            shutil.rmtree(install_path)
        raise e


def _write_install_metadata(name: str, repo: str, install_path: Path):
    import tomlkit

    install_metadata = {
        "name": name,
        "repo": repo,
    }
    with open(install_path / INSTALL_METADATA_FILE, "w") as f:
        tomlkit.dump(install_metadata, f)


def check_with_retry(
    name: str,
    spec_repo: str | None = None,
    with_update: bool = False,
    is_first: bool = False,
) -> Tuple[str, Path] | None:
    """Check the specified dbgpt with retry.

    Args:
        name (str): The name of the dbgpt
        spec_repo (str): The name of the repo
        with_update (bool): Whether to update the repo before installing
        is_first (bool): Whether it's the first time to check the dbgpt
    Returns:
        Tuple[str, Path] | None: The repo and the path of the dbgpt
    """
    repos = _list_repos_details()
    if spec_repo:
        repos = list(filter(lambda x: x[0] == spec_repo, repos))
        if not repos:
            cl.error(f"The specified repo '{spec_repo}' does not exist.", exit_code=1)
    if is_first and with_update:
        for repo in repos:
            update_repo(repo[0])
    for repo in repos:
        repo_path = Path(repo[1])
        for package in DEFAULT_PACKAGES:
            dbgpt_path = repo_path / package / name
            dbgpt_metadata_path = dbgpt_path / DBGPTS_METADATA_FILE
            if (
                dbgpt_path.exists()
                and dbgpt_path.is_dir()
                and dbgpt_metadata_path.exists()
            ):
                return repo[0], dbgpt_path
    if is_first:
        return check_with_retry(
            name, spec_repo, with_update=with_update, is_first=False
        )
    return None


def list_repo_apps(repo: str | None = None, with_update: bool = True):
    """List all installed dbgpts"""
    repos = _list_repos_details()
    if repo:
        repos = list(filter(lambda x: x[0] == repo, repos))
        if not repos:
            cl.error(f"The specified repo '{repo}' does not exist.", exit_code=1)
    if with_update:
        for repo in repos:
            update_repo(repo[0])
    table = Table(title=_("dbgpts In All Repos"))

    table.add_column(_("Repository"), justify="right", style="cyan", no_wrap=True)
    table.add_column(_("Type"), style="magenta")
    table.add_column(_("Name"), justify="right", style="green")

    data = []
    for repo in repos:
        repo_path = Path(repo[1])
        for package in DEFAULT_PACKAGES:
            dbgpt_path = repo_path / package
            for app in os.listdir(dbgpt_path):
                dbgpt_metadata_path = dbgpt_path / app / DBGPTS_METADATA_FILE
                if (
                    dbgpt_path.exists()
                    and dbgpt_path.is_dir()
                    and dbgpt_metadata_path.exists()
                ):
                    data.append((repo[0], package, app))
    # Sort by repo name, package name, and app name
    data.sort(key=lambda x: (x[0], x[1], x[2]))
    for repo, package, app in data:
        table.add_row(repo, package, app)
    cl.print(table)


def update_repo_inner(repo: str):
    logger.info(f"Updating repo '{repo}'...")
    repo_path = os.path.join(DBGPTS_REPO_HOME, repo)
    if not os.path.exists(repo_path):
        if repo in DEFAULT_REPO_MAP:
            add_repo(repo, DEFAULT_REPO_MAP[repo])
            if not os.path.exists(repo_path):
                raise ValueError(f"The repo '{repo}' does not exist.")
        else:
            raise ValueError(f"The repo '{repo}' does not exist.")
    os.chdir(repo_path)
    if not os.path.exists(".git"):
        logger.info(f"Repo '{repo}' is not a git repository.")
        return
    logger.info(f"Updating repo '{repo}'...")

    process = subprocess.Popen(
        ["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    logger.info(f"{out},{err}")


def list_dbgpts(
    spec_repo: str | None = None, with_update: bool = True
) -> List[Tuple[str, str, str, str]]:
    """scan dbgpts in repo

    Args:
        spec_repo:  The name of the repo

    Returns:
        Tuple[str, Path] | None: The repo and the path of the dbgpt
    """
    repos = _list_repos_details()
    if spec_repo:
        repos = list(filter(lambda x: x[0] == spec_repo, repos))
        if not repos:
            raise ValueError(f"The specified repo '{spec_repo}' does not exist.")
    if with_update:
        for repo in repos:
            update_repo_inner(repo[0])
    data = []
    for repo in repos:
        repo_path = Path(repo[1])
        for package in DEFAULT_PACKAGES:
            dbgpt_path = repo_path / package
            for app in os.listdir(dbgpt_path):
                gpts_path = dbgpt_path / app
                dbgpt_metadata_path = dbgpt_path / app / DBGPTS_METADATA_FILE
                if (
                    dbgpt_path.exists()
                    and dbgpt_path.is_dir()
                    and dbgpt_metadata_path.exists()
                ):
                    data.append((repo[0], package, app, gpts_path))
    return data


def list_installed_apps():
    """List all installed dbgpts"""
    packages = _load_package_from_path(INSTALL_DIR)
    table = Table(title=_("Installed dbgpts"))

    table.add_column(_("Name"), justify="right", style="cyan", no_wrap=True)
    table.add_column(_("Type"), style="blue")
    table.add_column(_("Repository"), style="magenta")
    table.add_column(_("Path"), justify="right", style="green")

    packages.sort(key=lambda x: (x.package, x.package_type, x.repo))
    for package in packages:
        str_path = package.root
        str_path = _print_path(str_path)
        table.add_row(package.package, package.package_type, package.repo, str_path)
    cl.print(table)
