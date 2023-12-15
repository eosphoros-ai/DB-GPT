from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy import UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model


class MyPluginEntity(Model):
    __tablename__ = "my_plugin"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    tenant = Column(String(255), nullable=True, comment="user's tenant")
    user_code = Column(String(255), nullable=False, comment="user code")
    user_name = Column(String(255), nullable=True, comment="user name")
    name = Column(String(255), unique=True, nullable=False, comment="plugin name")
    file_name = Column(String(255), nullable=False, comment="plugin package file name")
    type = Column(String(255), comment="plugin type")
    version = Column(String(255), comment="plugin version")
    use_count = Column(
        Integer, nullable=True, default=0, comment="plugin total use count"
    )
    succ_count = Column(
        Integer, nullable=True, default=0, comment="plugin total success count"
    )
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(
        DateTime, default=datetime.utcnow, comment="plugin install time"
    )
    UniqueConstraint("user_code", "name", name="uk_name")


class MyPluginDao(BaseDao[MyPluginEntity]):
    def add(self, engity: MyPluginEntity):
        session = self.get_raw_session()
        my_plugin = MyPluginEntity(
            tenant=engity.tenant,
            user_code=engity.user_code,
            user_name=engity.user_name,
            name=engity.name,
            type=engity.type,
            version=engity.version,
            use_count=engity.use_count or 0,
            succ_count=engity.succ_count or 0,
            sys_code=engity.sys_code,
            gmt_created=datetime.now(),
        )
        session.add(my_plugin)
        session.commit()
        id = my_plugin.id
        session.close()
        return id

    def update(self, entity: MyPluginEntity):
        session = self.get_raw_session()
        updated = session.merge(entity)
        session.commit()
        return updated.id

    def get_by_user(self, user: str) -> list[MyPluginEntity]:
        session = self.get_raw_session()
        my_plugins = session.query(MyPluginEntity)
        if user:
            my_plugins = my_plugins.filter(MyPluginEntity.user_code == user)
        result = my_plugins.all()
        session.close()
        return result

    def get_by_user_and_plugin(self, user: str, plugin: str) -> MyPluginEntity:
        session = self.get_raw_session()
        my_plugins = session.query(MyPluginEntity)
        if user:
            my_plugins = my_plugins.filter(MyPluginEntity.user_code == user)
        my_plugins = my_plugins.filter(MyPluginEntity.name == plugin)
        result = my_plugins.first()
        session.close()
        return result

    def list(self, query: MyPluginEntity, page=1, page_size=20) -> list[MyPluginEntity]:
        session = self.get_raw_session()
        my_plugins = session.query(MyPluginEntity)
        all_count = my_plugins.count()
        if query.id is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.id == query.id)
        if query.name is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.name == query.name)
        if query.tenant is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.tenant == query.tenant)
        if query.type is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.type == query.type)
        if query.user_code is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.user_code == query.user_code)
        if query.user_name is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.user_name == query.user_name)
        if query.sys_code is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.sys_code == query.sys_code)

        my_plugins = my_plugins.order_by(MyPluginEntity.id.desc())
        my_plugins = my_plugins.offset((page - 1) * page_size).limit(page_size)
        result = my_plugins.all()
        session.close()
        total_pages = all_count // page_size
        if all_count % page_size != 0:
            total_pages += 1

        return result, total_pages, all_count

    def count(self, query: MyPluginEntity):
        session = self.get_raw_session()
        my_plugins = session.query(func.count(MyPluginEntity.id))
        if query.id is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.id == query.id)
        if query.name is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.name == query.name)
        if query.type is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.type == query.type)
        if query.tenant is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.tenant == query.tenant)
        if query.user_code is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.user_code == query.user_code)
        if query.user_name is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.user_name == query.user_name)
        if query.sys_code is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.sys_code == query.sys_code)
        count = my_plugins.scalar()
        session.close()
        return count

    def delete(self, plugin_id: int):
        session = self.get_raw_session()
        if plugin_id is None:
            raise Exception("plugin_id is None")
        query = MyPluginEntity(id=plugin_id)
        my_plugins = session.query(MyPluginEntity)
        if query.id is not None:
            my_plugins = my_plugins.filter(MyPluginEntity.id == query.id)
        my_plugins.delete()
        session.commit()
        session.close()
