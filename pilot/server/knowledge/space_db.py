from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base

from pilot.configs.config import Config

from pilot.server.knowledge.request.request import KnowledgeSpaceRequest
from sqlalchemy.orm import sessionmaker

CFG = Config()
Base = declarative_base()


class KnowledgeSpaceEntity(Base):
    __tablename__ = "knowledge_space"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    vector_type = Column(String(100))
    desc = Column(String(100))
    owner = Column(String(100))
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"KnowledgeSpaceEntity(id={self.id}, name='{self.name}', vector_type='{self.vector_type}', desc='{self.desc}', owner='{self.owner}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class KnowledgeSpaceDao:
    def __init__(self):
        database = "knowledge_management"
        self.db_engine = create_engine(
            f"mysql+pymysql://{CFG.LOCAL_DB_USER}:{CFG.LOCAL_DB_PASSWORD}@{CFG.LOCAL_DB_HOST}:{CFG.LOCAL_DB_PORT}/{database}",
            echo=True,
        )
        self.Session = sessionmaker(bind=self.db_engine)

    def create_knowledge_space(self, space: KnowledgeSpaceRequest):
        session = self.Session()
        knowledge_space = KnowledgeSpaceEntity(
            name=space.name,
            vector_type=space.vector_type,
            desc=space.desc,
            owner=space.owner,
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
        )
        session.add(knowledge_space)
        session.commit()

        session.close()

    def get_knowledge_space(self, query: KnowledgeSpaceEntity):
        session = self.Session()
        knowledge_spaces = session.query(KnowledgeSpaceEntity)
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
        return result

    def update_knowledge_space(self, space_id: int, space: KnowledgeSpaceEntity):
        cursor = self.conn.cursor()
        query = "UPDATE knowledge_space SET name = %s, vector_type = %s, desc = %s, owner = %s WHERE id = %s"
        cursor.execute(
            query, (space.name, space.vector_type, space.desc, space.owner, space_id)
        )
        self.conn.commit()
        cursor.close()

    def delete_knowledge_space(self, space_id: int):
        cursor = self.conn.cursor()
        query = "DELETE FROM knowledge_space WHERE id = %s"
        cursor.execute(query, (space_id,))
        self.conn.commit()
        cursor.close()
