"""This is an auto-generated model file
You can define your own models and DAOs here
"""

import json
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from dbgpt._private.pydantic import model_to_dict
from dbgpt.core.awel.flow.flow_factory import State
from dbgpt.core.interface.variables import StorageVariablesProvider
from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.storage.metadata._base_dao import QUERY_SPEC

from ..api.schemas import (
    ServeRequest,
    ServerResponse,
    VariablesRequest,
    VariablesResponse,
)
from ..config import SERVER_APP_TABLE_NAME, SERVER_APP_VARIABLES_TABLE_NAME, ServeConfig


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
    error_message = Column(String(512), nullable=True, comment="Error message")
    source = Column(String(64), nullable=True, comment="Flow source")
    source_url = Column(String(512), nullable=True, comment="Flow source url")
    version = Column(String(32), nullable=True, comment="Flow version")
    define_type = Column(
        String(32),
        default="json",
        nullable=True,
        comment="Flow define type(json or python)",
    )
    editable = Column(
        Integer, nullable=True, comment="Editable, 0: editable, 1: not editable"
    )
    variables = Column(Text, nullable=True, comment="Flow variables, JSON format")
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


class VariablesEntity(Model):
    __tablename__ = SERVER_APP_VARIABLES_TABLE_NAME

    id = Column(Integer, primary_key=True, comment="Auto increment id")
    key = Column(String(128), index=True, nullable=False, comment="Variable key")
    name = Column(String(128), index=True, nullable=True, comment="Variable name")
    label = Column(String(128), nullable=True, comment="Variable label")
    value = Column(Text, nullable=True, comment="Variable value, JSON format")
    value_type = Column(
        String(32),
        nullable=True,
        comment="Variable value type(string, int, float, bool)",
    )
    category = Column(
        String(32),
        default="common",
        nullable=True,
        comment="Variable category(common or secret)",
    )
    encryption_method = Column(
        String(32),
        nullable=True,
        comment="Variable encryption method(fernet, simple, rsa, aes)",
    )
    salt = Column(String(128), nullable=True, comment="Variable salt")
    scope = Column(
        String(32),
        default="global",
        nullable=True,
        comment="Variable scope(global,flow,app,agent,datasource,flow_priv,agent_priv, "
        "etc)",
    )
    scope_key = Column(
        String(256),
        nullable=True,
        comment="Variable scope key, default is empty, for scope is 'flow_priv', "
        "the scope_key is dag id of flow",
    )
    enabled = Column(
        Integer,
        default=1,
        nullable=True,
        comment="Variable enabled, 0: disabled, 1: enabled",
    )
    description = Column(Text, nullable=True, comment="Variable description")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")


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
        request_dict = (
            model_to_dict(request) if isinstance(request, ServeRequest) else request
        )
        flow_data = json.dumps(request_dict.get("flow_data"), ensure_ascii=False)
        state = request_dict.get("state", State.INITIALIZING.value)
        error_message = request_dict.get("error_message")
        if error_message:
            error_message = error_message[:500]

        variables_raw = request_dict.get("variables")
        variables = (
            json.dumps(variables_raw, ensure_ascii=False) if variables_raw else None
        )
        new_dict = {
            "uid": request_dict.get("uid"),
            "dag_id": request_dict.get("dag_id"),
            "label": request_dict.get("label"),
            "name": request_dict.get("name"),
            "flow_category": request_dict.get("flow_category"),
            "flow_data": flow_data,
            "state": state,
            "error_message": error_message,
            "source": request_dict.get("source"),
            "source_url": request_dict.get("source_url"),
            "version": request_dict.get("version"),
            "define_type": request_dict.get("define_type"),
            "editable": ServeEntity.parse_editable(request_dict.get("editable")),
            "description": request_dict.get("description"),
            "variables": variables,
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
        variables_raw = json.loads(entity.variables) if entity.variables else None
        variables = ServeRequest.parse_variables(variables_raw)
        return ServeRequest(
            uid=entity.uid,
            dag_id=entity.dag_id,
            label=entity.label,
            name=entity.name,
            flow_category=entity.flow_category,
            flow_data=flow_data,
            state=State.value_of(entity.state),
            error_message=entity.error_message,
            source=entity.source,
            source_url=entity.source_url,
            version=entity.version,
            define_type=entity.define_type,
            editable=ServeEntity.to_bool_editable(entity.editable),
            description=entity.description,
            variables=variables,
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
        variables_raw = json.loads(entity.variables) if entity.variables else None
        variables = ServeRequest.parse_variables(variables_raw)
        return ServerResponse(
            uid=entity.uid,
            dag_id=entity.dag_id,
            label=entity.label,
            name=entity.name,
            flow_category=entity.flow_category,
            flow_data=flow_data,
            description=entity.description,
            state=State.value_of(entity.state),
            error_message=entity.error_message,
            source=entity.source,
            source_url=entity.source_url,
            version=entity.version,
            editable=ServeEntity.to_bool_editable(entity.editable),
            define_type=entity.define_type,
            variables=variables,
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
                    model_to_dict(update_request.flow_data), ensure_ascii=False
                )
            if update_request.description:
                entry.description = update_request.description
            if update_request.state:
                entry.state = update_request.state.value
            if update_request.error_message is not None:
                # Keep first 500 characters
                entry.error_message = update_request.error_message[:500]
            if update_request.source:
                entry.source = update_request.source
            if update_request.source_url:
                entry.source_url = update_request.source_url
            if update_request.version:
                entry.version = update_request.version
            entry.editable = ServeEntity.parse_editable(update_request.editable)
            if update_request.define_type:
                entry.define_type = update_request.define_type

            if update_request.variables:
                variables_raw = update_request.get_variables_dict()
                entry.variables = (
                    json.dumps(variables_raw, ensure_ascii=False)
                    if variables_raw
                    else None
                )
            if update_request.user_name:
                entry.user_name = update_request.user_name
            if update_request.sys_code:
                entry.sys_code = update_request.sys_code
            session.merge(entry)
            session.commit()
            return self.get_one(query_request)


class VariablesDao(BaseDao[VariablesEntity, VariablesRequest, VariablesResponse]):
    """The DAO class for Variables"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(
        self, request: Union[VariablesRequest, Dict[str, Any]]
    ) -> VariablesEntity:
        """Convert the request to an entity

        Args:
            request (Union[VariablesRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            model_to_dict(request) if isinstance(request, VariablesRequest) else request
        )
        value = StorageVariablesProvider.serialize_value(request_dict.get("value"))
        enabled = 1 if request_dict.get("enabled", True) else 0
        new_dict = {
            "key": request_dict.get("key"),
            "name": request_dict.get("name"),
            "label": request_dict.get("label"),
            "value": value,
            "value_type": request_dict.get("value_type"),
            "category": request_dict.get("category"),
            "encryption_method": request_dict.get("encryption_method"),
            "salt": request_dict.get("salt"),
            "scope": request_dict.get("scope"),
            "scope_key": request_dict.get("scope_key"),
            "enabled": enabled,
            "user_name": request_dict.get("user_name"),
            "sys_code": request_dict.get("sys_code"),
            "description": request_dict.get("description"),
        }
        entity = VariablesEntity(**new_dict)
        return entity

    def to_request(self, entity: VariablesEntity) -> VariablesRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        value = StorageVariablesProvider.deserialize_value(entity.value)
        if entity.category == "secret":
            value = "******"
        enabled = entity.enabled == 1
        return VariablesRequest(
            key=entity.key,
            name=entity.name,
            label=entity.label,
            value=value,
            value_type=entity.value_type,
            category=entity.category,
            encryption_method=entity.encryption_method,
            salt=entity.salt,
            scope=entity.scope,
            scope_key=entity.scope_key,
            enabled=enabled,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
            description=entity.description,
        )

    def to_response(self, entity: VariablesEntity) -> VariablesResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        value = StorageVariablesProvider.deserialize_value(entity.value)
        if entity.category == "secret":
            value = "******"
        gmt_created_str = entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        enabled = entity.enabled == 1
        return VariablesResponse(
            id=entity.id,
            key=entity.key,
            name=entity.name,
            label=entity.label,
            value=value,
            value_type=entity.value_type,
            category=entity.category,
            encryption_method=entity.encryption_method,
            salt=entity.salt,
            scope=entity.scope,
            scope_key=entity.scope_key,
            enabled=enabled,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
            description=entity.description,
        )
