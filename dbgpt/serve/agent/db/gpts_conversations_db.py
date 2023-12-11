from datetime import datetime
from typing import List
from sqlalchemy import Column, Integer, String, Index, DateTime, func, Text
from sqlalchemy import UniqueConstraint

from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata.meta_data import (
    Base,
    engine,
    session,
    META_DATA_DATABASE,
)



class GptsConversationsEntity(Base):
    __tablename__ = "gpts_conversations"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    conv_id = Column(String(255), nullable=True, comment="The unique id of the conversation record")
    user_goal = Column(Text, nullable=True, comment="User's goals content")

    gpts_name = Column(String(255), nullable=True, comment="The gpts name")
    state = Column(String(255), nullable=True, comment="The gpts state")


    max_auto_reply_round =  Column(Integer, nullable=False, comment="max auto reply round")
    auto_reply_count = Column(Integer, nullable=False, comment="auto reply count")


    user_code = Column(String(255), nullable=False, comment="user code")
    system_app = Column(String(255), nullable=True, comment="system app ")

    created_at = Column(
        DateTime, default=datetime.utcnow, comment="create time"
    )
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="last update time"
    )

    UniqueConstraint("conv_id", name="uk_gpts_conversations")
    Index("idx_q_gpts", "gpts_name")
    Index("idx_q_content", "goal_introdiction")

class GptsConversationsDao(BaseDao[GptsConversationsEntity]):
    def __init__(self):
        super().__init__(
            database=META_DATA_DATABASE,
            orm_base=Base,
            db_engine=engine,
            session=session,
        )

    def add(self, engity: GptsConversationsEntity):
        session = self.get_session()
        my_plugin = GptsConversationsEntity(
            tenant=engity.tenant,
            user_code=engity.user_code,
            user_name=engity.user_name,
            name=engity.name,
            type=engity.type,
            version=engity.version,
            use_count=engity.use_count or 0,
            succ_count=engity.succ_count or 0,
            gmt_created=datetime.now(),
        )
        session.add(my_plugin)
        session.commit()
        id = my_plugin.id
        session.close()
        return id
