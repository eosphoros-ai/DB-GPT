from datetime import datetime
from typing import List
from sqlalchemy import Column, Integer, String, Index, DateTime, func, Text
from sqlalchemy import UniqueConstraint

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import (
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
    user_code = Column(String(255), nullable=False, comment="user code")
    user_name = Column(String(255), nullable=True, comment="user name")
    max_auto_reply_round =  Column(Integer, nullable=False, comment="max auto reply round")
    auto_reply_count = Column(Integer, nullable=False, comment="auto reply count")

    gpts_name = Column(String(255), nullable=True, comment="The gpts name")
    goal_introdiction = Column(String(255), nullable=True, comment="The introdiction if goal")

    gmt_created = Column(
        DateTime, default=datetime.utcnow, comment="create time"
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
