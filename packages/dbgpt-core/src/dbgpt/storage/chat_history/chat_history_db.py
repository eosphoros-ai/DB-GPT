"""Chat history database model."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)


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
    app_code = Column(String(255), nullable=True, comment="App unique code")

    Index("idx_q_user", "user_name")
    Index("idx_q_mode", "chat_mode")
    Index("idx_q_conv", "summary")
    Index("idx_chat_his_app_code", "app_code")


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

    def list_hot_apps(self, skip_page: int = 0, top_k: int = 20):
        """Get list hot app list.

        Select COUNT(*) as sz, app_code from chat_history
        where app_code in
        (select app_code from gpts_app where
        published = 'true' and team_mode != 'native_app')
        group by app_code order by sz desc
        LIMIT (skip_page * top_k), (top_k)
        """
        from dbgpt_serve.agent.db.gpts_app import GptsAppDao

        gpts_app_dao = GptsAppDao()
        apps = gpts_app_dao.list_all()
        app_codes = [
            app.app_code
            for app in apps
            if app.published == "true" and app.app_code is not None
        ]
        if len(app_codes) == 0:
            return []

        session = self.get_raw_session()
        try:
            hot_apps = (
                session.query(
                    ChatHistoryEntity.app_code,
                    func.count(ChatHistoryEntity.app_code).label("sz"),
                )
                .filter(ChatHistoryEntity.app_code.in_(app_codes))
                .group_by(ChatHistoryEntity.app_code)
                .order_by(desc("sz"))
                .limit(top_k)
                .offset(skip_page * top_k)
                .all()
            )
        finally:
            session.close()
        return hot_apps

    def get_hot_app_map(self, skip_page: int = 0, top_k: int = 20):
        """Get hot app map."""
        with self.get_raw_session() as session:
            try:
                result = session.execute(
                    text(
                        f"""SELECT c.app_code, count(*) as sz FROM chat_history a
    INNER JOIN chat_history_message b on a.conv_uid = b.conv_uid
    INNER JOIN gpts_app c ON a.app_code = c.app_code and c.published = 'true'
    GROUP BY c.app_code
    ORDER BY sz desc  LIMIT {str(skip_page)}, {str(top_k)};"""
                    )
                )
                keys = result.keys()
                rows = [dict(zip(keys, row)) for row in result]
                return rows
            except Exception as e:
                logger.error(f"Error executing SQL query: {e}")
                raise e
