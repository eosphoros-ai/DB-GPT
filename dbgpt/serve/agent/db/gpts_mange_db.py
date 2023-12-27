from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model


class GptsInstanceEntity(Model):
    __tablename__ = "gpts_instance"
    id = Column(Integer, primary_key=True, comment="autoincrement id")

    gpts_name = Column(String(255), nullable=False, comment="Current AI assistant name")
    gpts_describe = Column(
        String(2255), nullable=False, comment="Current AI assistant describe"
    )
    resource_db = Column(
        Text,
        nullable=True,
        comment="List of structured database names contained in the current gpts",
    )
    resource_internet = Column(
        Text,
        nullable=True,
        comment="Is it possible to retrieve information from the internet",
    )
    resource_knowledge = Column(
        Text,
        nullable=True,
        comment="List of unstructured database names contained in the current gpts",
    )
    gpts_agents = Column(
        String(1000),
        nullable=True,
        comment="List of agents names contained in the current gpts",
    )
    gpts_models = Column(
        String(1000),
        nullable=True,
        comment="List of llm model names contained in the current gpts",
    )
    language = Column(String(100), nullable=True, comment="gpts language")

    user_code = Column(String(255), nullable=False, comment="user code")
    sys_code = Column(String(255), nullable=True, comment="system app code")

    created_at = Column(DateTime, default=datetime.utcnow, comment="create time")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )

    __table_args__ = (UniqueConstraint("gpts_name", name="uk_gpts"),)


class GptsInstanceDao(BaseDao):
    def add(self, engity: GptsInstanceEntity):
        session = self.get_raw_session()
        session.add(engity)
        session.commit()
        id = engity.id
        session.close()
        return id

    def get_by_name(self, name: str) -> GptsInstanceEntity:
        session = self.get_raw_session()
        gpts_instance = session.query(GptsInstanceEntity)
        if name:
            gpts_instance = gpts_instance.filter(GptsInstanceEntity.gpts_name == name)
        result = gpts_instance.first()
        session.close()
        return result
