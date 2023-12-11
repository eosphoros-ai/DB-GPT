from datetime import datetime
from typing import List
from sqlalchemy import Column, Integer, String, Index, DateTime, func, Text, Boolean
from sqlalchemy import UniqueConstraint

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import (
    Base,
    engine,
    session,
    META_DATA_DATABASE,
)


class GptsInstanceEntity(Base):
    __tablename__ = "gpts_instance"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    gpts_name = Column(String(255), nullable=False, comment="Current AI assistant name")
    gpts_describe= Column(String(2255), nullable=False, comment="Current AI assistant describe")
    gpts_db_names = Column(Text, nullable=True, comment="List of structured database names contained in the current gpts")
    search_web = Column(Boolean, nullable=True, comment="Is it possible to retrieve information from the internet")
    gpts_knowledge_names = Column(Text, nullable=True, comment="List of unstructured database names contained in the current gpts")
    gpts_agents = Column(Text, nullable=True, comment="List of agents names contained in the current gpts")
    gpts_models = Column(Text, nullable=True, comment="List of llm model names contained in the current gpts")
    user_code = Column(String(255), nullable=False, comment="user code")
    user_name = Column(String(255), nullable=True, comment="user name")

    planner_system = Column(Text, nullable=True, comment="Planner system messages")

    gmt_created = Column(
        DateTime, default=datetime.utcnow, comment="gpts create time"
    )
    UniqueConstraint("gpts_name", name="uk_gpts")



class GptsInstanceDao(BaseDao[GptsInstanceEntity]):
    def __init__(self):
        super().__init__(
            database=META_DATA_DATABASE,
            orm_base=Base,
            db_engine=engine,
            session=session,
        )

    def add(self, engity: GptsPlansEntity):
        session = self.get_session()
        my_plugin = MyPluginEntity(
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
