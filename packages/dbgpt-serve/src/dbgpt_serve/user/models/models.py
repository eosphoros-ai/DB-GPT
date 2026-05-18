from datetime import datetime
from typing import Any, Dict, Optional, Union

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from dbgpt._private.pydantic import model_to_dict
from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.storage.metadata._base_dao import QUERY_SPEC

from ..api.schemas import UserRequest, UserResponse
from ..config import (
    SERVER_APP_TABLE_USERS,
    SERVER_APP_TABLE_USER_GROUPS,
    SERVER_APP_TABLE_USER_GROUP_MENUS,
    ServeConfig,
)


class UserGroupEntity(Model):
    __tablename__ = SERVER_APP_TABLE_USER_GROUPS

    id = Column(Integer, primary_key=True, comment="Auto increment id")
    group_name = Column(String(100), nullable=False, comment="Group name")
    description = Column(String(500), nullable=True, comment="Group description")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")


class UserEntity(Model):
    __tablename__ = SERVER_APP_TABLE_USERS

    id = Column(Integer, primary_key=True, comment="Auto increment user id")
    username = Column(String(100), nullable=False, comment="Username, unique")
    password = Column(String(256), nullable=False, comment="Hashed password")
    user_group_id = Column(Integer, nullable=True, comment="FK to user_groups.id")
    user_role = Column(
        String(32), nullable=False, default="normal", comment="super_admin or normal"
    )
    phone = Column(String(20), nullable=True, comment="Phone number")
    email = Column(String(100), nullable=True, comment="Email address")
    real_name = Column(String(100), nullable=True, comment="Display name")
    avatar_url = Column(String(512), nullable=True, comment="Avatar url")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")


class UserGroupMenuEntity(Model):
    __tablename__ = SERVER_APP_TABLE_USER_GROUP_MENUS
    __table_args__ = (
        UniqueConstraint("group_id", "menu_key", name="uk_group_menu"),
    )

    id = Column(Integer, primary_key=True, comment="Auto increment id")
    group_id = Column(Integer, nullable=False, comment="FK to user_groups.id")
    menu_key = Column(String(100), nullable=False, comment="Menu identifier key")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")


class UserDao(BaseDao[UserEntity, UserRequest, UserResponse]):
    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(
        self, request: Union[UserRequest, Dict[str, Any]]
    ) -> UserEntity:
        request_dict = (
            model_to_dict(request) if isinstance(request, UserRequest) else request
        )
        entity = UserEntity(
            id=request_dict.get("id"),
            username=request_dict.get("username"),
            password=request_dict.get("password", ""),
            user_group_id=request_dict.get("user_group_id"),
            user_role=request_dict.get("user_role", "normal"),
            phone=request_dict.get("phone"),
            email=request_dict.get("email"),
            real_name=request_dict.get("real_name"),
            avatar_url=request_dict.get("avatar_url"),
        )
        return entity

    def to_response(self, entity: UserEntity) -> UserResponse:
        gmt_created_str = (
            entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_created
            else None
        )
        gmt_modified_str = (
            entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_modified
            else None
        )
        return UserResponse(
            id=entity.id,
            username=entity.username,
            user_role=entity.user_role,
            user_group_id=entity.user_group_id,
            user_group_name=None,
            phone=entity.phone,
            email=entity.email,
            real_name=entity.real_name,
            avatar_url=entity.avatar_url,
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )

    def update(
        self, query_request: QUERY_SPEC, update_request: UserRequest
    ) -> UserResponse:
        with self.session(commit=False) as session:
            query = self._create_query_object(session, query_request)
            entry: UserEntity = query.first()
            if entry is None:
                raise Exception("Invalid request")
            if update_request.user_group_id is not None:
                entry.user_group_id = update_request.user_group_id
            if update_request.user_role:
                entry.user_role = update_request.user_role
            if update_request.phone is not None:
                entry.phone = update_request.phone
            if update_request.email is not None:
                entry.email = update_request.email
            if update_request.real_name is not None:
                entry.real_name = update_request.real_name
            session.merge(entry)
            session.commit()
            return self.get_one(query_request)
