import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    and_,
    desc,
    or_,
)

from dbgpt.agent.util.conv_utils import parse_conv_id
from dbgpt.storage.metadata import BaseDao, Model


class GptsMessagesEntity(Model):
    __tablename__ = "gpts_messages"
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    conv_id = Column(
        String(255), nullable=False, comment="The unique id of the conversation record"
    )
    message_id = Column(
        String(255), nullable=False, comment="The unique id of the messages", default=""
    )
    sender = Column(
        String(255),
        nullable=False,
        comment="Who(role) speaking in the current conversation turn",
    )
    sender_name = Column(
        String(255),
        nullable=False,
        default = "",
        comment="Who(name) speaking in the current conversation turn",
    )
    receiver = Column(
        String(255),
        nullable=False,
        comment="Who(role) receive message in the current conversation turn",
    )
    receiver_name = Column(
        String(255),
        nullable=False,
        default="",
        comment="Who(name) receive message in the current conversation turn",
    )
    model_name = Column(String(255), nullable=True, comment="message generate model")
    rounds = Column(Integer, nullable=False, comment="dialogue turns")
    is_success = Column(Boolean, default=True, nullable=True, comment="is success")
    app_code = Column(
        String(255),
        nullable=False,
        comment="The message in which app",
    )
    app_name = Column(
        String(255),
        nullable=False,
        comment="The message in which app name",
    )
    thinking = Column(
        Text(length=2**31 - 1), nullable=True, comment="Thinking of the speech"
    )
    content = Column(
        Text(length=2**31 - 1), nullable=True, comment="Content of the speech"
    )
    show_message = Column(
        Boolean,
        nullable=True,
        comment="Whether the current message needs to be displayed to the user",
    )
    current_goal = Column(
        Text, nullable=True, comment="The target corresponding to the current message"
    )
    context = Column(Text, nullable=True, comment="Current conversation context")
    review_info = Column(
        Text, nullable=True, comment="Current conversation review info"
    )
    action_report = Column(
        Text(length=2**31 - 1),
        nullable=True,
        comment="Current conversation action report",
    )
    resource_info = Column(
        Text,
        nullable=True,
        comment="Current conversation resource info",
    )
    role = Column(
        String(255), nullable=True, comment="The role of the current message content"
    )
    avatar = Column(
        String(255),
        nullable=True,
        comment="The avatar of the agent who send current message content",
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="create time")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )
    __table_args__ = (Index("idx_q_messages", "conv_id", "rounds", "sender"),)


class GptsMessagesDao(BaseDao):
    def _dict_to_entity(self, entity: dict) -> GptsMessagesEntity:
        return GptsMessagesEntity(
            conv_id=entity.get("conv_id"),
            message_id=entity.get("message_id"),
            sender=entity.get("sender"),
            sender_name=entity.get("sender_name"),
            receiver=entity.get("receiver"),
            receiver_name=entity.get("receiver_name"),
            content=entity.get("content"),
            thinking=entity.get("thinking"),
            is_success=entity.get("is_success", True),
            role=entity.get("role", None),
            avatar=entity.get("avatar", None),
            model_name=entity.get("model_name", None),
            context=entity.get("context", None),
            rounds=entity.get("rounds", None),
            app_code=entity.get("app_code", None),
            app_name=entity.get("app_name", None),
            current_goal=entity.get("current_goal", None),
            review_info=entity.get("review_info", None),
            action_report=entity.get("action_report", None),
            resource_info=entity.get("resource_info", None),
            show_message=entity.get("show_message", None),
        )

    def update_message(self, entity: dict):
        session = self.get_raw_session()
        message_qry = session.query(GptsMessagesEntity)
        message_qry = message_qry.filter(
            GptsMessagesEntity.message_id == entity["message_id"]
        )
        old_message: GptsMessagesEntity = message_qry.order_by(
            GptsMessagesEntity.rounds
        ).one_or_none()

        if old_message:
            old_message.update(
                {
                    GptsMessagesEntity.receiver: entity.get("receiver"),
                    GptsMessagesEntity.receiver_name: entity.get("receiver_name"),
                    GptsMessagesEntity.content: entity.get("content"),
                    GptsMessagesEntity.thinking: entity.get("thinking"),
                    GptsMessagesEntity.is_success: entity.get("is_success"),
                    GptsMessagesEntity.role: entity.get("role"),
                    GptsMessagesEntity.model_name: entity.get("model_name"),
                    GptsMessagesEntity.context: entity.get("context"),
                    GptsMessagesEntity.review_info: entity.get("review_info"),
                    GptsMessagesEntity.action_report: entity.get("action_report"),
                    GptsMessagesEntity.resource_info: entity.get("resource_info"),
                },
                synchronize_session="fetch",
            )
        else:
            session.add(self._dict_to_entity(entity))

        session.commit()
        session.close()
        return id

    def append(self, entity: dict):
        session = self.get_raw_session()
        message = self._dict_to_entity(entity)
        session.add(message)
        session.commit()
        id = message.id
        session.close()
        return id

    def get_by_agent(
        self, conv_id: str, agent: str
    ) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_raw_session()
        real_conv_id, _ = parse_conv_id(conv_id)
        gpts_messages = session.query(GptsMessagesEntity)
        if agent:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.conv_id.like(f"%{real_conv_id}%")
            ).filter(
                or_(
                    GptsMessagesEntity.sender == agent,
                    GptsMessagesEntity.receiver == agent,
                )
            )
        # Extract results first to apply custom sorting
        results = gpts_messages.all()

        # Custom sorting based on conv_id suffix and rounds
        def get_suffix_number(entity):
            suffix_match = re.search(r"_(\d+)$", entity.conv_id)
            if suffix_match:
                return int(suffix_match.group(1))
            return 0  # Default for entries without a numeric suffix

        # Sort first by numeric suffix, then by rounds
        sorted_results = sorted(results, key=lambda x: (get_suffix_number(x), x.rounds))
        session.close()
        return sorted_results

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if conv_id:
            gpts_messages = gpts_messages.filter(GptsMessagesEntity.conv_id == conv_id)
        result = gpts_messages.order_by(GptsMessagesEntity.rounds).all()
        session.close()
        return result

    def delete_by_msg_id(self, message_id: str):
        session = self.get_raw_session()
        old_message_qry = session.query(GptsMessagesEntity)

        old_message_qry = old_message_qry.filter(
            GptsMessagesEntity.message_id == message_id
        )
        old_message = old_message_qry.order_by(GptsMessagesEntity.rounds).one_or_none()
        if old_message:
            session.delete(old_message)
            session.commit()
        session.close()

    def get_by_message_id(self, message_id: str) -> Optional[GptsMessagesEntity]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)

        gpts_messages = gpts_messages.filter(
            GptsMessagesEntity.message_id == message_id
        )
        result = gpts_messages.order_by(GptsMessagesEntity.rounds).one_or_none()
        session.close()
        return result

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_goal: Optional[str] = None,
    ) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if agent1 and agent2:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.conv_id == conv_id
            ).filter(
                or_(
                    and_(
                        GptsMessagesEntity.sender == agent1,
                        GptsMessagesEntity.receiver == agent2,
                    ),
                    and_(
                        GptsMessagesEntity.sender == agent2,
                        GptsMessagesEntity.receiver == agent1,
                    ),
                )
            )
        if current_goal:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.current_goal == current_goal
            )
        result = gpts_messages.order_by(GptsMessagesEntity.rounds).all()
        session.close()
        return result

    def get_last_message(self, conv_id: str) -> Optional[GptsMessagesEntity]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if conv_id:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.conv_id == conv_id
            ).order_by(desc(GptsMessagesEntity.rounds))

        result = gpts_messages.first()
        session.close()
        return result

    def delete_chat_message(self, conv_id: str) -> bool:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        gpts_messages.filter(GptsMessagesEntity.conv_id.like(f"%{conv_id}%")).delete()
        session.commit()
        session.close()
        return True
