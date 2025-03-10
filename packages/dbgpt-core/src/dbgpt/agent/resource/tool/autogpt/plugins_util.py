"""Load plugins from a directory or a zip file.

This module provides utility functions to load auto_gpt plugins from a directory or a
zip file.
"""

import datetime
import glob
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

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
            logger.warn(f"Error creating directory {directory_path}: {e}")
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


def update_from_git(
    download_path: str,
    github_repo: str = "",
    branch_name: str = "main",
    authorization: Optional[str] = None,
):
    """Update plugins from a git repository."""
    import requests

    os.makedirs(download_path, exist_ok=True)
    if github_repo:
        if github_repo.index("github.com") <= 0:
            raise ValueError("Not a correct Github repository address！" + github_repo)
        github_repo = github_repo.replace(".git", "")
        url = github_repo + "/archive/refs/heads/" + branch_name + ".zip"
        plugin_repo_name = github_repo.strip("/").split("/")[-1]
    else:
        url = (
            "https://github.com/eosphoros-ai/DB-GPT-Plugins/archive/refs/heads/main.zip"
        )
        plugin_repo_name = "DB-GPT-Plugins"
    try:
        session = requests.Session()
        headers = {}
        if authorization and len(authorization) > 0:
            headers = {"Authorization": authorization}
        response = session.get(
            url,
            headers=headers,
        )

        if response.status_code == 200:
            plugins_path_path = Path(download_path)
            files = glob.glob(os.path.join(plugins_path_path, f"{plugin_repo_name}*"))
            for file in files:
                os.remove(file)
            now = datetime.datetime.now()
            time_str = now.strftime("%Y%m%d%H%M%S")
            file_name = (
                f"{plugins_path_path}/{plugin_repo_name}-{branch_name}-{time_str}.zip"
            )
            print(file_name)
            with open(file_name, "wb") as f:
                f.write(response.content)
            return plugin_repo_name
        else:
            logger.error(
                f"Update plugins failed，response code：{response.status_code}"
            )
            raise ValueError(f"Download plugin failed: {response.status_code}")
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
