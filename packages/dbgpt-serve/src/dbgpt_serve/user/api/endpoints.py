from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import UserService
from .schemas import (
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

router = APIRouter()

global_system_app: Optional[SystemApp] = None

security = HTTPBearer(auto_error=False)


def get_service() -> UserService:
    return UserService.get_instance(global_system_app)


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    service: UserService = Depends(get_service),
) -> UserRequest:
    if not auth or not auth.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = service.validate_token(auth.credentials)
    user = service.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/auth/login", response_model=Result[LoginResponse])
async def login(
    request: LoginRequest,
    service: UserService = Depends(get_service),
):
    try:
        result = service.authenticate(request)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/list", response_model=Result[List[UserResponse]])
async def list_users(
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    result = service.get_users(current_user)
    return Result.succ(result)


@router.post("/user/add", response_model=Result[UserResponse])
async def add_user(
    request: UserCreateRequest,
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    try:
        result = service.create_user(request, current_user)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/user/{user_id}", response_model=Result[bool])
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    try:
        result = service.delete_user(user_id, current_user)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/user/{user_id}", response_model=Result[UserResponse])
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    try:
        result = service.update_user(user_id, request, current_user)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/groups", response_model=Result[List[GroupResponse]])
async def list_groups(
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    result = service.get_groups()
    return Result.succ(result)


@router.post("/user/groups", response_model=Result[GroupResponse])
async def create_group(
    group_name: str,
    description: str = "",
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    try:
        result = service.create_group(group_name, description, current_user)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/menus", response_model=Result[List[MenuResponse]])
async def get_menus(
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    result = service.get_menus_for_user(current_user.id)
    return Result.succ(result)


@router.post("/user/group-menus", response_model=Result[bool])
async def set_group_menus(
    request: GroupMenuRequest,
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    try:
        result = service.set_group_menus(request, current_user)
        return Result.succ(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/group-menus/{group_id}", response_model=Result[List[str]])
async def get_group_menus(
    group_id: int,
    service: UserService = Depends(get_service),
    current_user: UserRequest = Depends(get_current_user),
):
    result = service.get_group_menus(group_id)
    return Result.succ(result)


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    global global_system_app
    global_system_app = system_app
    system_app.register(UserService, config=config)
