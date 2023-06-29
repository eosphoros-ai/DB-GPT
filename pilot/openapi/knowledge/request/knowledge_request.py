from typing import List

from pydantic import BaseModel
from fastapi import UploadFile


class KnowledgeQueryRequest(BaseModel):
    """query: knowledge query"""

    query: str
    """top_k: return topK documents"""
    top_k: int


class KnowledgeSpaceRequest(BaseModel):
    """name: knowledge space name"""

    name: str = None
    """vector_type: vector type"""
    vector_type: str = None
    """desc: description"""
    desc: str = None
    """owner: owner"""
    owner: str = None


class KnowledgeDocumentRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: str = None
    """doc_type: doc type"""
    doc_type: str = None
    """content: content"""
    content: str = None
    """content: content"""
    source: str = None

    """text_chunk_size: text_chunk_size"""
    # text_chunk_size: int


class DocumentQueryRequest(BaseModel):
    """doc_name: doc path"""

    doc_name: str = None
    """doc_type: doc type"""
    doc_type: str = None
    """status: status"""
    status: str = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class DocumentSyncRequest(BaseModel):
    """doc_ids: doc ids"""

    doc_ids: List


class ChunkQueryRequest(BaseModel):
    """id: id"""

    id: int = None
    """document_id: doc id"""
    document_id: int = None
    """doc_name: doc path"""
    doc_name: str = None
    """doc_type: doc type"""
    doc_type: str = None
    """page: page"""
    page: int = 1
    """page_size: page size"""
    page_size: int = 20


class KnowledgeQueryResponse:
    """source: knowledge reference source"""

    source: str
    """score: knowledge vector query similarity score"""
    score: float = 0.0
    """text: raw text info"""
    text: str
