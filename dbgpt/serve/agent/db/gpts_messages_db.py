from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Index, DateTime, func, Text, or_, and_
from sqlalchemy import UniqueConstraint

from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata.meta_data import (
    Base,
    engine,
    session,
    META_DATA_DATABASE,
)


class GptsMessagesEntity(Base):
    __tablename__ = "gpts_messages"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    conv_id = Column(String(255), nullable=False, comment="The unique id of the conversation record")
    sender = Column(String(255), nullable=False, comment="Who speaking in the current conversation turn")
    receiver = Column(String(255), nullable=True, comment="Who receive message in the current conversation turn")

    sub_task_num = Column(Integer, nullable=True, comment="Subtask number")
    rounds = Column(Integer, default=False, comment="dialogue turns")

    content = Column(Text, nullable=True, comment="Content of the speech")
    context = Column(Text, nullable=True, comment="Current conversation context")
    context = Column(Text, nullable=True, comment="Current conversation context")

    role = Column(String(255), nullable=False, comment="The role of the current message content")

    gmt_created = Column(
        DateTime, default=datetime.utcnow, comment="create time"
    )

    Index("idx_q_messages", "conv_id", "rounds", "sender")


class GptsMessagesDao(BaseDao[GptsMessagesEntity]):
    def __init__(self):
        super().__init__(
            database=META_DATA_DATABASE,
            orm_base=Base,
            db_engine=engine,
            session=session,
        )

    def append(self, entity: dict):
        session = self.get_session()
        message = GptsMessagesEntity(**entity)
        session.add(message)
        session.commit()
        id = message.id
        session.close()
        return id

    def get_by_agent(self, agent: str) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if agent:
            gpts_messages = gpts_messages.filter(
                or_(GptsMessagesEntity.sender == agent, GptsMessagesEntity.receiver == agent))
        result = gpts_messages.all()
        session.close()
        return result

    def get_between_agents(self, agent1: str, agent2: str) -> Optional[List[GptsMessagesEntity]]:
        session = self.get_session()
        gpts_messages = session.query(GptsMessagesEntity)
        if agent1 and agent2:
            gpts_messages = gpts_messages.filter(or_(
                and_(GptsMessagesEntity.sender == agent1, GptsMessagesEntity.receiver == agent2),
                and_(GptsMessagesEntity.sender == agent2, GptsMessagesEntity.receiver == agent1)))
        result = gpts_messages.all()
        session.close()
        return result
