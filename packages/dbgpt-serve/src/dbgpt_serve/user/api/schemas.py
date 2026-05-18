from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

from ..config import SERVE_APP_NAME_HUMP


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    user_role: str
    user_group_id: Optional[int] = None
    user_group_name: Optional[str] = None
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class UserCreateRequest(BaseModel):
    username: str = Field(..., description="Unique username")
    password: str = Field(..., description="Plain text password")
    user_group_id: int = Field(..., description="Group ID")
    user_role: str = Field(default="normal", description="super_admin or normal")
    phone: Optional[str] = None
    email: Optional[str] = None
    real_name: Optional[str] = None


class UserUpdateRequest(BaseModel):
    user_group_id: Optional[int] = None
    user_role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    real_name: Optional[str] = None


class UserRequest(BaseModel):
    id: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    user_group_id: Optional[int] = None
    user_role: Optional[str] = "normal"
    phone: Optional[str] = None
    email: Optional[str] = None
    real_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(title=f"ServeResponse for {SERVE_APP_NAME_HUMP}")

    id: int
    username: str
    user_role: str
    user_group_id: Optional[int] = None
    user_group_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    real_name: Optional[str] = None
    avatar_url: Optional[str] = None
    gmt_created: Optional[str] = None
    gmt_modified: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    group_name: str
    description: Optional[str] = None


class GroupMenuRequest(BaseModel):
    group_id: int = Field(..., description="Group ID")
    menu_keys: List[str] = Field(default_factory=list, description="List of menu keys")


class MenuResponse(BaseModel):
    menu_key: str
    menu_name: str
