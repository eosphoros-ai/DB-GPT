from datetime import datetime
from typing import Any, Dict, List, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from dbgpt._private.config import Config
from dbgpt._private.pydantic import model_to_dict
from dbgpt.serve.conversation.api.schemas import ServeRequest
from dbgpt.serve.rag.api.schemas import (
    DocumentServeRequest,
    DocumentServeResponse,
    DocumentVO,
)
from dbgpt.storage.metadata import BaseDao, Model

CFG = Config()


class KnowledgeDocumentEntity(Model):
    __tablename__ = "knowledge_document"
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

    @classmethod
    def to_document_vo(
        cls, entity_list: List["KnowledgeDocumentEntity"]
    ) -> List[DocumentVO]:
        vo_results = []
        for item in entity_list:
            vo_results.append(
                DocumentVO(
                    id=item.id,
                    doc_name=item.doc_name,
                    doc_type=item.doc_type,
                    space=item.space,
                    chunk_size=item.chunk_size,
                    status=item.status,
                    last_sync=item.last_sync.strftime("%Y-%m-%d %H:%M:%S"),
                    content=item.content,
                    result=item.result,
                    vector_ids=item.vector_ids,
                    summary=item.summary,
                    gmt_created=item.gmt_created.strftime("%Y-%m-%d %H:%M:%S"),
                    gmt_modified=item.gmt_modified.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
        return vo_results

    @classmethod
    def from_document_vo(cls, vo: DocumentVO) -> "KnowledgeDocumentEntity":
        entity = KnowledgeDocumentEntity(
            id=vo.id,
            doc_name=vo.doc_name,
            doc_type=vo.doc_type,
            space=vo.space,
            chunk_size=vo.chunk_size,
            status=vo.status,
            content=vo.content,
            result=vo.result,
            vector_ids=vo.vector_ids,
            summary=vo.summary,
        )
        if vo.last_sync:
            entity.last_sync = datetime.strptime(vo.last_sync, "%Y-%m-%d %H:%M:%S")
        if vo.gmt_created:
            entity.gmt_created = datetime.strptime(vo.gmt_created, "%Y-%m-%d %H:%M:%S")
        if vo.gmt_modified:
            entity.gmt_modified = datetime.strptime(
                vo.gmt_modified, "%Y-%m-%d %H:%M:%S"
            )
        return entity


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

    def get_knowledge_documents(self, query, page=1, page_size=20) -> List[DocumentVO]:
        """Get a list of documents that match the given query.
        Args:
            query: A KnowledgeDocumentEntity object containing the query parameters.
            page: The page number to return.
            page_size: The number of documents to return per page.
        """
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
        return KnowledgeDocumentEntity.to_document_vo(result)

    def documents_by_ids(self, ids) -> List[DocumentVO]:
        """Get a list of documents by their IDs.
        Args:
            ids: A list of document IDs.
        Returns:
            A list of KnowledgeDocumentEntity objects.
        """
        session = self.get_raw_session()
        print(f"current session:{session}")
        knowledge_documents = session.query(KnowledgeDocumentEntity)
        knowledge_documents = knowledge_documents.filter(
            KnowledgeDocumentEntity.id.in_(ids)
        )
        result = knowledge_documents.all()
        session.close()
        return KnowledgeDocumentEntity.to_document_vo(result)

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
        session.close()
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
        update_space_id = updated_space.id
        session.close()
        return update_space_id

    #
    def raw_delete(self, query: KnowledgeDocumentEntity):
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

    def from_request(
        self, request: Union[ServeRequest, Dict[str, Any]]
    ) -> KnowledgeDocumentEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            model_to_dict(request)
            if isinstance(request, DocumentServeRequest)
            else request
        )
        entity = KnowledgeDocumentEntity(**request_dict)
        return entity

    def to_request(self, entity: KnowledgeDocumentEntity) -> DocumentServeResponse:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return DocumentServeResponse(
            id=entity.id,
            doc_name=entity.doc_name,
            doc_type=entity.doc_type,
            space=entity.space,
            chunk_size=entity.chunk_size,
            status=entity.status,
            last_sync=entity.last_sync,
            content=entity.content,
            result=entity.result,
            vector_ids=entity.vector_ids,
            summary=entity.summary,
            gmt_created=entity.gmt_created,
            gmt_modified=entity.gmt_modified,
        )

    def to_response(self, entity: KnowledgeDocumentEntity) -> DocumentServeResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return DocumentServeResponse(
            id=entity.id,
            doc_name=entity.doc_name,
            doc_type=entity.doc_type,
            space=entity.space,
            chunk_size=entity.chunk_size,
            status=entity.status,
            last_sync=entity.last_sync,
            content=entity.content,
            result=entity.result,
            vector_ids=entity.vector_ids,
            summary=entity.summary,
            gmt_created=entity.gmt_created,
            gmt_modified=entity.gmt_modified,
        )
