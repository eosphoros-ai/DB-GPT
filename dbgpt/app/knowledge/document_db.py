from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Text, func

from dbgpt.storage.metadata import BaseDao, Model
from dbgpt._private.config import Config

CFG = Config()


class KnowledgeDocumentEntity(Model):
    __tablename__ = "knowledge_document"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id = Column(Integer, primary_key=True)
    doc_name = Column(String(100))
    doc_type = Column(String(100))
    space = Column(String(100))
    chunk_size = Column(Integer)
    status = Column(String(100))
    last_sync = Column(DateTime)
    content = Column(Text)
    result = Column(Text)
    vector_ids = Column(Text)
    summary = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"KnowledgeDocumentEntity(id={self.id}, doc_name='{self.doc_name}', doc_type='{self.doc_type}', chunk_size='{self.chunk_size}', status='{self.status}', last_sync='{self.last_sync}', content='{self.content}', result='{self.result}', summary='{self.summary}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class KnowledgeDocumentDao(BaseDao):
    def create_knowledge_document(self, document: KnowledgeDocumentEntity):
        session = self.get_raw_session()
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
        session = self.get_raw_session()
        print(f"current session:{session}")
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
        session.close()
        return result

    def get_documents(self, query):
        session = self.get_raw_session()
        print(f"current session:{session}")
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
        result = knowledge_documents.all()
        session.close()
        return result

    def get_knowledge_documents_count_bulk(self, space_names):
        session = self.get_raw_session()
        """
        Perform a batch query to count the number of documents for each knowledge space.

        Args:
            space_names: A list of knowledge space names to query for document counts.
            session: A SQLAlchemy session object.

        Returns:
            A dictionary mapping each space name to its document count.
        """
        counts_query = (
            session.query(
                KnowledgeDocumentEntity.space,
                func.count(KnowledgeDocumentEntity.id).label("document_count"),
            )
            .filter(KnowledgeDocumentEntity.space.in_(space_names))
            .group_by(KnowledgeDocumentEntity.space)
        )

        results = counts_query.all()
        docs_count = {result.space: result.document_count for result in results}
        return docs_count

    def get_knowledge_documents_count(self, query):
        session = self.get_raw_session()
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
        session.close()
        return count

    def update_knowledge_document(self, document: KnowledgeDocumentEntity):
        session = self.get_raw_session()
        updated_space = session.merge(document)
        session.commit()
        return updated_space.id

    #
    def delete(self, query: KnowledgeDocumentEntity):
        session = self.get_raw_session()
        knowledge_documents = session.query(KnowledgeDocumentEntity)
        if query.id is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.id == query.id
            )
        if query.doc_name is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.doc_name == query.doc_name
            )
        if query.space is not None:
            knowledge_documents = knowledge_documents.filter(
                KnowledgeDocumentEntity.space == query.space
            )
        knowledge_documents.delete()
        session.commit()
        session.close()
