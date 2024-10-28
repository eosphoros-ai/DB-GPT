"""This is an auto-generated model file
You can define your own models and DAOs here
"""
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from dbgpt.storage.metadata import BaseDao, Model, db

from ..api.schemas import ConvFeedbackReasonType, ServeRequest, ServerResponse
from ..config import ServeConfig


class ServeEntity(Model):
    __tablename__ = "chat_feed_back"
    id = Column(Integer, primary_key=True)
    conv_uid = Column(String(128))
    conv_index = Column(Integer)
    score = Column(Integer)
    ques_type = Column(String(32))
    question = Column(Text)
    knowledge_space = Column(String(128))
    messages = Column(Text)
    remark = Column(Text, nullable=True, comment="feedback remark")
    message_id = Column(String(255), nullable=True, comment="Message ID")
    feedback_type = Column(
        String(31), nullable=True, comment="Feedback type like or unlike"
    )
    reason_types = Column(
        String(255), nullable=True, comment="Feedback reason categories"
    )
    user_code = Column(String(255), nullable=True, comment="User ID")

    user_name = Column(String(128))
    gmt_created = Column(DateTime, default=datetime.utcnow, comment="Creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Modification time",
    )

    __table_args__ = (
        Index("idx_conv_uid", "conv_uid"),
        Index("idx_gmt_create", "gmt_created"),
    )

    def __repr__(self):
        return (
            f"ChatFeekBackEntity(id={self.id}, conv_index='{self.conv_index}', conv_index='{self.conv_index}', "
            f"score='{self.score}', ques_type='{self.ques_type}', question='{self.question}', knowledge_space='{self.knowledge_space}', "
            f"messages='{self.messages}', user_name='{self.user_name}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"
        )


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for Feedback"""

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
        new_dict = {
            "conv_uid": request.conv_uid,
            "message_id": request.message_id,
            "reason_types": ",".join(request.reason_types),
            "remark": request.remark,
            "score": request.score,
            "ques_type": request.ques_type,
            "question": request.question,
            "knowledge_space": request.knowledge_space,
            "feedback_type": request.feedback_type,
            "user_code": request.user_code,
            "user_name": request.user_name,
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
        reason_types = []
        if entity.reason_types:
            reason_types = entity.reason_types.split(",")
        reason = []
        if len(reason_types) > 0:
            reason = [
                ConvFeedbackReasonType.to_dict(ConvFeedbackReasonType.of_type(t))
                for t in reason_types
            ]
        gmt_created_str = (
            entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_created
            else None
        )
        gmt_modified_str = (
            entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_modified
            else None
        )
        return ServeRequest(
            **{
                "id": entity.id,
                "user_code": entity.user_code,
                "conv_uid": entity.conv_uid,
                "message_id": entity.message_id,
                "question": entity.question,
                "knowledge_space": entity.knowledge_space,
                "feedback_type": entity.feedback_type,
                "remark": entity.remark,
                "reason_types": reason_types,
                "reason": reason,
                "gmt_created": gmt_created_str,
                "gmt_modified": gmt_modified_str,
            }
        )

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """

        return self.to_request(entity)
