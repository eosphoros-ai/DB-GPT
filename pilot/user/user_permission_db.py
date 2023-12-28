from enum import Enum

from sqlalchemy import Column, BigInteger, String, TIMESTAMP
from sqlalchemy.sql import func

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import Base, session, engine


class ResourceType(Enum):
    KNOWLEDGE_SPACE = "KNOWLEDGE_SPACE"


class UserPermissionEntity(Base):
    __tablename__ = "user_permission"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
        "comment": "用户资源权限表"
    }
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    gmt_create = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    gmt_modified = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='修改时间')
    resource_type = Column(String(100), default=None, comment='资源类型：KNOWLEDGE_SPACE_')
    user_id = Column(String(100), default=None, comment='用户id')
    resource_id = Column(String(100), default=None, comment='资源id，如knowledge_space_id')
    permission_code = Column(String(100), default=None, comment='当前权限码')

    def __repr__(self):
        return f"UserPermissionEntity(id='{self.id}', user_id='{self.user_id}', gmt_create='{self.gmt_create}', gmt_modified='{self.gmt_modified}', resource_type='{self.resource_type}', resource_id='{self.resource_id}', permission_code='{self.permission_code}')"


class UserPermissionDao(BaseDao):
    def __init__(self):
        super().__init__(
            database="dbgpt", orm_base=Base, db_engine=engine, session=session
        )

    def create_permission(self, permission: UserPermissionEntity):
        """
          create permission.
        """

        if permission is None:
            raise f"permission info is empty!"
        # new user, by user_channel and user_no:
        if permission.user_id is not None and permission.resource_type is not None and permission.resource_id is not None:
            result = self.get_permissions(UserPermissionEntity(user_id=permission.user_id, resource_type=permission.resource_type, resource_id=permission.resource_id))
            if len(result) == 0:
                session = self.get_session()
                new_permission = UserPermissionEntity(
                    user_id=permission.user_id,
                    resource_type=permission.resource_type,
                    resource_id=permission.resource_id,
                    permission_code=permission.permission_code,
                )
                session.add(new_permission)
                session.commit()
                session.close()
                return self.get_permissions(UserPermissionEntity(user_id=permission.user_id, resource_type=permission.resource_type, resource_id=permission.resource_id))[0]
        return None

    def get_permissions(self, query: UserPermissionEntity):
        """
          get permissions with some conditions.
        """
        session = self.get_session()
        permissions = session.query(UserPermissionEntity)
        if query.id is not None:
            permissions = permissions.filter(UserPermissionEntity.id == query.id)
        if query.user_id is not None:
            permissions = permissions.filter(UserPermissionEntity.user_id == query.user_id)
        if query.permission_code is not None:
            permissions = permissions.filter(UserPermissionEntity.permission_code == query.permission_code)
        if query.resource_id is not None:
            permissions = permissions.filter(UserPermissionEntity.resource_id == query.resource_id)
        if query.resource_type is not None:
            permissions = permissions.filter(UserPermissionEntity.resource_type == query.resource_type)
        results = permissions.all()
        session.close()
        return results

    def update_permission(self, permission: UserPermissionEntity):
        """
          Update permission.
        """
        session = self.get_session()
        session.merge(permission)
        session.commit()
        session.close()
        return True

    def delete_permission(self, permission: UserPermissionEntity):
        """
          Delete permission.
        """

        results = self.get_permissions(UserPermissionEntity(id=permission.id))
        if len(results) == 0:
            raise f"delete permission failed, not exist."

        session = self.get_session()
        if permission:
            session.delete(results[0])
            session.commit()
        session.close()

    def has_permission(self, user_id: str, resource_type: str, resource_id: str):
        """
          query if the user own the specific permission.
        """
        return len(self.get_permissions(UserPermissionEntity(user_id=user_id, resource_type=resource_type, resource_id=resource_id))) > 0
