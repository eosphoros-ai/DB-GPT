"""Chat history database model."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from ..metadata import BaseDao, Model


class ChatHistoryEntity(Model):
    """Chat history entity."""

    __tablename__ = "chat_history"
    __table_args__ = (UniqueConstraint("conv_uid", name="uk_conv_uid"),)
    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )
    conv_uid = Column(
        String(255),
        # Change from False to True, the alembic migration will fail, so we use
        # UniqueConstraint to replace it
        unique=False,
        nullable=False,
        comment="Conversation record unique id",
    )
    chat_mode = Column(String(255), nullable=False, comment="Conversation scene mode")
    summary = Column(
        Text(length=2**31 - 1), nullable=False, comment="Conversation record summary"
    )
    user_name = Column(String(255), nullable=True, comment="interlocutor")
    messages = Column(
        Text(length=2**31 - 1), nullable=True, comment="Conversation details"
    )
    message_ids = Column(
        Text(length=2**31 - 1), nullable=True, comment="Message ids, split by comma"
    )
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")

    Index("idx_q_user", "user_name")
    Index("idx_q_mode", "chat_mode")
    Index("idx_q_conv", "summary")


class ChatHistoryMessageEntity(Model):
    """Chat history message entity."""

    __tablename__ = "chat_history_message"
    __table_args__ = (
        UniqueConstraint("conv_uid", "index", name="uk_conversation_message"),
    )
    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )
    conv_uid = Column(
        String(255),
        unique=False,
        nullable=False,
        comment="Conversation record unique id",
    )
    index = Column(Integer, nullable=False, comment="Message index")
    round_index = Column(Integer, nullable=False, comment="Message round index")
    message_detail = Column(
        Text(length=2**31 - 1), nullable=True, comment="Message details, json format"
    )
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")


class ChatHistoryDao(BaseDao):
    """Chat history dao."""

    def list_last_20(
        self, user_name: Optional[str] = None, sys_code: Optional[str] = None
    ):
        """Retrieve the last 20 chat history records."""
        session = self.get_raw_session()
        chat_history = session.query(ChatHistoryEntity)
        if user_name:
            chat_history = chat_history.filter(ChatHistoryEntity.user_name == user_name)
        if sys_code:
            chat_history = chat_history.filter(ChatHistoryEntity.sys_code == sys_code)

        chat_history = chat_history.order_by(ChatHistoryEntity.id.desc())

        result = chat_history.limit(20).all()
        session.close()
        return result

    def raw_update(self, entity: ChatHistoryEntity):
        """Update the chat history record."""
        session = self.get_raw_session()
        try:
            updated = session.merge(entity)
            session.commit()
            return updated.id
        finally:
            session.close()

    def update_message_by_uid(self, message: str, conv_uid: str):
        """Update the chat history record."""
        session = self.get_raw_session()
        try:
            chat_history = session.query(ChatHistoryEntity)
            chat_history = chat_history.filter(ChatHistoryEntity.conv_uid == conv_uid)
            updated = chat_history.update({ChatHistoryEntity.messages: message})
            session.commit()
            return updated
        finally:
            session.close()

    def raw_delete(self, conv_uid: str):
        """Delete the chat history record."""
        if conv_uid is None:
            raise Exception("conv_uid is None")
        with self.session() as session:
            chat_history = session.query(ChatHistoryEntity)
            chat_history = chat_history.filter(ChatHistoryEntity.conv_uid == conv_uid)
            chat_history.delete()

    def get_by_uid(self, conv_uid: str) -> Optional[ChatHistoryEntity]:
        """Retrieve the chat history record by conv_uid."""
        with self.session(commit=False) as session:
            return session.query(ChatHistoryEntity).filter_by(conv_uid=conv_uid).first()
