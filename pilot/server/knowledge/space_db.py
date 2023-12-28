from datetime import datetime

from sqlalchemy import Column, Integer, Text, String, DateTime

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import (
    Base,
    engine,
    session,
    META_DATA_DATABASE,
)
from pilot.configs.config import Config
from pilot.server.knowledge.request.request import KnowledgeSpaceRequest

CFG = Config()


class KnowledgeSpaceEntity(Base):
    __tablename__ = "knowledge_space"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    vector_type = Column(String(100))
    desc = Column(String(100))
    owner = Column(String(100))
    context = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)
    user_id = Column(String(100))

    def __repr__(self):
        return f"KnowledgeSpaceEntity(id={self.id}, name='{self.name}', vector_type='{self.vector_type}', desc='{self.desc}', owner='{self.owner}' context='{self.context}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}', user_id='{self.user_id}')"


class KnowledgeSpaceDao(BaseDao):
    def __init__(self):
        super().__init__(
            database=META_DATA_DATABASE,
            orm_base=Base,
            db_engine=engine,
            session=session,
        )

    def create_knowledge_space(self, space: KnowledgeSpaceRequest):
        session = self.get_session()
        knowledge_space = KnowledgeSpaceEntity(
            name=space.name,
            vector_type=CFG.VECTOR_STORE_TYPE,
            desc=space.desc,
            owner=space.owner,
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
            user_id=space.user_id,
        )
        session.add(knowledge_space)
        session.commit()
        session.close()

    def get_knowledge_space_by_ids(self, ids):
        session = self.get_session()
        if ids:
            knowledge_spaces = session.query(KnowledgeSpaceEntity).filter(KnowledgeSpaceEntity.id.in_(ids))
        else:
            return []
        knowledge_spaces_list = knowledge_spaces.all()
        session.close()
        return knowledge_spaces_list

    def get_knowledge_space(self, query: KnowledgeSpaceEntity):
        session = self.get_session()
        knowledge_spaces = session.query(KnowledgeSpaceEntity)
        if query.user_id is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.user_id == query.user_id
            )
        if query.id is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.id == query.id
            )
        if query.name is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.name == query.name
            )
        if query.vector_type is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.vector_type == query.vector_type
            )
        if query.desc is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.desc == query.desc
            )
        if query.owner is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.owner == query.owner
            )
        if query.gmt_created is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.gmt_created == query.gmt_created
            )
        if query.gmt_modified is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.gmt_modified == query.gmt_modified
            )

        knowledge_spaces = knowledge_spaces.order_by(
            KnowledgeSpaceEntity.gmt_created.desc()
        )
        result = knowledge_spaces.all()
        session.close()
        return result

    def update_knowledge_space(self, space: KnowledgeSpaceEntity):
        session = self.get_session()
        session.merge(space)
        session.commit()
        session.close()
        return True

    def delete_knowledge_space(self, space: KnowledgeSpaceEntity):
        session = self.get_session()
        if space:
            session.delete(space)
            session.commit()
        session.close()
