import logging

from ..db.plugin_hub_db import PluginHubEntity, PluginHubDao
from ..db.my_plugin_db import MyPluginDao, MyPluginEntity
from .schema import PluginStorageType

logger = logging.getLogger("agent_hub")


class AgentHub:
    def __init__(self) -> None:
        self.hub_dao = PluginHubDao()
        self.my_lugin_dao = MyPluginDao()

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
                    if not user_name:
                        # TODO use user
                        my_plugin_entity.user_code = ""
                        my_plugin_entity.user_name = user_name
                        my_plugin_entity.tenant = ""

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

    def __download_from_git(self, plugin_name, url):
        pass

    def load_plugin(self, plugin_name):

        pass

    def get_my_plugin(self, user: str):
        pass

    def uninstall_plugin(self):
        pass
