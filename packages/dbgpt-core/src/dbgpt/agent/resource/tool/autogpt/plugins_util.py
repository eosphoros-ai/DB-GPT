"""Load plugins from a directory or a zip file.

This module provides utility functions to load auto_gpt plugins from a directory or a
zip file.
"""

import datetime
import glob
import ipaddress
import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import urljoin, urlsplit

if TYPE_CHECKING:
    from auto_gpt_plugin_template import AutoGPTPluginTemplate

logger = logging.getLogger(__name__)


def inspect_zip_for_modules(zip_path: str, debug: bool = False) -> list[str]:
    """Load the AutoGPTPluginTemplate from a zip file.

    Loader zip plugin file. Native support Auto_gpt_plugin

    Args:
    zip_path (str): Path to the zipfile.
    debug (bool, optional): Enable debug logging. Defaults to False.

    Returns:
    list[str]: The list of module names found or empty list if none were found.
    """
    import zipfile

    result = []
    with zipfile.ZipFile(zip_path, "r") as zfile:
        for name in zfile.namelist():
            if name.endswith("__init__.py") and not name.startswith("__MACOSX"):
                logger.debug(f"Found module '{name}' in the zipfile at: {name}")
                result.append(name)
    if len(result) == 0:
        logger.debug(f"Module '__init__.py' not found in the zipfile @ {zip_path}.")
    return result


def write_dict_to_json_file(data: dict, file_path: str) -> None:
    """Write a dictionary to a JSON file.

    Args:
        data (dict): Dictionary to write.
        file_path (str): Path to the file.
    """
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def create_directory_if_not_exists(directory_path: str) -> bool:
    """Create a directory if it does not exist.

    Args:
        directory_path (str): Path to the directory.
    Returns:
        bool: True if the directory was created, else False.
    """
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            logger.debug(f"Created directory: {directory_path}")
            return True
        except OSError as e:
            logger.warning(f"Error creating directory {directory_path}: {e}")
            return False
    else:
        logger.info(f"Directory {directory_path} already exists")
        return True


def scan_plugin_file(file_path, debug: bool = False) -> List["AutoGPTPluginTemplate"]:
    """Scan a plugin file and load the plugins."""
    from zipimport import zipimporter

    logger.info(f"__scan_plugin_file:{file_path},{debug}")
    loaded_plugins = []
    if moduleList := inspect_zip_for_modules(str(file_path), debug):
        for module in moduleList:
            plugin = Path(file_path)
            module = Path(module)  # type: ignore
            logger.debug(f"Plugin: {plugin} Module: {module}")
            zipped_package = zipimporter(str(plugin))
            zipped_module = zipped_package.load_module(
                str(module.parent)  # type: ignore
            )
            for key in dir(zipped_module):
                if key.startswith("__"):
                    continue
                a_module = getattr(zipped_module, key)
                a_keys = dir(a_module)
                if (
                    "_abc_impl" in a_keys
                    and a_module.__name__ != "AutoGPTPluginTemplate"
                    # and denylist_allowlist_check(a_module.__name__, cfg)
                ):
                    loaded_plugins.append(a_module())
    return loaded_plugins


def scan_plugins(
    plugins_file_path: str, file_name: str = "", debug: bool = False
) -> List["AutoGPTPluginTemplate"]:
    """Scan the plugins directory for plugins and loads them.

    Args:
        cfg (Config): Config instance including plugins config
        debug (bool, optional): Enable debug logging. Defaults to False.

    Returns:
        List[Tuple[str, Path]]: List of plugins.
    """
    loaded_plugins = []
    # Generic plugins
    plugins_path = Path(plugins_file_path)
    if file_name:
        plugin_path = Path(plugins_path, file_name)
        loaded_plugins = scan_plugin_file(plugin_path)
    else:
        for plugin_path in plugins_path.glob("*.zip"):
            loaded_plugins.extend(scan_plugin_file(plugin_path))

    if loaded_plugins:
        logger.info(f"\nPlugins found: {len(loaded_plugins)}\n--------------------")
    for plugin in loaded_plugins:
        logger.info(f"{plugin._name}: {plugin._version} - {plugin._description}")
    return loaded_plugins


_GITHUB_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9._/+-]+$")
_ALLOWED_GITHUB_HOSTS = frozenset({"github.com"})
_ALLOWED_DOWNLOAD_HOSTS = frozenset({"github.com", "codeload.github.com"})
_MAX_REDIRECTS = 5
_REQUEST_TIMEOUT = 30


def _validate_github_repo_url(github_repo: str) -> tuple[str, str]:
    """Validate and canonicalize a GitHub repository HTTPS URL."""
    parsed = urlsplit(github_repo.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError(f"Not a correct Github repository address: {github_repo}")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError(f"Not a correct Github repository address: {github_repo}")
    hostname = (parsed.hostname or "").lower()
    if hostname not in _ALLOWED_GITHUB_HOSTS:
        raise ValueError(f"Not a correct Github repository address: {github_repo}")
    if parsed.query or parsed.fragment:
        raise ValueError(f"Not a correct Github repository address: {github_repo}")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise ValueError(f"Not a correct Github repository address: {github_repo}")
    owner, repo = parts
    repo = repo.removesuffix(".git")
    for segment in (owner, repo):
        if segment in ("", ".", "..") or not _GITHUB_SEGMENT_RE.match(segment):
            raise ValueError(f"Not a correct Github repository address: {github_repo}")

    return f"https://github.com/{owner}/{repo}", repo


def _validate_branch_name(branch_name: str) -> str:
    """Validate a git branch name for safe URL construction and filenames."""
    branch = branch_name.strip()
    if not branch or not _BRANCH_NAME_RE.match(branch):
        raise ValueError(f"Invalid branch name: {branch_name}")
    if any(seg in ("", ".", "..") for seg in branch.split("/")):
        raise ValueError(f"Invalid branch name: {branch_name}")
    return branch


def _validate_download_url(url: str) -> str:
    """Ensure archive fetch and redirect URLs stay on allowlisted GitHub HTTPS hosts."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"Disallowed plugin download scheme: {url}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"Disallowed credentials in download URL: {url}")
    if parsed.port not in (None, 443):
        raise ValueError(f"Disallowed port in download URL: {url}")
    hostname = (parsed.hostname or "").lower()
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError(f"Disallowed IP literal host in download URL: {url}")
    if hostname not in _ALLOWED_DOWNLOAD_HOSTS:
        raise ValueError(f"Disallowed plugin download host: {url}")
    return url


def update_from_git(
    download_path: str,
    github_repo: str = "",
    branch_name: str = "main",
    authorization: Optional[str] = None,
):
    """Update plugins from a git repository."""
    import requests

    os.makedirs(download_path, exist_ok=True)
    branch_name = _validate_branch_name(branch_name)
    if github_repo:
        canonical_repo, plugin_repo_name = _validate_github_repo_url(github_repo)
        url = f"{canonical_repo}/archive/refs/heads/{branch_name}.zip"
    else:
        url = (
            "https://github.com/eosphoros-ai/DB-GPT-Plugins/archive/refs/heads/main.zip"
        )
        plugin_repo_name = "DB-GPT-Plugins"
    try:
        session = requests.Session()
        current_url = _validate_download_url(url)
        response = None
        for _ in range(_MAX_REDIRECTS + 1):
            host = (urlsplit(current_url).hostname or "").lower()
            headers = {}
            if (
                authorization
                and len(authorization) > 0
                and host in _ALLOWED_GITHUB_HOSTS
            ):
                headers = {"Authorization": authorization}
            response = session.get(
                current_url,
                headers=headers,
                allow_redirects=False,
                timeout=_REQUEST_TIMEOUT,
            )
            if response.is_redirect or response.status_code in (
                301,
                302,
                303,
                307,
                308,
            ):
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Redirect missing Location header")
                current_url = _validate_download_url(urljoin(current_url, location))
                continue
            break
        else:
            raise ValueError("Too many redirects while downloading plugin")

        if response is not None and response.status_code == 200:
            plugins_path_path = Path(download_path).resolve()
            files = glob.glob(os.path.join(plugins_path_path, f"{plugin_repo_name}*"))
            for file in files:
                os.remove(file)
            now = datetime.datetime.now()
            time_str = now.strftime("%Y%m%d%H%M%S")
            safe_branch = branch_name.replace("/", "_")
            dest_path = (
                plugins_path_path / f"{plugin_repo_name}-{safe_branch}-{time_str}.zip"
            ).resolve()
            if dest_path.parent != plugins_path_path:
                raise ValueError(
                    "Resolved plugin archive path escapes download directory"
                )
            print(dest_path)
            with open(dest_path, "wb") as f:
                f.write(response.content)
            return plugin_repo_name
        else:
            status = response.status_code if response is not None else "unknown"
            logger.error(f"Update plugins failed, response code: {status}")
            raise ValueError(f"Download plugin failed: {status}")
    except Exception as e:
        logger.error("update plugins from git exception!" + str(e))
        raise ValueError("download plugin exception!", e)


def __fetch_from_git(local_path, git_url):
    import git

    logger.info("fetch plugins from git to local path:{}", local_path)
    os.makedirs(local_path, exist_ok=True)
    repo = git.Repo(local_path)
    if repo.is_repo():
        repo.remotes.origin.pull()
    else:
        git.Repo.clone_from(git_url, local_path)

    # if repo.head.is_valid():
    # clone succ， fetch plugins info
