import ast
import glob
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from dbgpt.agent.core.schema import PluginStorageType
from dbgpt.agent.resource.tool.autogpt.plugins_util import scan_plugins, update_from_git
from dbgpt.configs.model_config import PLUGINS_DIR
from dbgpt_serve.agent.hub.db.my_plugin_db import MyPluginDao, MyPluginEntity
from dbgpt_serve.agent.hub.db.plugin_hub_db import PluginHubDao, PluginHubEntity

logger = logging.getLogger(__name__)
Default_User = "default"
DEFAULT_PLUGIN_REPO = "https://github.com/eosphoros-ai/DB-GPT-Plugins.git"
TEMP_PLUGIN_PATH = ""


class PluginHub:
    def __init__(self, plugin_dir) -> None:
        self.hub_dao = PluginHubDao()
        self.my_plugin_dao = MyPluginDao()
        os.makedirs(plugin_dir, exist_ok=True)
        self.plugin_dir = plugin_dir
        self.temp_hub_file_path = os.path.join(plugin_dir, "temp")
        # Disallowed modules that might lead to RCE
        self.disallowed_imports = {
            "subprocess",
            "os.system",
            "os.popen",
            "os.spawn",
            "os.exec",
            "eval",
            "exec",
            "compile",
            "pty",
            "commands",
            "asyncio.create_subprocess",
            "multiprocessing",
            "pickle",
            "marshal",
            "shelve",
        }
        # Disallowed AST nodes that could be used for code execution
        self.disallowed_ast_nodes = {ast.Expr, ast.Call}

    def _validate_plugin_code(self, file_path: str) -> bool:
        """Validate plugin code for potentially malicious operations.

        Args:
            file_path: Path to the Python file to validate

        Returns:
            bool: True if the code is safe, raises an exception otherwise
        """
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Parse the code into an AST
        try:
            tree = ast.parse(code)
        except SyntaxError:
            raise ValueError("Plugin contains invalid Python syntax")

        # Check for potentially dangerous imports
        for node in ast.walk(tree):
            # Check for import statements
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in self.disallowed_imports:
                        raise ValueError(
                            f"Plugin contains disallowed import: {name.name}"
                        )

            # Check for from ... import statements
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in self.disallowed_imports:
                    raise ValueError(f"Plugin contains disallowed import: {module}")

                for name in node.names:
                    combined = f"{module}.{name.name}" if module else name.name
                    if (
                        combined in self.disallowed_imports
                        or name.name in self.disallowed_imports
                    ):
                        raise ValueError(
                            f"Plugin contains disallowed import: {combined}"
                        )

            # Check for calls to dangerous functions
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "compile"}:
                        raise ValueError(
                            f"Plugin contains potentially dangerous function call: "
                            f"{node.func.id}"
                        )
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "os" and node.func.attr in {
                            "system",
                            "popen",
                            "spawn",
                            "exec",
                        }:
                            raise ValueError(
                                f"Plugin contains potentially dangerous function call: "
                                f"os.{node.func.attr}"
                            )

        return True

    def install_plugin(self, plugin_name: str, user_name: str = None):
        logger.info(f"install_plugin {plugin_name}")
        plugin_entity = self.hub_dao.get_by_name(plugin_name)
        if plugin_entity:
            if plugin_entity.storage_channel == PluginStorageType.Git.value:
                try:
                    branch_name = None
                    authorization = None
                    if plugin_entity.download_param:
                        download_param = json.loads(plugin_entity.download_param)
                        branch_name = download_param.get("branch_name")
                        authorization = download_param.get("authorization")
                    file_name = self.__download_from_git(
                        plugin_entity.storage_url, branch_name, authorization
                    )

                    # add to my plugins and edit hub status
                    plugin_entity.installed = plugin_entity.installed + 1

                    my_plugin_entity = self.my_plugin_dao.get_by_user_and_plugin(
                        user_name, plugin_name
                    )
                    if my_plugin_entity is None:
                        my_plugin_entity = self.__build_my_plugin(plugin_entity)
                    my_plugin_entity.file_name = file_name
                    if user_name:
                        # TODO use user
                        my_plugin_entity.user_code = user_name
                        my_plugin_entity.user_name = user_name
                        my_plugin_entity.tenant = ""
                    else:
                        my_plugin_entity.user_code = Default_User

                    with self.hub_dao.session() as session:
                        if my_plugin_entity.id is None:
                            session.add(my_plugin_entity)
                        else:
                            session.merge(my_plugin_entity)
                        session.merge(plugin_entity)
                except Exception as e:
                    logger.error("install pluguin exception!", e)
                    raise ValueError(f"Install Plugin {plugin_name} Faild! {str(e)}")
            else:
                raise ValueError(
                    f"Unsupport Storage Channel {plugin_entity.storage_channel}!"
                )
        else:
            raise ValueError(f"Can't Find Plugin {plugin_name}!")

    def uninstall_plugin(self, plugin_name, user):
        logger.info(f"uninstall_plugin:{plugin_name},{user}")
        plugin_entity = self.hub_dao.get_by_name(plugin_name)
        my_plugin_entity = self.my_plugin_dao.get_by_user_and_plugin(user, plugin_name)
        if plugin_entity is not None:
            plugin_entity.installed = plugin_entity.installed - 1
        with self.hub_dao.session() as session:
            my_plugin_q = session.query(MyPluginEntity).filter(
                MyPluginEntity.name == plugin_name
            )
            if user:
                my_plugin_q.filter(MyPluginEntity.user_code == user)
            my_plugin_q.delete()
            if plugin_entity is not None:
                session.merge(plugin_entity)

        if plugin_entity is not None:
            # delete package file if not use
            plugin_infos = self.hub_dao.get_by_storage_url(plugin_entity.storage_url)
            have_installed = False
            for plugin_info in plugin_infos:
                if plugin_info.installed > 0:
                    have_installed = True
                    break
            if not have_installed:
                plugin_repo_name = (
                    plugin_entity.storage_url.replace(".git", "")
                    .strip("/")
                    .split("/")[-1]
                )
                files = glob.glob(os.path.join(self.plugin_dir, f"{plugin_repo_name}*"))
                for file in files:
                    os.remove(file)
        else:
            files = glob.glob(
                os.path.join(self.plugin_dir, f"{my_plugin_entity.file_name}")
            )
            for file in files:
                os.remove(file)

    def __download_from_git(self, github_repo, branch_name, authorization):
        return update_from_git(self.plugin_dir, github_repo, branch_name, authorization)

    def __build_my_plugin(self, hub_plugin: PluginHubEntity) -> MyPluginEntity:
        my_plugin_entity = MyPluginEntity()
        my_plugin_entity.name = hub_plugin.name
        my_plugin_entity.type = hub_plugin.type
        my_plugin_entity.version = hub_plugin.version
        return my_plugin_entity

    def refresh_hub_from_git(
        self,
        github_repo: str = None,
        branch_name: str = "main",
        authorization: str = None,
    ):
        logger.info("refresh_hub_by_git start!")
        update_from_git(
            self.temp_hub_file_path, github_repo, branch_name, authorization
        )
        git_plugins = scan_plugins(self.temp_hub_file_path)
        try:
            for git_plugin in git_plugins:
                old_hub_info = self.hub_dao.get_by_name(git_plugin._name)
                if old_hub_info:
                    plugin_hub_info = old_hub_info
                else:
                    plugin_hub_info = PluginHubEntity()
                    plugin_hub_info.type = ""
                    plugin_hub_info.storage_channel = PluginStorageType.Git.value
                    plugin_hub_info.storage_url = DEFAULT_PLUGIN_REPO
                    plugin_hub_info.author = getattr(git_plugin, "_author", "DB-GPT")
                    plugin_hub_info.email = getattr(git_plugin, "_email", "")
                    download_param = {}
                    if branch_name:
                        download_param["branch_name"] = branch_name
                    if authorization and len(authorization) > 0:
                        download_param["authorization"] = authorization
                    plugin_hub_info.download_param = json.dumps(download_param)
                    plugin_hub_info.installed = 0

                plugin_hub_info.name = git_plugin._name
                plugin_hub_info.version = git_plugin._version
                plugin_hub_info.description = git_plugin._description
                self.hub_dao.raw_update(plugin_hub_info)
        except Exception as e:
            raise ValueError(f"Update Agent Hub Db Info Faild!{str(e)}")

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize the filename to prevent directory traversal attacks.

        Args:
            filename: The original filename

        Returns:
            str: Sanitized filename
        """
        # Only keep the basic filename, remove any path information
        filename = os.path.basename(filename)

        # Remove any unsafe characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

        # Ensure the filename is not empty and valid
        if not filename or filename.startswith("."):
            raise ValueError("Invalid filename")

        return filename

    def _validate_extracted_files(self, directory: str) -> bool:
        """Validate all Python files in the extracted plugin directory.

        Args:
            directory: The directory containing extracted plugin files

        Returns:
            bool: True if all files are safe, raises an exception otherwise
        """
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    logger.info(f"Validating plugin file: {file_path}")
                    self._validate_plugin_code(file_path)
        return True

    async def upload_my_plugin(self, doc_file: UploadFile, user: Any = Default_User):
        # Verify and clean file names
        try:
            safe_filename = self._sanitize_filename(doc_file.filename)
        except ValueError as e:
            raise ValueError(f"Invalid plugin file: {str(e)}")

        # Structure a safe file path
        file_path = os.path.join(self.plugin_dir, safe_filename)

        # Verify the final path is within the allowed directory
        if (
            not Path(file_path)
            .resolve()
            .is_relative_to(Path(self.plugin_dir).resolve())
        ):
            raise ValueError("Invalid file path")

        if os.path.exists(file_path):
            os.remove(file_path)

        # Use a temporary file for secure file writing
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.plugin_dir)
        try:
            with os.fdopen(tmp_fd, "wb") as tmp:
                tmp.write(await doc_file.read())
            shutil.move(tmp_path, file_path)
        except Exception as e:
            # Ensure the temporary file is cleaned up
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e

        # If it's a zip file, extract and validate each Python file before loading
        if safe_filename.lower().endswith(".zip"):
            import zipfile

            extract_dir = os.path.join(
                self.plugin_dir, f"temp_extract_{os.path.splitext(safe_filename)[0]}"
            )
            try:
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    # Create a secure temp directory for extraction
                    os.makedirs(extract_dir, exist_ok=True)

                    # Check for zip file issues (bombs, traversal)
                    for zip_info in zip_ref.infolist():
                        if (
                            zip_info.file_size > 10 * 1024 * 1024
                        ):  # 10MB limit for any single file
                            raise ValueError("Zip contains files that are too large")

                        # Check for path traversal
                        if ".." in zip_info.filename or zip_info.filename.startswith(
                            "/"
                        ):
                            raise ValueError("Zip contains potentially malicious paths")

                    # Extract the zip
                    zip_ref.extractall(extract_dir)

                    # Validate all Python files before allowing them to be loaded
                    self._validate_extracted_files(extract_dir)

            except zipfile.BadZipFile:
                raise ValueError("Invalid or corrupted zip file")
            finally:
                # Clean up the extraction directory
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)

        # Validate single file plugins
        elif safe_filename.lower().endswith(".py"):
            self._validate_plugin_code(file_path)

        # Scan and validate the plugin
        try:
            my_plugins = scan_plugins(self.plugin_dir, safe_filename)
        except Exception as e:
            # If the plugin validation fails, clean up the uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise ValueError(f"Invalid plugin file: {str(e)}")

        if user is None or len(user) <= 0:
            user = Default_User

        # Update the database
        for my_plugin in my_plugins:
            my_plugin_entiy = self.my_plugin_dao.get_by_user_and_plugin(
                user, my_plugin._name
            )
            if my_plugin_entiy is None:
                my_plugin_entiy = MyPluginEntity()
            my_plugin_entiy.name = my_plugin._name
            my_plugin_entiy.version = my_plugin._version
            my_plugin_entiy.type = "Personal"
            my_plugin_entiy.user_code = user
            my_plugin_entiy.user_name = user
            my_plugin_entiy.tenant = ""
            my_plugin_entiy.file_name = safe_filename
            self.my_plugin_dao.raw_update(my_plugin_entiy)

    def reload_my_plugins(self):
        logger.info("load_plugins start!")
        return scan_plugins(self.plugin_dir)

    def get_my_plugin(self, user: str):
        logger.info(f"get_my_plugin:{user}")
        if not user:
            user = Default_User
        return self.my_plugin_dao.get_by_user(user)


plugin_hub = PluginHub(PLUGINS_DIR)
