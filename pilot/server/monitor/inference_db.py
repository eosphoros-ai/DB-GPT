"""
  User payment, User inference count, and decide if attach the limitation for free.

  give me a star then you can continue with more free tokens.


  Query the latest 1 day, if the user request_count > 20次/day, do not allowed.

"""
from sqlalchemy import Column, Integer, Text, DateTime, String

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import engine, session, Base


class InferenceRequestEntity(Base):
    __tablename__ = "inference_request"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True)

    """ current user_id"""
    user_id = Column(String(100))

    """ current request"""
    request = Column(Text)

    """ current response"""
    response = Column(Text)

    """ current cost tokens"""
    use_tokens = Column(Integer)

    gmt_created = Column(DateTime)

    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"InferenceRequestEntity(id={self.id}, user_id='{self.user_id}', request='{self.request}', response='{self.response}', use_tokens='{self.use_tokens}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class InferenceRequestDao(BaseDao):
    def __init__(self):
        super().__init__(
            database="dbgpt", orm_base=Base, db_engine=engine, session=session
        )

    def add_inference_request(self, req: InferenceRequestEntity):
        session = self.get_session()
        session.add(req)
        session.commit()
        session.close()

    def get_inference_requests(self, query: InferenceRequestEntity, page=1, page_size=20):
        session = self.get_session()
        inference_requests = session.query(InferenceRequestEntity)
        if query.id is not None:
            inference_requests = inference_requests.filter(
                InferenceRequestEntity.id == query.id
            )
        if query.user_id is not None:
            inference_requests = inference_requests.filter(
                InferenceRequestEntity.user_id == query.user_id
            )
        inference_requests = inference_requests.order_by(InferenceRequestEntity.id.desc())
        inference_requests = inference_requests.offset((page - 1) * page_size).limit(
            page_size
        )
        result = inference_requests.all()
        session.close()
        return result
