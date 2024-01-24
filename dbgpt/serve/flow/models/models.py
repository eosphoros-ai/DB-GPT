"""This is an auto-generated model file
You can define your own models and DAOs here
"""
import json
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.core.awel.flow.flow_factory import FlowData
from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.storage.metadata._base_dao import QUERY_SPEC

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="Auto increment id")
    uid = Column(String(128), index=True, nullable=True, comment="Unique id")
    name = Column(String(128), index=True, nullable=True, comment="Flow name")
    flow_data = Column(Text, nullable=True, comment="Flow data, JSON format")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")

    def __repr__(self):
        return (
            f"ServeEntity(id={self.id}, uid={self.uid}, name={self.name}, "
            f"flow_data={self.flow_data}, user_name={self.user_name}, "
            f"sys_code={self.sys_code}, gmt_created={self.gmt_created}, "
            f"gmt_modified={self.gmt_modified})"
        )


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for Flow"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(self, request: Union[ServeRequest, Dict[str, Any]]) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = request.dict() if isinstance(request, ServeRequest) else request
        flow_data = json.dumps(request_dict.get("flow_data"), ensure_ascii=False)
        new_dict = {
            "uid": request_dict.get("uid"),
            "name": request_dict.get("name"),
            "flow_data": flow_data,
            "user_name": request_dict.get("user_name"),
            "sys_code": request_dict.get("sys_code"),
        }
        entity = ServeEntity(**new_dict)
        return entity

    def to_request(self, entity: ServeEntity) -> ServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        flow_data = json.loads(entity.flow_data)
        return ServeRequest(
            uid=entity.uid,
            name=entity.name,
            flow_data=flow_data,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
        )

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        flow_data = json.loads(entity.flow_data)
        gmt_created_str = entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        return ServerResponse(
            uid=entity.uid,
            name=entity.name,
            flow_data=flow_data,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )

    def update(
        self, query_request: QUERY_SPEC, update_request: ServeRequest
    ) -> ServerResponse:
        with self.session() as session:
            query = self._create_query_object(session, query_request)
            entry: ServeEntity = query.first()
            if entry is None:
                raise Exception("Invalid request")
            if update_request.name:
                entry.name = update_request.name
            if update_request.flow_data:
                entry.flow_data = json.dumps(
                    update_request.flow_data.dict(), ensure_ascii=False
                )
            if update_request.user_name:
                entry.user_name = update_request.user_name
            if update_request.sys_code:
                entry.sys_code = update_request.sys_code
            session.merge(entry)
            return self.get_one(self.to_request(entry))
