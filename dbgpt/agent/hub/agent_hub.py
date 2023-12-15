import json
import logging
import os
import glob
import shutil
from fastapi import UploadFile
from typing import Any
import tempfile

from ..db.plugin_hub_db import PluginHubEntity, PluginHubDao
from ..db.my_plugin_db import MyPluginDao, MyPluginEntity
from ..common.schema import PluginStorageType
from ..plugins_util import scan_plugins, update_from_git

logger = logging.getLogger(__name__)
Default_User = "default"
DEFAULT_PLUGIN_REPO = "https://github.com/eosphoros-ai/DB-GPT-Plugins.git"
TEMP_PLUGIN_PATH = ""


class AgentHub:
    def __init__(self, plugin_dir) -> None:
        self.hub_dao = PluginHubDao()
        self.my_plugin_dao = MyPluginDao()
        os.makedirs(plugin_dir, exist_ok=True)
        self.plugin_dir = plugin_dir
        self.temp_hub_file_path = os.path.join(plugin_dir, "temp")

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
                self.hub_dao.update(plugin_hub_info)
        except Exception as e:
            raise ValueError(f"Update Agent Hub Db Info Faild!{str(e)}")

    async def upload_my_plugin(self, doc_file: UploadFile, user: Any = Default_User):
        # We can not move temp file in windows system when we open file in context of `with`
        file_path = os.path.join(self.plugin_dir, doc_file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.join(self.plugin_dir))
        with os.fdopen(tmp_fd, "wb") as tmp:
            tmp.write(await doc_file.read())
        shutil.move(
            tmp_path,
            os.path.join(self.plugin_dir, doc_file.filename),
        )

        my_plugins = scan_plugins(self.plugin_dir, doc_file.filename)

        if user is None or len(user) <= 0:
            user = Default_User

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
            my_plugin_entiy.file_name = doc_file.filename
            self.my_plugin_dao.update(my_plugin_entiy)

    def reload_my_plugins(self):
        logger.info(f"load_plugins start!")
        return scan_plugins(self.plugin_dir)

    def get_my_plugin(self, user: str):
        logger.info(f"get_my_plugin:{user}")
        if not user:
            user = Default_User
        return self.my_plugin_dao.get_by_user(user)
