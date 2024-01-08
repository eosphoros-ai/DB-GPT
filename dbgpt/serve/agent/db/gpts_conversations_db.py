from datetime import datetime

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
)

from dbgpt.storage.metadata import BaseDao, Model


class GptsConversationsEntity(Model):
    __tablename__ = "gpts_conversations"
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    conv_id = Column(
        String(255), nullable=False, comment="The unique id of the conversation record"
    )
    user_goal = Column(Text, nullable=False, comment="User's goals content")

    gpts_name = Column(String(255), nullable=False, comment="The gpts name")
    state = Column(String(255), nullable=True, comment="The gpts state")

    max_auto_reply_round = Column(
        Integer, nullable=False, comment="max auto reply round"
    )
    auto_reply_count = Column(Integer, nullable=False, comment="auto reply count")

    user_code = Column(String(255), nullable=True, comment="user code")
    sys_code = Column(String(255), nullable=True, comment="system app ")

    created_at = Column(DateTime, default=datetime.utcnow, comment="create time")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )

    __table_args__ = (
        UniqueConstraint("conv_id", name="uk_gpts_conversations"),
        Index("idx_gpts_name", "gpts_name"),
    )


class GptsConversationsDao(BaseDao):
    def add(self, engity: GptsConversationsEntity):
        session = self.get_raw_session()
        session.add(engity)
        session.commit()
        id = engity.id
        session.close()
        return id

    def get_by_conv_id(self, conv_id: str):
        session = self.get_raw_session()
        gpts_conv = session.query(GptsConversationsEntity)
        if conv_id:
            gpts_conv = gpts_conv.filter(GptsConversationsEntity.conv_id == conv_id)
        result = gpts_conv.first()
        session.close()
        return result

    def get_convs(self, user_code: str = None, system_app: str = None):
        session = self.get_raw_session()
        gpts_conversations = session.query(GptsConversationsEntity)
        if user_code:
            gpts_conversations = gpts_conversations.filter(
                GptsConversationsEntity.user_code == user_code
            )
        if system_app:
            gpts_conversations = gpts_conversations.filter(
                GptsConversationsEntity.system_app == system_app
            )

        result = (
            gpts_conversations.limit(20)
            .order_by(desc(GptsConversationsEntity.id))
            .all()
        )
        session.close()
        return result

    def update(self, conv_id: str, state: str):
        session = self.get_raw_session()
        gpts_convs = session.query(GptsConversationsEntity)
        gpts_convs = gpts_convs.filter(GptsConversationsEntity.conv_id == conv_id)
        gpts_convs.update(
            {GptsConversationsEntity.state: state}, synchronize_session="fetch"
        )
        session.commit()
        session.close()
