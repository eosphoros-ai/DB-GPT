from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    and_,
    desc,
    func,
    or_,
)

from dbgpt.storage.metadata import BaseDao, Model


class GptsMessagesEntity(Model):
    __tablename__ = "gpts_messages"
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    conv_id = Column(
        String(255), nullable=False, comment="The unique id of the conversation record"
    )
    sender = Column(
        String(255),
        nullable=False,
        comment="Who speaking in the current conversation turn",
    )
    receiver = Column(
        String(255),
        nullable=False,
        comment="Who receive message in the current conversation turn",
    )
    model_name = Column(String(255), nullable=True, comment="message generate model")
    rounds = Column(Integer, nullable=False, comment="dialogue turns")
    content = Column(Text, nullable=True, comment="Content of the speech")
    current_gogal = Column(
        Text, nullable=True, comment="The target corresponding to the current message"
    )
    context = Column(Text, nullable=True, comment="Current conversation context")
    review_info = Column(
        Text, nullable=True, comment="Current conversation review info"
    )
    action_report = Column(
        Text, nullable=True, comment="Current conversation action report"
    )

    role = Column(
        String(255), nullable=True, comment="The role of the current message content"
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
    def append(self, entity: dict):
        session = self.get_raw_session()
        message = GptsMessagesEntity(
            conv_id=entity.get("conv_id"),
            sender=entity.get("sender"),
            receiver=entity.get("receiver"),
            content=entity.get("content"),
            role=entity.get("role", None),
            model_name=entity.get("model_name", None),
            context=entity.get("context", None),
            rounds=entity.get("rounds", None),
            current_gogal=entity.get("current_gogal", None),
            review_info=entity.get("review_info", None),
            action_report=entity.get("action_report", None),
        )
        session.add(message)
        session.commit()
        id = message.id
        session.close()
        return id

    def get_by_agent(
        self, conv_id: str, agent: str
    ) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if agent:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.conv_id == conv_id
            ).filter(
                or_(
                    GptsMessagesEntity.sender == agent,
                    GptsMessagesEntity.receiver == agent,
                )
            )
        result = gpts_messages.order_by(GptsMessagesEntity.rounds).all()
        session.close()
        return result

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_raw_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if conv_id:
            gpts_messages = gpts_messages.filter(GptsMessagesEntity.conv_id == conv_id)
        result = gpts_messages.order_by(GptsMessagesEntity.rounds).all()
        session.close()
        return result

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_gogal: Optional[str] = None,
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
        if current_gogal:
            gpts_messages = gpts_messages.filter(
                GptsMessagesEntity.current_gogal == current_gogal
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
