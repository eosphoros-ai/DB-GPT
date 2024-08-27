import json
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.app.knowledge.document_db import KnowledgeDocumentEntity
from dbgpt.serve.rag.api.schemas import (
    ChunkServeResponse,
    DocumentChunkVO,
    DocumentServeResponse,
    DocumentVO,
)


class ChunkQueryResponse(BaseModel):
    """data: data"""

    data: List[ChunkServeResponse] = Field(None, description="document chunk list")
    """summary: document summary"""
    summary: Optional[str] = Field(None, description="document summary")
    """total: total size"""
    total: Optional[int] = Field(None, description="total size")
    """page: current page"""
    page: Optional[int] = Field(None, description="current page")


class DocumentResponse(BaseModel):
    """DocumentResponse: DocumentResponse"""

    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc type")
    """vector_type: vector type"""
    doc_type: Optional[str] = Field(None, description="The doc content")
    """desc: description"""
    content: Optional[str] = Field(None, description="content")
    """vector ids"""
    vector_ids: Optional[str] = Field(None, description="vector ids")
    """space: space name"""
    space: Optional[str] = Field(None, description="space name")
    """space_id: space id"""
    space_id: Optional[int] = Field(None, description="space id")
    """status: status"""
    status: Optional[str] = Field(None, description="status")
    """last_sync: last sync time"""
    last_sync: Optional[str] = Field(None, description="last sync time")
    """result: result"""
    result: Optional[str] = Field(None, description="result")
    """summary: summary"""
    summary: Optional[str] = Field(None, description="summary")
    """gmt_created: created time"""
    gmt_created: Optional[str] = Field(None, description="created time")
    """gmt_modified: modified time"""
    gmt_modified: Optional[str] = Field(None, description="modified time")
    """chunk_size: chunk size"""
    chunk_size: Optional[int] = Field(None, description="chunk size")
    """questions: questions"""
    questions: Optional[List[str]] = Field(None, description="questions")

    @classmethod
    def to_response(cls, entity: KnowledgeDocumentEntity):
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return DocumentResponse(
            id=entity.id,
            doc_name=entity.doc_name,
            doc_type=entity.doc_type,
            space=entity.space,
            chunk_size=entity.chunk_size,
            status=entity.status,
            last_sync=str(entity.last_sync),
            content=entity.content,
            result=entity.result,
            vector_ids=entity.vector_ids,
            summary=entity.summary,
            questions=json.loads(entity.questions) if entity.questions else None,
            gmt_created=str(entity.gmt_created),
            gmt_modified=str(entity.gmt_modified),
        )

    @classmethod
    def serve_to_response(cls, response: DocumentServeResponse):
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return DocumentResponse(
            id=response.id,
            doc_name=response.doc_name,
            doc_type=response.doc_type,
            space=response.space,
            chunk_size=response.chunk_size,
            status=response.status,
            last_sync=str(response.last_sync),
            content=response.content,
            result=response.result,
            vector_ids=response.vector_ids,
            summary=response.summary,
            questions=json.loads(response.questions) if response.questions else None,
            gmt_created=str(response.gmt_created),
            gmt_modified=str(response.gmt_modified),
        )


class SpaceQueryResponse(BaseModel):
    """data: data"""

    id: Optional[int] = None
    name: Optional[str] = None
    """vector_type: vector type"""
    vector_type: Optional[str] = None
    """domain_type"""
    domain_type: Optional[str] = None
    """desc: description"""
    desc: Optional[str] = None
    """context: context"""
    context: Optional[str] = None
    """owner: owner"""
    owner: Optional[str] = None
    gmt_created: Optional[str] = None
    gmt_modified: Optional[str] = None
    """doc_count: doc_count"""
    docs: Optional[int] = None


class KnowledgeQueryResponse(BaseModel):
    """source: knowledge reference source"""

    source: str
    """score: knowledge vector query similarity score"""
    score: float = 0.0
    """text: raw text info"""
    text: str


class DocumentQueryResponse(BaseModel):
    """data: data"""

    data: List[DocumentResponse] = Field(None, description="document list")
    """total: total size"""
    total: Optional[int] = Field(None, description="total size")
    """page: current page"""
    page: Optional[int] = Field(None, description="current page")
