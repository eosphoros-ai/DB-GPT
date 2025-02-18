from datetime import datetime
from typing import Any, Dict, List, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, func, not_

from dbgpt._private.pydantic import model_to_dict
from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.storage.metadata._base_dao import QUERY_SPEC, REQ, RES
from dbgpt_serve.rag.api.schemas import ChunkServeRequest, ChunkServeResponse


class DocumentChunkEntity(Model):
    __tablename__ = "document_chunk"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer)
    doc_name = Column(String(100))
    doc_type = Column(String(100))
    content = Column(Text)
    questions = Column(Text)
    meta_info = Column(String(500))
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return (
            f"DocumentChunkEntity(id={self.id}, doc_name='{self.doc_name}', "
            f"doc_type='{self.doc_type}', "
            f"document_id='{self.document_id}', content='{self.content}', "
            f"questions='{self.questions}', meta_info='{self.meta_info}', "
            f"gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "doc_name": self.doc_name,
            "doc_type": self.doc_type,
            "content": self.content,
            "questions": self.questions,
            "meta_info": self.meta_info,
            "gmt_created": self.gmt_created,
            "gmt_modified": self.gmt_modified,
        }


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
    ):
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
                DocumentChunkEntity.content.like(f"%{query.content}%")
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
        return result

    def get_chunks_with_questions(self, query: DocumentChunkEntity, document_ids=None):
        session = self.get_raw_session()
        document_chunks = session.query(DocumentChunkEntity)
        if query.doc_name is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.doc_name == query.doc_name
            )
        if query.meta_info is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.meta_info == query.meta_info
            )
        document_chunks = document_chunks.filter(
            not_(DocumentChunkEntity.questions is None)
        )
        if document_ids is not None:
            document_chunks = document_chunks.filter(
                DocumentChunkEntity.document_id.in_(document_ids)
            )

        document_chunks = document_chunks.order_by(DocumentChunkEntity.id.asc())
        result = document_chunks.all()
        session.close()
        return result

    def update(self, query_request: QUERY_SPEC, update_request: REQ) -> RES:
        """Update an entity object.

        Args:
            query_request (REQ): The request schema object or dict for query.
            update_request (REQ): The request schema object for update.
        Returns:
            RES: The response schema object.
        """
        with self.session() as session:
            query = self._create_query_object(session, query_request)
            entry = query.first()
            if entry is None:
                raise Exception("Invalid request")
            for key, value in model_to_dict(update_request).items():  # type: ignore
                if value is not None:
                    if key in ["gmt_created", "gmt_modified"]:
                        # Assuming the datetime format is 'YYYY-MM-DD HH:MM:SS'
                        value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    setattr(entry, key, value)
            session.merge(entry)
            return self.to_response(entry)

    def update_chunk(self, chunk: DocumentChunkEntity):
        """Update a chunk"""
        try:
            session = self.get_raw_session()
            updated = session.merge(chunk)
            session.commit()
            return updated.id
        finally:
            session.close()

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

    def from_request(
        self, request: Union[ChunkServeRequest, Dict[str, Any]]
    ) -> DocumentChunkEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.dict() if isinstance(request, ChunkServeRequest) else request
        )
        entity = DocumentChunkEntity(**request_dict)
        return entity

    def to_request(self, entity: DocumentChunkEntity) -> ChunkServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return ChunkServeRequest(
            id=entity.id,
            doc_name=entity.doc_name,
            doc_type=entity.doc_type,
            document_id=entity.document_id,
            content=entity.content,
            questions=entity.questions,
            meta_info=entity.meta_info,
            gmt_created=entity.gmt_created,
            gmt_modified=entity.gmt_modified,
        )

    def to_response(self, entity: DocumentChunkEntity) -> ChunkServeResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        gmt_created_str = entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        return ChunkServeResponse(
            id=entity.id,
            doc_name=entity.doc_name,
            doc_type=entity.doc_type,
            document_id=entity.document_id,
            content=entity.content,
            questions=entity.questions,
            meta_info=entity.meta_info,
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )

    def from_response(
        self, response: Union[ChunkServeResponse, Dict[str, Any]]
    ) -> DocumentChunkEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        response_dict = (
            response.dict() if isinstance(response, ChunkServeResponse) else response
        )
        entity = DocumentChunkEntity(**response_dict)
        return entity
