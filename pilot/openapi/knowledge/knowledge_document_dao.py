from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Text, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

from pilot.configs.config import Config


CFG = Config()

Base = declarative_base()


class KnowledgeDocumentEntity(Base):
    __tablename__ = "knowledge_document"
    id = Column(Integer, primary_key=True)
    doc_name = Column(String(100))
    doc_type = Column(String(100))
    space = Column(String(100))
    chunk_size = Column(Integer)
    status = Column(String(100))
    last_sync = Column(String(100))
    content = Column(Text)
    result = Column(Text)
    vector_ids = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"KnowledgeDocumentEntity(id={self.id}, doc_name='{self.doc_name}', doc_type='{self.doc_type}', chunk_size='{self.chunk_size}', status='{self.status}', last_sync='{self.last_sync}', content='{self.content}', result='{self.result}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class KnowledgeDocumentDao:
    def __init__(self):
        database = "knowledge_management"
        self.db_engine = create_engine(
            f"mysql+pymysql://{CFG.LOCAL_DB_USER}:{CFG.LOCAL_DB_PASSWORD}@{CFG.LOCAL_DB_HOST}:{CFG.LOCAL_DB_PORT}/{database}",
            echo=True,
        )
        self.Session = sessionmaker(bind=self.db_engine)

    def create_knowledge_document(self, document: KnowledgeDocumentEntity):
        session = self.Session()
        knowledge_document = KnowledgeDocumentEntity(
            doc_name=document.doc_name,
            doc_type=document.doc_type,
            space=document.space,
            chunk_size=0.0,
            status=document.status,
            last_sync=document.last_sync,
            content=document.content or "",
            result=document.result or "",
            vector_ids=document.vector_ids,
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
        )
        session.add(knowledge_document)
        session.commit()
        doc_id = knowledge_document.id
        session.close()
        return doc_id

    def get_knowledge_documents(self, query, page=1, page_size=20):
        session = self.Session()
        knowledge_documents = session.query(KnowledgeDocumentEntity)
        if query.id is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.id == query.id
            )
        if query.doc_name is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.doc_name == query.doc_name
            )
        if query.doc_type is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.doc_type == query.doc_type
            )
        if query.space is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.space == query.space
            )
        if query.status is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.status == query.status
            )

        knowledge_documents = knowledge_documents.order_by(
            KnowledgeDocumentEntity.id.desc()
        )
        knowledge_documents = knowledge_documents.offset((page - 1) * page_size).limit(
            page_size
        )
        result = knowledge_documents.all()
        return result

    def get_knowledge_documents_count(self, query):
        session = self.Session()
        knowledge_documents = session.query(func.count(KnowledgeDocumentEntity.id))
        if query.id is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.id == query.id
            )
        if query.doc_name is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.doc_name == query.doc_name
            )
        if query.doc_type is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.doc_type == query.doc_type
            )
        if query.space is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.space == query.space
            )
        if query.status is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.status == query.status
            )
        count = knowledge_documents.scalar()
        return count

    def update_knowledge_document(self, document: KnowledgeDocumentEntity):
        session = self.Session()
        updated_space = session.merge(document)
        session.commit()
        return updated_space.id

    #
    # def delete_knowledge_document(self, document_id: int):
    #     cursor = self.conn.cursor()
    #     query = "DELETE FROM knowledge_document WHERE id = %s"
    #     cursor.execute(query, (document_id,))
    #     self.conn.commit()
    #     cursor.close()
