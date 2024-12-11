"""This is an auto-generated model file
You can define your own models and DAOs here
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from dbgpt.agent.core.schema import Status
from dbgpt.storage.metadata import BaseDao, Model

from ..api.schemas import EvaluateServeRequest, EvaluateServeResponse
from ..config import ServeConfig


class ServeEntity(Model):
    __tablename__ = "evaluate_manage"
    __table_args__ = (
        UniqueConstraint(
            "evaluate_code",
            name="uk_evaluate_code",
        ),
    )
    id = Column(Integer, primary_key=True, comment="Auto increment id")
    evaluate_code = Column(String(256), comment="evaluate Code")
    scene_key = Column(String(100), comment="evaluate scene key")
    scene_value = Column(String(256), comment="evaluate scene value")
    context = Column(Text, comment="evaluate scene run context")
    evaluate_metrics = Column(String(599), comment="evaluate metrics")
    datasets_name = Column(String(256), comment="datasets name")
    datasets = Column(Text, comment="datasets")
    storage_type = Column(String(256), comment="datasets storage type")
    parallel_num = Column(Integer, comment="datasets run parallel num")
    state = Column(String(100), comment="evaluate state")
    result = Column(Text, comment="evaluate result")
    log_info = Column(Text, comment="evaluate log info")
    average_score = Column(Text, comment="evaluate average score")
    user_id = Column(String(100), index=True, nullable=True, comment="User id")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_create = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )

    def __repr__(self):
        return f"ServeEntity(id={self.id}, evaluate_code='{self.evaluate_code}', scene_key='{self.scene_key}', scene_value='{self.scene_value}', datasets='{self.datasets}', user_id='{self.user_id}', user_name='{self.user_name}', sys_code='{self.sys_code}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class ServeDao(BaseDao[ServeEntity, EvaluateServeRequest, EvaluateServeResponse]):
    """The DAO class for Prompt"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(
        self, request: Union[EvaluateServeRequest, Dict[str, Any]]
    ) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[EvaluateServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.dict() if isinstance(request, EvaluateServeRequest) else request
        )
        entity = ServeEntity(
            evaluate_code=request_dict.get("evaluate_code", None),
            scene_key=request_dict.get("scene_key", None),
            scene_value=request_dict.get("scene_value", None),
            context=json.dumps(request_dict.get("context", None))
            if request_dict.get("context", None)
            else None,
            evaluate_metrics=request_dict.get("evaluate_metrics", None),
            datasets_name=request_dict.get("datasets_name", None),
            datasets=request_dict.get("datasets", None),
            storage_type=request_dict.get("storage_type", None),
            parallel_num=request_dict.get("parallel_num", 1),
            state=request_dict.get("state", Status.TODO.value),
            result=request_dict.get("result", None),
            average_score=request_dict.get("average_score", None),
            log_info=request_dict.get("log_info", None),
            user_id=request_dict.get("user_id", None),
            user_name=request_dict.get("user_name", None),
            sys_code=request_dict.get("sys_code", None),
        )
        if not entity.evaluate_code:
            entity.evaluate_code = uuid.uuid1().hex
        return entity

    def to_request(self, entity: ServeEntity) -> EvaluateServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """

        return EvaluateServeRequest(
            evaluate_code=entity.evaluate_code,
            scene_key=entity.scene_key,
            scene_value=entity.scene_value,
            datasets_name=entity.datasets_name,
            datasets=entity.datasets,
            storage_type=entity.storage_type,
            evaluate_metrics=entity.evaluate_metrics,
            context=json.loads(entity.context) if entity.context else None,
            user_name=entity.user_name,
            user_id=entity.user_id,
            sys_code=entity.sys_code,
            state=entity.state,
            result=entity.result,
            average_score=entity.average_score,
            log_info=entity.log_info,
        )

    def to_response(self, entity: ServeEntity) -> EvaluateServeResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        gmt_created_str = entity.gmt_create.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        return EvaluateServeResponse(
            evaluate_code=entity.evaluate_code,
            scene_key=entity.scene_key,
            scene_value=entity.scene_value,
            datasets_name=entity.datasets_name,
            datasets=entity.datasets,
            storage_type=entity.storage_type,
            evaluate_metrics=entity.evaluate_metrics,
            context=json.loads(entity.context) if entity.context else None,
            user_name=entity.user_name,
            user_id=entity.user_id,
            sys_code=entity.sys_code,
            state=entity.state,
            result=entity.result,
            average_score=entity.average_score,
            log_info=entity.log_info,
            gmt_create=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )
