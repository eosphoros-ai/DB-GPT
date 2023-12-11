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

    def add(self, engity: GptsMessagesEntity):
        session = self.get_session()
        my_plugin = GptsMessagesEntity(
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
