from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Column, DateTime, String

from dbgpt.storage.metadata import BaseDao, Model


class ConvLinksEntity(Model):
    __tablename__ = "conv_links"
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Primary Key")
    gmt_create = Column(DateTime, default=datetime.now, comment="Creation time")
    gmt_modify = Column(
        DateTime,
        default=datetime.now,
        comment="Modification time",
    )
    conv_id = Column(String(255), nullable=True, comment="Conversation ID")
    message_id = Column(String(255), nullable=True, comment="Message ID")
    chat_room_id = Column(String(255), nullable=True, comment="Chat room ID")
    app_code = Column(String(255), nullable=True, comment="App code")
    emp_id = Column(String(255), nullable=True, comment="Employee ID")

    def __repr__(self):
        return (
            f"ConvLinksEntity(id={self.id}, conv_id='{self.conv_id}', message_id='{self.message_id}', "
            f"chat_room_id='{self.chat_room_id}', app_code='{self.app_code}', emp_id='{self.emp_id}', "
            f"gmt_create='{self.gmt_create}', gmt_modify='{self.gmt_modify}')"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "conv_id": self.conv_id,
            "message_id": self.message_id,
            "chat_room_id": self.chat_room_id,
            "app_code": self.app_code,
            "emp_id": self.emp_id,
            "gmt_create": self.gmt_create,
            "gmt_modify": self.gmt_modify,
        }


class ConvLinksRequest(BaseModel):
    conv_id: Optional[str] = Field(None, description="The conversation id")
    message_id: Optional[str] = Field(None, description="The message id")
    chat_room_id: Optional[str] = Field(None, description="The chat room id")
    app_code: Optional[str] = Field(None, description="The app code")
    emp_id: Optional[str] = Field(None, description="The employee id")


class ConvLinksResponse(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    conv_id: Optional[str] = Field(None, description="The conversation id")
    message_id: Optional[str] = Field(None, description="The message id")
    chat_room_id: Optional[str] = Field(None, description="The chat room id")
    app_code: Optional[str] = Field(None, description="The app code")
    emp_id: Optional[str] = Field(None, description="The employee id")
    gmt_create: Optional[str] = Field(None, description="The create time")
    gmt_modify: Optional[str] = Field(None, description="The modify time")


class ConvLinksDao(BaseDao):
    def from_request(self, request: Union[ConvLinksRequest, Dict[str, Any]]):
        request_dict = (
            request.dict() if isinstance(request, ConvLinksRequest) else request
        )
        entity = ConvLinksEntity(**request_dict)
        return entity

    def to_request(self, entity):
        return {
            "id": entity.id,
            "gmt_create": entity.gmt_create,
            "gmt_modify": entity.gmt_modify,
            "conv_id": entity.conv_id,
            "message_id": entity.message_id,
            "chat_room_id": entity.chat_room_id,
            "app_code": entity.app_code,
            "emp_id": entity.emp_id,
        }

    def from_response(self, response: Union[ConvLinksResponse, Dict[str, Any]]):
        response_dict = (
            response.dict() if isinstance(response, ConvLinksResponse) else response
        )
        entity = ConvLinksEntity(**response_dict)
        return entity

    def to_response(self, entity):
        return {
            "id": entity.id,
            "gmt_create": entity.gmt_create,
            "gmt_modify": entity.gmt_modify,
            "conv_id": entity.conv_id,
            "message_id": entity.message_id,
            "chat_room_id": entity.chat_room_id,
            "app_code": entity.app_code,
            "emp_id": entity.emp_id,
        }
