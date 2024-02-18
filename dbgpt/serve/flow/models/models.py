"""This is an auto-generated model file
You can define your own models and DAOs here
"""
import json
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from dbgpt.core.awel.flow.flow_factory import State
from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.storage.metadata._base_dao import QUERY_SPEC

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    __table_args__ = (UniqueConstraint("uid", name="uk_uid"),)

    id = Column(Integer, primary_key=True, comment="Auto increment id")
    uid = Column(String(128), index=True, nullable=False, comment="Unique id")
    dag_id = Column(String(128), index=True, nullable=True, comment="DAG id")
    label = Column(String(128), nullable=True, comment="Flow label")
    name = Column(String(128), index=True, nullable=True, comment="Flow name")
    flow_category = Column(String(64), nullable=True, comment="Flow category")
    flow_data = Column(Text, nullable=True, comment="Flow data, JSON format")
    description = Column(String(512), nullable=True, comment="Flow description")
    state = Column(String(32), nullable=True, comment="Flow state")
    source = Column(String(64), nullable=True, comment="Flow source")
    source_url = Column(String(512), nullable=True, comment="Flow source url")
    version = Column(String(32), nullable=True, comment="Flow version")
    editable = Column(
        Integer, nullable=True, comment="Editable, 0: editable, 1: not editable"
    )
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")

    def __repr__(self):
        return (
            f"ServeEntity(id={self.id}, uid={self.uid}, dag_id={self.dag_id}, name={self.name}, "
            f"flow_data={self.flow_data}, user_name={self.user_name}, "
            f"sys_code={self.sys_code}, gmt_created={self.gmt_created}, "
            f"gmt_modified={self.gmt_modified})"
        )

    @classmethod
    def parse_editable(cls, editable: Any) -> int:
        """Parse editable"""
        if editable is None:
            return 0
        if isinstance(editable, bool):
            return 0 if editable else 1
        elif isinstance(editable, int):
            return 0 if editable == 0 else 1
        else:
            raise ValueError(f"Invalid editable: {editable}")

    @classmethod
    def to_bool_editable(cls, editable: int) -> bool:
        """Convert editable to bool"""
        return editable is None or editable == 0


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
        state = request_dict.get("state", State.INITIALIZING.value)
        new_dict = {
            "uid": request_dict.get("uid"),
            "dag_id": request_dict.get("dag_id"),
            "label": request_dict.get("label"),
            "name": request_dict.get("name"),
            "flow_category": request_dict.get("flow_category"),
            "flow_data": flow_data,
            "state": state,
            "source": request_dict.get("source"),
            "source_url": request_dict.get("source_url"),
            "version": request_dict.get("version"),
            "editable": ServeEntity.parse_editable(request_dict.get("editable")),
            "description": request_dict.get("description"),
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
            dag_id=entity.dag_id,
            label=entity.label,
            name=entity.name,
            flow_category=entity.flow_category,
            flow_data=flow_data,
            state=State.value_of(entity.state),
            source=entity.source,
            source_url=entity.source_url,
            version=entity.version,
            editable=ServeEntity.to_bool_editable(entity.editable),
            description=entity.description,
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
            dag_id=entity.dag_id,
            label=entity.label,
            name=entity.name,
            flow_category=entity.flow_category,
            flow_data=flow_data,
            description=entity.description,
            state=State.value_of(entity.state),
            source=entity.source,
            source_url=entity.source_url,
            version=entity.version,
            editable=ServeEntity.to_bool_editable(entity.editable),
            user_name=entity.user_name,
            sys_code=entity.sys_code,
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )

    def update(
        self, query_request: QUERY_SPEC, update_request: ServeRequest
    ) -> ServerResponse:
        with self.session(commit=False) as session:
            query = self._create_query_object(session, query_request)
            entry: ServeEntity = query.first()
            if entry is None:
                raise Exception("Invalid request")
            if update_request.label:
                entry.label = update_request.label
            if update_request.name:
                entry.name = update_request.name
            if update_request.flow_category:
                entry.flow_category = update_request.flow_category
            if update_request.flow_data:
                entry.flow_data = json.dumps(
                    update_request.flow_data.dict(), ensure_ascii=False
                )
            if update_request.description:
                entry.description = update_request.description
            if update_request.state:
                entry.state = update_request.state.value
            if update_request.source:
                entry.source = update_request.source
            if update_request.source_url:
                entry.source_url = update_request.source_url
            if update_request.version:
                entry.version = update_request.version
            if update_request.editable:
                entry.editable = ServeEntity.parse_editable(update_request.editable)
            if update_request.user_name:
                entry.user_name = update_request.user_name
            if update_request.sys_code:
                entry.sys_code = update_request.sys_code
            session.merge(entry)
            session.commit()
            return self.get_one(query_request)
