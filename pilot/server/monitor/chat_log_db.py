from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, Text, DateTime, String

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import engine, session, Base


class ChatLogEntity(Base):
    __tablename__ = "chat_log"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True)

    """ current user_id"""
    user_id = Column(String(100))

    """ current request"""
    request = Column(Text)

    gmt_created = Column(DateTime)

    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"ChatLogEntity(id={self.id}, user_id='{self.user_id}', request='{self.request}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class ChatLogDao(BaseDao):
    def __init__(self):
        super().__init__(
            database="dbgpt", orm_base=Base, db_engine=engine, session=session
        )

    def add_inference_request(self, req: ChatLogEntity):
        session = self.get_session()
        req.gmt_created = datetime.now()
        req.gmt_modified = datetime.now()
        session.add(req)
        session.commit()
        session.close()

    def get_inference_requests(self, query: ChatLogEntity, page=1, page_size=20):
        session = self.get_session()
        chat_logs = session.query(ChatLogEntity)
        if query.id is not None:
            chat_logs = chat_logs.filter(
                ChatLogEntity.id == query.id
            )
        if query.user_id is not None:
            chat_logs = chat_logs.filter(
                ChatLogEntity.user_id == query.user_id
            )
        chat_logs = chat_logs.order_by(ChatLogEntity.id.desc())
        chat_logs = chat_logs.offset((page - 1) * page_size).limit(
            page_size
        )
        result = chat_logs.all()
        session.close()
        return result

    def get_latest_one_day_records(self, user_id):
        """
          Query the latest one day records for user 'user_id'
        """
        session = self.get_session()
        try:
            now = datetime.now()
            last_day = now - timedelta(days=1)

            # Query the records within the datetime range for the given user_id
            query = session.query(ChatLogEntity).filter(
                ChatLogEntity.user_id == user_id,
                ChatLogEntity.gmt_created >= last_day,
                ChatLogEntity.gmt_created <= now
            )
            records = query.all()
            return len(records)
        finally:
            session.close()
