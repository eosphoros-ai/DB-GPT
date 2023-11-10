from sqlalchemy import Integer, Column, String, DateTime

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import engine, session, Base

import random


class ApiKeyEntity(Base):
    __tablename__ = "api_key"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True)

    """LLM name"""
    llm_model = Column(String(100))

    """Secret key"""
    sk = Column(String(100))

    """LLM status ('UP', 'DOWN')"""
    status = Column(String(100))

    gmt_created = Column(DateTime)

    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"ApiKeyEntity(id={self.id}, llm_model='{self.llm_model}', sk='{self.sk}', status='{self.status}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class ApiKeyDao(BaseDao):
    def __init__(self):
        super().__init__(
            database="dbgpt", orm_base=Base, db_engine=engine, session=session
        )

    def get_one_valid_key(self, llm_model: str) -> str:
        """
          获取随机有效key
        """
        if not type:
            raise "llm_model is null"
        session = self.get_session()
        api_keys = session.query(ApiKeyEntity).filter(ApiKeyEntity.llm_model == llm_model).filter(ApiKeyEntity.status == 'UP').all()
        if len(api_keys) == 0:
            raise "No valid key found."
        key = api_keys[random.randint(0, len(api_keys) - 1)]
        print(f"valid key ({llm_model}, {key.sk})")
        return key.sk

    def add_key(self, api_key: ApiKeyEntity):
        if api_key.llm_model and api_key.sk:
            session = self.get_session()
            session.add(api_key)
            session.commit()
            session.close()
            return True
        return False

    def remove_key(self, api_key: ApiKeyEntity):
        session = self.get_session()
        if api_key.sk and api_key.llm_model:
            session.query(ApiKeyEntity).filter(ApiKeyEntity.sk == api_key.sk).filter(ApiKeyEntity.llm_model == api_key.llm_model).delete()
            session.commit()
            session.close()
            return True
        return False
