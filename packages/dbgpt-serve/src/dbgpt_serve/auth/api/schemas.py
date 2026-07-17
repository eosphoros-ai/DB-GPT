"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, field_validator
from dbgpt_serve.auth.models.models import UserEntity


class LoginRequest(BaseModel):
    """Credentials accepted by the login endpoint."""

    login_name: str = Field(min_length=1, max_length=128)
    password: str

    @field_validator("login_name")
    @classmethod
    def normalize_login_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("login_name must not be blank")
        return value


class UserResponse(BaseModel):
    """Non-sensitive user fields returned by authentication APIs."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    login_name: str
    display_name: str
    role: str
    is_active: bool
    gmt_created: datetime
    disabled_at: datetime | None = None

    @classmethod
    def from_entity(cls, entity: UserEntity) -> "UserResponse":
        return cls.model_validate(entity)


class LoginResponse(BaseModel):
    """Successful authentication response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
