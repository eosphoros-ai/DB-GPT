from typing import List
from sqlalchemy import Column, Integer, String, Index, DateTime, func, Boolean, Text
from sqlalchemy import UniqueConstraint

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import (
    Base,
    engine,
    session,
    META_DATA_DATABASE,
)


class ConnectConfigEntity(Base):
    __tablename__ = "connect_config"
    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )
    db_type = Column(String(255), nullable=False, comment="db type")
    db_name = Column(String(255), nullable=False, comment="db name")
    db_path = Column(String(255), nullable=True, comment="file db path")
    db_host = Column(String(255), nullable=True, comment="db connect host(not file db)")
    db_port = Column(String(255), nullable=True, comment="db cnnect port(not file db)")
    db_user = Column(String(255), nullable=True, comment="db user")
    db_pwd = Column(String(255), nullable=True, comment="db password")
    comment = Column(Text, nullable=True, comment="db comment")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")

    __table_args__ = (
        UniqueConstraint("db_name", name="uk_db"),
        Index("idx_q_db_type", "db_type"),
    )


class ConnectConfigDao(BaseDao[ConnectConfigEntity]):
    def __init__(self):
        super().__init__(
            database=META_DATA_DATABASE,
            orm_base=Base,
            db_engine=engine,
            session=session,
        )

    def update(self, entity: ConnectConfigEntity):
        session = self.get_session()
        try:
            updated = session.merge(entity)
            session.commit()
            return updated.id
        finally:
            session.close()

    def delete(self, db_name: int):
        session = self.get_session()
        if db_name is None:
            raise Exception("db_name is None")

        db_connect = session.query(ConnectConfigEntity)
        db_connect = db_connect.filter(ConnectConfigEntity.db_name == db_name)
        db_connect.delete()
        session.commit()
        session.close()

    def get_by_name(self, db_name: str) -> ConnectConfigEntity:
        session = self.get_session()
        db_connect = session.query(ConnectConfigEntity)
        db_connect = db_connect.filter(ConnectConfigEntity.db_name == db_name)
        result = db_connect.first()
        session.close()
        return result
