from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Column, DateTime, String

from dbgpt.storage.metadata import BaseDao, Model


class SettingsEntity(Model):
    """Settings entity"""

    __tablename__ = "settings"
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Primary Key")
    gmt_create = Column(DateTime, default=datetime.now, comment="Creation time")
    gmt_modify = Column(
        DateTime,
        default=datetime.now,
        comment="Modification time",
    )
    setting_key = Column(String(32), nullable=False, comment="Configuration key")
    setting_value = Column(String(255), nullable=True, comment="Configuration value")
    description = Column(
        String(255), nullable=True, comment="Configuration description"
    )

    def __repr__(self):
        return (
            f"SettingsEntity(id={self.id}, setting_key='{self.setting_key}', setting_value='{self.setting_value}', "
            f"description='{self.description}', gmt_create='{self.gmt_create}', gmt_modify='{self.gmt_modify}')"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "description": self.description,
            "gmt_create": self.gmt_create,
            "gmt_modify": self.gmt_modify,
        }


class SettingsRequest(BaseModel):
    """Settings request."""

    setting_key: str = Field(..., description="The configuration key")
    setting_value: Optional[str] = Field(None, description="The configuration value")
    description: Optional[str] = Field(
        None, description="The configuration description"
    )


class SettingsResponse(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    setting_key: str = Field(..., description="The configuration key")
    setting_value: Optional[str] = Field(None, description="The configuration value")
    description: Optional[str] = Field(
        None, description="The configuration description"
    )


class SettingsDao(BaseDao):
    """Settings dao."""

    def from_request(self, request: SettingsRequest) -> Dict[str, Any]:
        request_dict = (
            request.dict() if isinstance(request, SettingsRequest) else request
        )
        entity = SettingsEntity(**request_dict)
        return entity

    def to_response(self, entity: SettingsEntity) -> SettingsResponse:
        return SettingsResponse(
            id=entity.id,
            setting_key=entity.setting_key,
            setting_value=entity.setting_value,
            description=entity.description,
        )

    def to_request(self, entity: SettingsEntity) -> SettingsRequest:
        return SettingsRequest(
            setting_key=entity.setting_key,
            setting_value=entity.setting_value,
            description=entity.description,
        )

    def from_response(self, response: SettingsResponse) -> Dict[str, Any]:
        response_dict = (
            response.dict() if isinstance(response, SettingsResponse) else response
        )
        entity = SettingsEntity(**response_dict)
        return entity
