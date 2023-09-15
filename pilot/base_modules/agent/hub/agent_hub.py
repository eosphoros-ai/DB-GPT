import logging
import git
import os

from ..db.plugin_hub_db import PluginHubEntity, PluginHubDao
from ..db.my_plugin_db import MyPluginDao, MyPluginEntity
from .schema import PluginStorageType

logger = logging.getLogger("agent_hub")
Default_User = "default"
DEFAULT_PLUGIN_REPO = "https://github.com/eosphoros-ai/DB-GPT-Plugins.git"
TEMP_PLUGIN_PATH = ""

class AgentHub:
    def __init__(self, temp_hub_file_path:str = "") -> None:
        self.hub_dao = PluginHubDao()
        self.my_lugin_dao = MyPluginDao()
        if temp_hub_file_path:
            self.temp_hub_file_path = temp_hub_file_path
        else:
            self.temp_hub_file_path =  os.path.join(os.getcwd(), "plugins", "temp")

    def install_plugin(self, plugin_name: str, user_name: str = None):
        logger.info(f"install_plugin {plugin_name}")

        plugin_entity = self.hub_dao.get_by_name(plugin_name)
        if plugin_entity:
            if plugin_entity.storage_channel == PluginStorageType.Git.value:
                try:
                    self.__download_from_git(plugin_name, plugin_entity.storage_url)
                    self.load_plugin(plugin_name)

                    # add to my plugins and edit hub status
                    plugin_entity.installed = True

                    my_plugin_entity = self.__build_my_plugin(plugin_entity)
                    if user_name:
                        # TODO use user
                        my_plugin_entity.user_code = ""
                        my_plugin_entity.user_name = user_name
                        my_plugin_entity.tenant = ""
                    else:
                        my_plugin_entity.user_code = Default_User

                    with self.hub_dao.Session() as session:
                        try:
                            session.add(my_plugin_entity)
                            session.merge(plugin_entity)
                            session.commit()
                        except:
                            session.rollback()
                except Exception as e:
                    logger.error("install pluguin exception!", e)
                    raise ValueError(f"Install Plugin {plugin_name} Faild! {str(e)}")

            else:
                raise ValueError(f"Unsupport Storage Channel {plugin_entity.storage_channel}!")
        else:
            raise ValueError(f"Can't Find Plugin {plugin_name}!")

    def __build_my_plugin(self, hub_plugin: PluginHubEntity) -> MyPluginEntity:
        my_plugin_entity = MyPluginEntity()
        my_plugin_entity.name = hub_plugin.name
        my_plugin_entity.type = hub_plugin.type
        my_plugin_entity.version = hub_plugin.version
        return my_plugin_entity

    def __fetch_from_git(self):
        logger.info("fetch plugins from git to local path:{}", self.temp_hub_file_path)
        os.makedirs(self.temp_hub_file_path, exist_ok=True)
        repo = git.Repo(self.temp_hub_file_path)
        if  repo.is_repo():
            repo.remotes.origin.pull()
        else:
            git.Repo.clone_from(DEFAULT_PLUGIN_REPO, self.temp_hub_file_path)

        # if repo.head.is_valid():
            # clone succ， fetch plugins info


    def upload_plugin_in_hub(self, name: str, path: str):

        pass

    def __download_from_git(self, plugin_name, url):
        pass

    def load_plugin(self, plugin_name):
        logger.info(f"load_plugin:{plugin_name}")
        pass

    def get_my_plugin(self, user: str):
        logger.info(f"get_my_plugin:{user}")
        if not user:
            user = Default_User
        return self.my_lugin_dao.get_by_user(user)

    def uninstall_plugin(self, plugin_name, user):
        logger.info(f"uninstall_plugin:{plugin_name},{user}")

        pass
