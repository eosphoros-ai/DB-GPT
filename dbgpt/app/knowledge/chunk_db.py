from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from dbgpt._private.config import Config
from dbgpt.serve.rag.api.schemas import DocumentChunkVO
from dbgpt.storage.metadata import BaseDao, Model

CFG = Config()


class DocumentChunkEntity(Model):
    __tablename__ = "document_chunk"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer)
    doc_name = Column(String(100))
    doc_type = Column(String(100))
    content = Column(Text)
    meta_info = Column(String(500))
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"DocumentChunkEntity(id={self.id}, doc_name='{self.doc_name}', doc_type='{self.doc_type}', document_id='{self.document_id}', content='{self.content}', meta_info='{self.meta_info}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"

    @classmethod
    def to_to_document_chunk_vo(cls, entity_list: List["DocumentChunkEntity"]):
        return [
            DocumentChunkVO(
                id=entity.id,
                document_id=entity.document_id,
                doc_name=entity.doc_name,
                doc_type=entity.doc_type,
                content=entity.content,
                meta_info=entity.meta_info,
                gmt_created=entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S"),
                gmt_modified=entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for entity in entity_list
        ]


class DocumentChunkDao(BaseDao):
    def create_documents_chunks(self, documents: List):
        session = self.get_raw_session()
        docs = [
            DocumentChunkEntity(
                doc_name=document.doc_name,
                doc_type=document.doc_type,
                document_id=document.document_id,
                content=document.content or "",
                meta_info=document.meta_info or "",
                gmt_created=datetime.now(),
                gmt_modified=datetime.now(),
            )
            for document in documents
        ]
        session.add_all(docs)
        session.commit()
        session.close()

    def get_document_chunks(
        self, query: DocumentChunkEntity, page=1, page_size=20, document_ids=None
    ) -> List[DocumentChunkVO]:
        session = self.get_raw_session()
        document_chunks = session.query(DocumentChunkEntity)
        if query.id is not None:
            document_chunks = document_chunks.filter(DocumentChunkEntity.id == query.id)
        if query.document_id is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.document_id == query.document_id
            )
        if query.doc_type is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.doc_type == query.doc_type
            )
        if query.content is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.content == query.content
            )
        if query.doc_name is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.doc_name == query.doc_name
            )
        if query.meta_info is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.meta_info == query.meta_info
            )
        if document_ids is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.document_id.in_(document_ids)
            )

        document_chunks = document_chunks.order_by(DocumentChunkEntity.id.asc())
        document_chunks = document_chunks.offset((page - 1) * page_size).limit(
            page_size
        )
        result = document_chunks.all()
        session.close()
        return DocumentChunkEntity.to_to_document_chunk_vo(result)

    def get_document_chunks_count(self, query: DocumentChunkEntity):
        session = self.get_raw_session()
        document_chunks = session.query(func.count(DocumentChunkEntity.id))
        if query.id is not None:
            document_chunks = document_chunks.filter(DocumentChunkEntity.id == query.id)
        if query.document_id is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.document_id == query.document_id
            )
        if query.doc_type is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.doc_type == query.doc_type
            )
        if query.doc_name is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.doc_name == query.doc_name
            )
        if query.meta_info is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.meta_info == query.meta_info
            )
        count = document_chunks.scalar()
        session.close()
        return count

    def raw_delete(self, document_id: int):
        session = self.get_raw_session()
        if document_id is None:
            raise Exception("document_id is None")
        query = DocumentChunkEntity(document_id=document_id)
        knowledge_documents = session.query(DocumentChunkEntity)
        if query.document_id is not None:
            chunks = knowledge_documents.filter(
                DocumentChunkEntity.document_id == query.document_id
            )
        chunks.delete()
        session.commit()
        session.close()
