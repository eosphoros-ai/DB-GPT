import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException

from dbgpt.component import SystemApp
from dbgpt_serve.core import BaseService, blocking_func_to_async

from ..api.schemas import (
    GroupMenuRequest,
    GroupResponse,
    LoginRequest,
    LoginResponse,
    MenuResponse,
    UserCreateRequest,
    UserRequest,
    UserResponse,
    UserUpdateRequest,
)
from ..config import ALL_MENU_KEYS, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import UserDao, UserEntity, UserGroupEntity, UserGroupMenuEntity

logger = logging.getLogger(__name__)


class UserService(BaseService[UserEntity, UserRequest, UserResponse]):
    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: ServeConfig,
        dao: Optional[UserDao] = None,
    ):
        self._system_app = None
        self._serve_config: ServeConfig = config
        self._dao: UserDao = dao
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        super().init_app(system_app)
        self._dao = self._dao or UserDao(self._serve_config)
        self._system_app = system_app

    @property
    def dao(self) -> UserDao:
        return self._dao

    @property
    def config(self) -> ServeConfig:
        return self._serve_config

    def _get_jwt_secret(self) -> str:
        secret = self._serve_config.jwt_secret_key
        if not secret:
            secret = os.environ.get("DBGPT_JWT_SECRET", "dbgpt_default_jwt_secret")
        return secret

    def _hash_password(self, password: str) -> str:
        import hashlib

        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, plain_password: str, hashed: str) -> bool:
        return self._hash_password(plain_password) == hashed

    def _generate_token(self, user: UserEntity, group_name: Optional[str] = None) -> str:
        import jwt

        secret = self._get_jwt_secret()
        expire_minutes = self._serve_config.jwt_expire_minutes
        payload = {
            "user_id": user.id,
            "username": user.username,
            "user_role": user.user_role,
            "user_group_id": user.user_group_id,
            "exp": datetime.utcnow() + timedelta(minutes=expire_minutes),
        }
        return jwt.encode(payload, secret, algorithm=self._serve_config.jwt_algorithm)

    def validate_token(self, token: str) -> dict:
        import jwt

        secret = self._get_jwt_secret()
        try:
            payload = jwt.decode(
                token, secret, algorithms=[self._serve_config.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def authenticate(self, request: LoginRequest) -> LoginResponse:
        with self._dao.session() as session:
            user = (
                session.query(UserEntity)
                .filter(UserEntity.username == request.username)
                .first()
            )
            if not user:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            if not self._verify_password(request.password, user.password or ""):
                raise HTTPException(status_code=401, detail="Invalid username or password")

            group_name = None
            if user.user_group_id:
                group = (
                    session.query(UserGroupEntity)
                    .filter(UserGroupEntity.id == user.user_group_id)
                    .first()
                )
                if group:
                    group_name = group.group_name

            token = self._generate_token(user, group_name)
            return LoginResponse(
                token=token,
                user_id=user.id,
                username=user.username,
                user_role=user.user_role,
                user_group_id=user.user_group_id,
                user_group_name=group_name,
                real_name=user.real_name,
                phone=user.phone,
                email=user.email,
            )

    def get_user_by_id(self, user_id: int) -> Optional[UserRequest]:
        with self._dao.session() as session:
            user = session.query(UserEntity).filter(UserEntity.id == user_id).first()
            if not user:
                return None
            group_name = None
            if user.user_group_id:
                group = (
                    session.query(UserGroupEntity)
                    .filter(UserGroupEntity.id == user.user_group_id)
                    .first()
                )
                if group:
                    group_name = group.group_name
            return UserRequest(
                id=user.id,
                username=user.username,
                user_group_id=user.user_group_id,
                user_role=user.user_role,
                phone=user.phone,
                email=user.email,
                real_name=user.real_name,
                avatar_url=user.avatar_url,
            )

    def get_users(self, current_user: UserRequest) -> List[UserResponse]:
        with self._dao.session() as session:
            if current_user.user_role == "super_admin":
                users = session.query(UserEntity).all()
            else:
                users = (
                    session.query(UserEntity)
                    .filter(UserEntity.user_group_id == current_user.user_group_id)
                    .all()
                )

            result = []
            for user in users:
                resp = self._dao.to_response(user)
                if user.user_group_id:
                    group = (
                        session.query(UserGroupEntity)
                        .filter(UserGroupEntity.id == user.user_group_id)
                        .first()
                    )
                    if group:
                        resp.user_group_name = group.group_name
                result.append(resp)
            return result

    def create_user(
        self, request: UserCreateRequest, current_user: UserRequest
    ) -> UserResponse:
        if current_user.user_role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can create users")

        with self._dao.session() as session:
            existing = (
                session.query(UserEntity)
                .filter(UserEntity.username == request.username)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Username '{request.username}' already exists",
                )

            user = UserEntity(
                username=request.username,
                password=self._hash_password(request.password),
                user_group_id=request.user_group_id,
                user_role=request.user_role,
                phone=request.phone,
                email=request.email,
                real_name=request.real_name,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._dao.to_response(user)

    def delete_user(self, user_id: int, current_user: UserRequest) -> bool:
        if current_user.user_role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can delete users")
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")

        with self._dao.session() as session:
            user = session.query(UserEntity).filter(UserEntity.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            session.delete(user)
            session.commit()
        return True

    def update_user(
        self, user_id: int, request: UserUpdateRequest, current_user: UserRequest
    ) -> UserResponse:
        if current_user.user_role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can update users")

        with self._dao.session() as session:
            user = session.query(UserEntity).filter(UserEntity.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if request.user_group_id is not None:
                user.user_group_id = request.user_group_id
            if request.user_role is not None:
                user.user_role = request.user_role
            if request.phone is not None:
                user.phone = request.phone
            if request.email is not None:
                user.email = request.email
            if request.real_name is not None:
                user.real_name = request.real_name

            session.merge(user)
            session.commit()
            session.refresh(user)
            return self._dao.to_response(user)

    def get_groups(self) -> List[GroupResponse]:
        with self._dao.session() as session:
            groups = session.query(UserGroupEntity).all()
            return [
                GroupResponse(
                    id=g.id,
                    group_name=g.group_name,
                    description=g.description,
                )
                for g in groups
            ]

    def create_group(
        self, group_name: str, description: str, current_user: UserRequest
    ) -> GroupResponse:
        if current_user.user_role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can create groups")

        with self._dao.session() as session:
            existing = (
                session.query(UserGroupEntity)
                .filter(UserGroupEntity.group_name == group_name)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Group '{group_name}' already exists",
                )
            group = UserGroupEntity(group_name=group_name, description=description)
            session.add(group)
            session.commit()
            session.refresh(group)
            return GroupResponse(
                id=group.id,
                group_name=group.group_name,
                description=group.description,
            )

    def get_group_menus(self, group_id: int) -> List[str]:
        with self._dao.session() as session:
            menus = (
                session.query(UserGroupMenuEntity)
                .filter(UserGroupMenuEntity.group_id == group_id)
                .all()
            )
            return [m.menu_key for m in menus]

    def set_group_menus(
        self, request: GroupMenuRequest, current_user: UserRequest
    ) -> bool:
        if current_user.user_role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can set menus")

        # Block assigning user_management menu to any group
        if "user_management" in request.menu_keys:
            raise HTTPException(
                status_code=400,
                detail="The 'user_management' menu cannot be assigned to groups",
            )

        with self._dao.session() as session:
            # Delete existing menus for this group
            session.query(UserGroupMenuEntity).filter(
                UserGroupMenuEntity.group_id == request.group_id
            ).delete()
            # Insert new menus
            for menu_key in request.menu_keys:
                if menu_key in ALL_MENU_KEYS:
                    m = UserGroupMenuEntity(
                        group_id=request.group_id, menu_key=menu_key
                    )
                    session.add(m)
            session.commit()
        return True

    def get_menus_for_user(self, user_id: int) -> List[MenuResponse]:
        with self._dao.session() as session:
            user = session.query(UserEntity).filter(UserEntity.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if user.user_role == "super_admin":
                return [
                    MenuResponse(menu_key=k, menu_name=k) for k in ALL_MENU_KEYS
                ]

            if not user.user_group_id:
                return []

            menus = (
                session.query(UserGroupMenuEntity)
                .filter(UserGroupMenuEntity.group_id == user.user_group_id)
                .all()
            )
            return [MenuResponse(menu_key=m.menu_key, menu_name=m.menu_key) for m in menus]
